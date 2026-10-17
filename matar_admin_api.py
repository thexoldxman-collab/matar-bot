"""Authenticated admin API for Matar Admin.

All authority is derived from the Telegram-authenticated server session.
Financial requests are never marked completed by this module.
"""
from __future__ import annotations

import json
import math
import os
import secrets
from datetime import datetime, timedelta, timezone
from flask import jsonify, request


PREFERENCE_KEYS = {
    "charge_new", "withdraw_new", "financial_error", "moderator_actions",
    "referrals", "bot_offline", "ai_decisions",
}
PERMISSION_COLUMNS = {
    "can_reply_tickets", "can_handle_charges", "can_handle_withdraws",
    "can_send_broadcast", "can_manage_users", "can_charge_withdraw_users",
    "can_view_stats", "can_manage_buttons", "can_access_full_admin",
    "can_manage_moderators", "can_use_ai",
}
BUTTON_FIELDS = {
    "button_text", "parent_button", "button_type", "action", "message_text",
    "is_active", "requires_subscription", "requires_admin", "requires_moderator",
    "sort_order", "path",
}


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value=None):
    return (value or _now()).isoformat().replace("+00:00", "Z")


def register_admin_api(
    app, bot, conn, db_lock, owner_id, check_permission,
    get_operation_mode=None, complete_charge=None, complete_withdraw=None,
    cancel_charge=None, cancel_withdraw=None, get_conn=None
):
    """Register safe management endpoints. Call after register_admin_auth."""
    conn.execute("""CREATE TABLE IF NOT EXISTS admin_operation_claims (
        operation_type TEXT NOT NULL,
        operation_id INTEGER NOT NULL,
        claimed_by BIGINT NOT NULL,
        claimed_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        PRIMARY KEY (operation_type, operation_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS admin_app_preferences (
        user_id BIGINT PRIMARY KEY,
        preferences TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""")
    conn.commit()
    initialized_connections = {id(conn)}

    def db():
        active = get_conn() if callable(get_conn) else conn
        if id(active) not in initialized_connections:
            active.execute("""CREATE TABLE IF NOT EXISTS admin_operation_claims (
                operation_type TEXT NOT NULL,
                operation_id INTEGER NOT NULL,
                claimed_by BIGINT NOT NULL,
                claimed_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY (operation_type, operation_id)
            )""")
            active.execute("""CREATE TABLE IF NOT EXISTS admin_app_preferences (
                user_id BIGINT PRIMARY KEY,
                preferences TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
            active.commit()
            initialized_connections.add(id(active))
        return active

    def session():
        getter = app.config.get("MATAR_ADMIN_AUTH_SESSION")
        if not callable(getter):
            return None
        try:
            return getter()
        except Exception:
            app.logger.exception("Admin session validation failed")
            return None

    def current():
        result = session()
        if not result:
            return None
        return result[0]

    def allowed(user, permission):
        if not user:
            return False
        if user.get("role") == "owner" or int(user.get("telegram_id", 0)) == int(owner_id):
            return True
        try:
            return bool(check_permission(int(user["telegram_id"]), permission))
        except Exception:
            return False

    def denied():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    def forbidden():
        return jsonify({"ok": False, "error": "permission_denied"}), 403

    def audit(user, action, details, target_user=None, amount=None):
        try:
            db().execute(
                """INSERT INTO admin_logs
                   (admin_id, display_name, action_type, details, target_user, amount, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (int(user["telegram_id"]), "مدير التطبيق" if user.get("role") == "owner" else "مشرف التطبيق",
                 str(action)[:120], str(details)[:1000], target_user, amount,
                 _now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            db().commit()
        except Exception:
            app.logger.exception("Could not write admin app audit log")

    def permission_for_type(operation_type):
        return "can_handle_withdraws" if operation_type == "withdraw" else "can_handle_charges"

    def ensure_claims_table():
        # Reopen the underlying request when the ten-minute lease expires.
        now_text = _iso()
        expired = db().execute(
            "SELECT operation_type,operation_id,claimed_by FROM admin_operation_claims WHERE expires_at<=?",
            (now_text,),
        ).fetchall()
        for claim in expired:
            operation_type, operation_id, claimed_by = claim
            table = "pending_charges" if operation_type == "charge" else "pending_withdraws"
            db().execute(
                f"""UPDATE {table} SET status='pending', processed_by=NULL, processed_at=NULL
                    WHERE id=? AND status='processing' AND processed_by=?""",
                (int(operation_id), int(claimed_by)),
            )
        db().execute("DELETE FROM admin_operation_claims WHERE expires_at<=?", (now_text,))
        db().commit()

    @app.get("/api/admin/dashboard")
    def admin_dashboard():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_view_stats"):
            return forbidden()
        with db_lock:
            def count(sql, args=()):
                row = db().execute(sql, args).fetchone()
                return int(row[0] or 0) if row else 0
            try:
                payload = {
                    "users": count("SELECT COUNT(*) FROM users WHERE COALESCE(deleted,0)=0"),
                    "pending_charges": count("SELECT COUNT(*) FROM pending_charges WHERE status IN ('pending','processing')"),
                    "pending_withdraws": count("SELECT COUNT(*) FROM pending_withdraws WHERE status IN ('pending','processing')"),
                    "moderators": count("SELECT COUNT(*) FROM moderators"),
                    "open_tickets": count("SELECT COUNT(*) FROM tickets WHERE status='open'"),
                    "operation_mode": str(app.config.get("MATAR_OPERATION_MODE", "demo")),
                }
            except Exception:
                app.logger.exception("Dashboard query failed")
                return jsonify({"ok": False, "error": "dashboard_unavailable"}), 503
        return jsonify({"ok": True, "stats": payload}), 200

    @app.get("/api/admin/operations")
    def admin_operations():
        user = current()
        if not user:
            return denied()
        if not (allowed(user, "can_handle_charges") or allowed(user, "can_handle_withdraws")):
            return forbidden()
        items = []
        with db_lock:
            try:
                ensure_claims_table()
                if allowed(user, "can_handle_charges"):
                    rows = db().execute(
                        """SELECT id,user_id,amount,method,status,created_at,receipt_number
                           FROM pending_charges WHERE status IN ('pending','processing')
                           ORDER BY created_at ASC LIMIT 100"""
                    ).fetchall()
                    for row in rows:
                        items.append({"id": int(row[0]), "type": "charge", "user_id": row[1],
                                      "amount": float(row[2] or 0), "method": row[3] or "",
                                      "status": row[4] or "pending", "created_at": row[5] or "",
                                      "reference": row[6] or ""})
                if allowed(user, "can_handle_withdraws"):
                    rows = db().execute(
                        """SELECT id,user_id,amount,net_amount,method,status,created_at,account
                           FROM pending_withdraws WHERE status IN ('pending','processing')
                           ORDER BY created_at ASC LIMIT 100"""
                    ).fetchall()
                    for row in rows:
                        items.append({"id": int(row[0]), "type": "withdraw", "user_id": row[1],
                                      "amount": float(row[2] or 0), "net_amount": float(row[3] or 0),
                                      "method": row[4] or "", "status": row[5] or "pending",
                                      "created_at": row[6] or "", "reference": row[7] or ""})
                for item in items:
                    claim = db().execute(
                        """SELECT claimed_by,claimed_at,expires_at FROM admin_operation_claims
                           WHERE operation_type=? AND operation_id=? AND expires_at>?""",
                        (item["type"], item["id"], _iso()),
                    ).fetchone()
                    item["claim"] = ({"claimed_by": int(claim[0]), "claimed_at": claim[1],
                                      "expires_at": claim[2]} if claim else None)
            except Exception:
                app.logger.exception("Admin operations list failed")
                return jsonify({"ok": False, "error": "operations_unavailable"}), 503
        items.sort(key=lambda x: (x.get("created_at") or "", x["id"]))
        return jsonify({"ok": True, "items": items}), 200

    @app.post("/api/admin/operations/<operation_type>/<int:operation_id>/claim")
    def claim_operation(operation_type, operation_id):
        user = current()
        if not user:
            return denied()
        if operation_type not in ("charge", "withdraw"):
            return jsonify({"ok": False, "error": "operation_not_found"}), 404
        if not allowed(user, permission_for_type(operation_type)):
            return forbidden()
        now = _now()
        expiry = _iso(now + timedelta(minutes=10))
        now_text = _iso(now)
        table = "pending_charges" if operation_type == "charge" else "pending_withdraws"
        with db_lock:
            try:
                ensure_claims_table()
                db().execute("BEGIN")
                row = db().execute(
                    f"SELECT status,processed_by FROM {table} WHERE id=?", (operation_id,)
                ).fetchone()
                if not row:
                    db().rollback()
                    return jsonify({"ok": False, "error": "operation_not_found"}), 404
                if row[0] not in ("pending", "processing"):
                    db().rollback()
                    return jsonify({"ok": False, "error": "operation_not_open"}), 409
                existing = db().execute(
                    """SELECT claimed_by,expires_at FROM admin_operation_claims
                       WHERE operation_type=? AND operation_id=?""",
                    (operation_type, operation_id),
                ).fetchone()
                uid = int(user["telegram_id"])
                if existing and str(existing[1]) > now_text and int(existing[0]) != uid:
                    db().rollback()
                    return jsonify({"ok": False, "error": "already_claimed"}), 409
                processed_by = row[1]
                if row[0] == "processing" and processed_by not in (None, uid):
                    db().rollback()
                    return jsonify({"ok": False, "error": "already_claimed"}), 409
                updated = db().execute(
                    f"""UPDATE {table} SET status='processing',processed_by=?
                        WHERE id=? AND status IN ('pending','processing')""",
                    (uid, operation_id),
                )
                if updated.rowcount != 1:
                    db().rollback()
                    return jsonify({"ok": False, "error": "already_claimed"}), 409
                if existing:
                    db().execute(
                        """UPDATE admin_operation_claims SET claimed_by=?,claimed_at=?,expires_at=?
                           WHERE operation_type=? AND operation_id=?""",
                        (uid, now_text, expiry, operation_type, operation_id),
                    )
                else:
                    db().execute(
                        """INSERT INTO admin_operation_claims
                           (operation_type,operation_id,claimed_by,claimed_at,expires_at)
                           VALUES (?,?,?,?,?)""",
                        (operation_type, operation_id, uid, now_text, expiry),
                    )
                db().commit()
                audit(user, "استلام طلب", f"{operation_type}:{operation_id} لمدة 10 دقائق")
            except Exception:
                db().rollback()
                app.logger.exception("Claim operation failed")
                return jsonify({"ok": False, "error": "claim_unavailable"}), 503
        return jsonify({"ok": True, "claimed_by": int(user["telegram_id"]),
                        "expires_at": expiry, "message": "تم استلام الطلب لمدة 10 دقائق."}), 200

    @app.post("/api/admin/operations/<operation_type>/<int:operation_id>/release")
    def release_operation(operation_type, operation_id):
        user = current()
        if not user:
            return denied()
        if operation_type not in ("charge", "withdraw"):
            return jsonify({"ok": False, "error": "operation_not_found"}), 404
        if not allowed(user, permission_for_type(operation_type)):
            return forbidden()
        with db_lock:
            row = db().execute(
                """SELECT claimed_by FROM admin_operation_claims
                   WHERE operation_type=? AND operation_id=?""",
                (operation_type, operation_id),
            ).fetchone()
            if not row:
                return jsonify({"ok": True, "message": "الطلب غير مستلم حالياً."}), 200
            claimed_by = int(row[0])
            if claimed_by != int(user["telegram_id"]) and user.get("role") != "owner":
                return forbidden()
            table = "pending_charges" if operation_type == "charge" else "pending_withdraws"
            db().execute(
                f"""UPDATE {table} SET status='pending',processed_by=NULL,processed_at=NULL
                    WHERE id=? AND status='processing' AND processed_by=?""",
                (operation_id, claimed_by),
            )
            db().execute(
                "DELETE FROM admin_operation_claims WHERE operation_type=? AND operation_id=?",
                (operation_type, operation_id),
            )
            db().commit()
            audit(user, "تحرير طلب", f"{operation_type}:{operation_id}")
        return jsonify({"ok": True, "message": "تم تحرير الطلب."}), 200

    @app.post("/api/admin/operations/<operation_type>/<int:operation_id>/complete")
    def complete_operation(operation_type, operation_id):
        user = current()
        if not user:
            return denied()
        if operation_type not in ("charge", "withdraw"):
            return jsonify({"ok": False, "error": "operation_not_found"}), 404
        if not allowed(user, permission_for_type(operation_type)):
            return forbidden()
        # Deliberately fail closed until the owner explicitly approves and tests
        # the existing atomic financial handlers. Never mutate balances here.
        audit(user, "financial_completion_blocked",
              f"{operation_type}:{operation_id}; no balance changes")
        return jsonify({
            "ok": False, "error": "financial_execution_disabled",
            "message": "التنفيذ المالي الحقيقي مقفول؛ لم تتغير الأرصدة ولم يتم تأكيد العملية."
        }), 423

    @app.post("/api/admin/operations/<operation_type>/<int:operation_id>/cancel")
    def cancel_operation(operation_type, operation_id):
        user = current()
        if not user:
            return denied()
        if operation_type not in ("charge", "withdraw"):
            return jsonify({"ok": False, "error": "operation_not_found"}), 404
        if not allowed(user, permission_for_type(operation_type)):
            return forbidden()
        # Cancellation can affect reserved funds, so it remains disabled until
        # the bot's existing atomic cancellation logic is integrated and tested.
        audit(user, "financial_cancellation_blocked",
              f"{operation_type}:{operation_id}; no balance changes")
        return jsonify({
            "ok": False, "error": "financial_execution_disabled",
            "message": "الإلغاء المالي الحقيقي مقفول؛ لم تتغير الأرصدة ولم يتم تأكيد الإلغاء."
        }), 423

    @app.get("/api/admin/notifications")
    def get_notifications():
        user = current()
        if not user:
            return denied()
        with db_lock:
            row = db().execute(
                "SELECT preferences FROM admin_app_preferences WHERE user_id=?",
                (int(user["telegram_id"]),),
            ).fetchone()
        defaults = {key: key not in ("referrals", "ai_decisions") for key in sorted(PREFERENCE_KEYS)}
        if row:
            try:
                stored = json.loads(row[0] or "{}")
                defaults.update({key: bool(value) for key, value in stored.items() if key in PREFERENCE_KEYS})
            except Exception:
                app.logger.exception("Invalid admin app preferences")
        return jsonify({"ok": True, "preferences": defaults}), 200

    @app.put("/api/admin/notifications")
    def put_notifications():
        user = current()
        if not user:
            return denied()
        payload = request.get_json(silent=True) or {}
        prefs = payload.get("preferences")
        if not isinstance(prefs, dict) or any(k not in PREFERENCE_KEYS or not isinstance(v, bool) for k, v in prefs.items()):
            return jsonify({"ok": False, "error": "invalid_preferences"}), 400
        with db_lock:
            db().execute(
                """INSERT INTO admin_app_preferences(user_id,preferences,updated_at)
                   VALUES (?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET preferences=excluded.preferences,updated_at=excluded.updated_at""",
                (int(user["telegram_id"]), json.dumps(prefs, ensure_ascii=False), _iso()),
            )
            db().commit()
            audit(user, "تحديث تفضيلات الإدارة", "تحديث تفضيلات إشعارات التطبيق")
        return jsonify({"ok": True}), 200

    @app.get("/api/admin/moderators")
    def get_moderators():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_moderators"):
            return forbidden()
        with db_lock:
            rows = db().execute(
                """SELECT user_id,custom_name,added_by,added_at,can_reply_tickets,can_handle_charges,
                          can_handle_withdraws,can_send_broadcast,can_manage_users,can_charge_withdraw_users,
                          can_view_stats,can_manage_buttons,can_access_full_admin,can_manage_moderators,can_use_ai
                   FROM moderators ORDER BY added_at DESC"""
            ).fetchall()
        items = []
        for row in rows:
            items.append({
                "user_id": int(row[0]), "custom_name": row[1] or "",
                "added_by": row[2], "added_at": row[3] or "",
                "permissions": {key: bool(row[index]) for key, index in {
                    "can_reply_tickets": 4, "can_handle_charges": 5, "can_handle_withdraws": 6,
                    "can_send_broadcast": 7, "can_manage_users": 8, "can_charge_withdraw_users": 9,
                    "can_view_stats": 10, "can_manage_buttons": 11, "can_access_full_admin": 12,
                    "can_manage_moderators": 13, "can_use_ai": 14,
                }.items()}
            })
        return jsonify({"ok": True, "items": items}), 200

    @app.post("/api/admin/moderators")
    def add_moderator():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_moderators"):
            return forbidden()
        payload = request.get_json(silent=True) or {}
        try:
            target = int(payload.get("user_id"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_user_id"}), 400
        if target <= 0 or target == int(owner_id):
            return jsonify({"ok": False, "error": "invalid_user_id"}), 400
        name = str(payload.get("custom_name", "")).strip()[:80]
        permissions = payload.get("permissions") or {}
        if not isinstance(permissions, dict) or any(k not in PERMISSION_COLUMNS or not isinstance(v, bool) for k, v in permissions.items()):
            return jsonify({"ok": False, "error": "invalid_permissions"}), 400
        privileged_permissions = {"can_manage_moderators", "can_access_full_admin", "can_send_broadcast", "can_manage_users"}
        if user.get("role") != "owner" and any(permissions.get(key) is True for key in privileged_permissions):
            return jsonify({"ok": False, "error": "owner_required_for_privileged_permissions"}), 403
        fields = sorted(PERMISSION_COLUMNS)
        columns = ["user_id", "custom_name", "added_by", "added_at"] + fields
        values = [target, name, int(user["telegram_id"]), _now().strftime("%Y-%m-%d %H:%M:%S")]
        values.extend(1 if permissions.get(field, False) else 0 for field in fields)
        placeholders = ",".join("?" for _ in columns)
        with db_lock:
            exists = db().execute("SELECT 1 FROM moderators WHERE user_id=?", (target,)).fetchone()
            if exists:
                return jsonify({"ok": False, "error": "moderator_exists"}), 409
            db().execute(f"INSERT INTO moderators ({','.join(columns)}) VALUES ({placeholders})", tuple(values))
            db().commit()
            audit(user, "إضافة مشرف", f"إضافة المشرف {target}", target_user=target)
        return jsonify({"ok": True}), 201

    @app.put("/api/admin/moderators/<int:target_id>")
    def update_moderator(target_id):
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_moderators"):
            return forbidden()
        payload = request.get_json(silent=True) or {}
        updates, values = [], []
        if "custom_name" in payload:
            updates.append("custom_name=?")
            values.append(str(payload["custom_name"]).strip()[:80])
        permissions = payload.get("permissions")
        if permissions is not None:
            if not isinstance(permissions, dict) or any(k not in PERMISSION_COLUMNS or not isinstance(v, bool) for k, v in permissions.items()):
                return jsonify({"ok": False, "error": "invalid_permissions"}), 400
            privileged_permissions = {"can_manage_moderators", "can_access_full_admin", "can_send_broadcast", "can_manage_users"}
            if user.get("role") != "owner" and any(permissions.get(key) is True for key in privileged_permissions):
                return jsonify({"ok": False, "error": "owner_required_for_privileged_permissions"}), 403
            for field, enabled in permissions.items():
                updates.append(f"{field}=?")
                values.append(1 if enabled else 0)
        if not updates:
            return jsonify({"ok": False, "error": "nothing_to_update"}), 400
        values.append(target_id)
        with db_lock:
            cur = db().execute(f"UPDATE moderators SET {','.join(updates)} WHERE user_id=?", tuple(values))
            db().commit()
            if cur.rowcount != 1:
                return jsonify({"ok": False, "error": "moderator_not_found"}), 404
            audit(user, "تعديل صلاحيات مشرف", f"تعديل المشرف {target_id}", target_user=target_id)
        return jsonify({"ok": True}), 200

    @app.delete("/api/admin/moderators/<int:target_id>")
    def delete_moderator(target_id):
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_moderators"):
            return forbidden()
        if target_id == int(owner_id) or (target_id == int(user["telegram_id"]) and user.get("role") != "owner"):
            return jsonify({"ok": False, "error": "protected_moderator"}), 403
        with db_lock:
            cur = db().execute("DELETE FROM moderators WHERE user_id=?", (target_id,))
            db().commit()
            if cur.rowcount != 1:
                return jsonify({"ok": False, "error": "moderator_not_found"}), 404
            audit(user, "حذف مشرف", f"حذف المشرف {target_id}", target_user=target_id)
        return jsonify({"ok": True}), 200

    @app.get("/api/admin/buttons")
    def get_buttons():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        with db_lock:
            rows = db().execute(
                """SELECT id,button_name,button_text,parent_button,button_type,action,message_text,
                          level,sort_order,is_active,requires_subscription,requires_admin,
                          requires_moderator,path
                   FROM dynamic_buttons ORDER BY level,sort_order,id LIMIT 500"""
            ).fetchall()
        keys = ("id","button_name","button_text","parent_button","button_type","action","message_text",
                "level","sort_order","is_active","requires_subscription","requires_admin","requires_moderator","path")
        return jsonify({"ok": True, "items": [dict(zip(keys, row)) for row in rows]}), 200

    @app.put("/api/admin/buttons/<int:button_id>")
    def update_button(button_id):
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        payload = request.get_json(silent=True) or {}
        updates, values = [], []
        for field, value in payload.items():
            if field not in BUTTON_FIELDS:
                return jsonify({"ok": False, "error": "invalid_field"}), 400
            if field in ("is_active","requires_subscription","requires_admin","requires_moderator"):
                if not isinstance(value, bool):
                    return jsonify({"ok": False, "error": "invalid_value"}), 400
                value = 1 if value else 0
            elif field in ("sort_order",):
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    return jsonify({"ok": False, "error": "invalid_value"}), 400
            else:
                value = str(value)[:4000]
            updates.append(f"{field}=?")
            values.append(value)
        if not updates:
            return jsonify({"ok": False, "error": "nothing_to_update"}), 400
        updates.append("updated_at=?")
        values.append(_now().strftime("%Y-%m-%d %H:%M:%S"))
        values.append(button_id)
        with db_lock:
            cur = db().execute(f"UPDATE dynamic_buttons SET {','.join(updates)} WHERE id=?", tuple(values))
            db().commit()
            if cur.rowcount != 1:
                return jsonify({"ok": False, "error": "button_not_found"}), 404
            audit(user, "تعديل زر", f"تعديل الزر رقم {button_id}")
        return jsonify({"ok": True}), 200

    @app.get("/api/admin/audit")
    def get_audit():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_view_stats"):
            return forbidden()
        with db_lock:
            rows = db().execute(
                """SELECT id,admin_id,display_name,action_type,details,target_user,amount,created_at
                   FROM admin_logs ORDER BY id DESC LIMIT 100"""
            ).fetchall()
        keys = ("id","admin_id","display_name","action_type","details","target_user","amount","created_at")
        return jsonify({"ok": True, "items": [dict(zip(keys, row)) for row in rows]}), 200

    @app.post("/api/admin/messages/broadcast")
    def broadcast_message():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_send_broadcast"):
            return forbidden()
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        audience = str(payload.get("audience", "all")).strip()
        if not message or len(message) > 4000 or audience not in ("all", "moderators"):
            return jsonify({"ok": False, "error": "invalid_message"}), 400
        if audience == "all":
            rows = db().execute("SELECT user_id FROM users WHERE COALESCE(deleted,0)=0 AND COALESCE(status,'active')='active' ORDER BY user_id LIMIT 5000").fetchall()
            ids = [int(row[0]) for row in rows]
        else:
            rows = db().execute("SELECT user_id FROM moderators ORDER BY user_id").fetchall()
            ids = [int(row[0]) for row in rows]
            if int(owner_id) not in ids:
                ids.append(int(owner_id))
        sent, failed = 0, 0
        # This endpoint is only called after the UI's explicit send action.
        for target in ids:
            try:
                bot.send_message(target, message)
                sent += 1
            except Exception:
                failed += 1
        audit(user, "إرسال رسالة جماعية", f"الجمهور={audience}؛ نجح={sent}؛ فشل={failed}")
        return jsonify({"ok": True, "sent": sent, "failed": failed}), 200

    @app.get("/api/admin/referrals")
    def get_referrals():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_view_stats"):
            return forbidden()
        with db_lock:
            try:
                def setting(key, default=""):
                    row = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
                    return str(row[0]) if row and row[0] is not None else default
                total_refs_row = db().execute("SELECT COUNT(*) FROM referrals_log").fetchone()
                total_refs = int(total_refs_row[0] or 0) if total_refs_row else 0
                earnings_rows = db().execute(
                    """SELECT referrer_id,
                              SUM(CASE WHEN theoretical_amount>COALESCE(paid_amount,0)
                                       THEN theoretical_amount-COALESCE(paid_amount,0) ELSE 0 END),
                              SUM(COALESCE(theoretical_amount,0)), SUM(COALESCE(paid_amount,0))
                       FROM referral_earnings GROUP BY referrer_id"""
                ).fetchall()
                earnings = {int(row[0]): {
                    "unpaid_amount": float(row[1] or 0),
                    "theoretical_amount": float(row[2] or 0),
                    "paid_amount": float(row[3] or 0)
                } for row in earnings_rows if row[0] is not None}
                ref_rows = db().execute(
                    """SELECT referrer_id,COUNT(*) FROM referrals_log
                       GROUP BY referrer_id ORDER BY COUNT(*) DESC LIMIT 100"""
                ).fetchall()
                items = []
                for row in ref_rows:
                    uid = int(row[0])
                    amounts = earnings.get(uid, {})
                    items.append({"user_id": uid, "referrals": int(row[1] or 0),
                        "unpaid_amount": amounts.get("unpaid_amount", 0.0),
                        "theoretical_amount": amounts.get("theoretical_amount", 0.0),
                        "paid_amount": amounts.get("paid_amount", 0.0)})
                cashier_row = db().execute("SELECT balance FROM cashier_balance WHERE admin_id=?", (int(owner_id),)).fetchone()
                active_cycle = db().execute(
                    "SELECT start_date,end_date,status,total_theoretical,total_paid FROM referral_cycles WHERE status='active' ORDER BY id DESC LIMIT 1"
                ).fetchone()
                payload = {
                    "total_referrals": total_refs,
                    "referral_percentage": float(setting("referral_percentage", "10") or 10),
                    "next_payout": setting("next_referral_payout", ""),
                    "cycle_days": int(float(setting("referral_cycle_days", "10") or 10)),
                    "cashier_balance": float(cashier_row[0] or 0) if cashier_row else 0.0,
                    "unpaid_total": sum(x.get("unpaid_amount", 0.0) for x in earnings.values()),
                    "active_cycle": ({"start_date": active_cycle[0], "end_date": active_cycle[1],
                        "status": active_cycle[2], "theoretical": float(active_cycle[3] or 0),
                        "paid": float(active_cycle[4] or 0)} if active_cycle else None),
                    "items": items
                }
            except Exception:
                app.logger.exception("Referral dashboard query failed")
                return jsonify({"ok": False, "error": "referrals_unavailable"}), 503
        return jsonify({"ok": True, "data": payload}), 200

    @app.put("/api/admin/referrals/settings")
    def update_referral_settings():
        user = current()
        if not user:
            return denied()
        if user.get("role") != "owner" and int(user.get("telegram_id", 0)) != int(owner_id):
            return forbidden()
        payload = request.get_json(silent=True) or {}
        try:
            percentage = float(payload.get("percentage"))
            cycle_days = int(payload.get("cycle_days"))
            payout_date = str(payload.get("next_payout", "")).strip()
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_settings"}), 400
        if not math.isfinite(percentage) or not 0 <= percentage <= 100 or not 1 <= cycle_days <= 60:
            return jsonify({"ok": False, "error": "invalid_settings"}), 400
        if payout_date:
            try:
                datetime.strptime(payout_date, "%Y-%m-%d")
            except ValueError:
                return jsonify({"ok": False, "error": "invalid_payout_date",
                                "message": "اكتب التاريخ بصيغة YYYY-MM-DD."}), 400
        now_text = _now().strftime("%Y-%m-%d %H:%M:%S")
        values = [
            ("referral_percentage", str(percentage), "نسبة الإحالات", "number"),
            ("referral_cycle_days", str(cycle_days), "عدد أيام دورة الإحالات", "number"),
            ("next_referral_payout", payout_date, "موعد الدفعة القادمة", "text"),
        ]
        with db_lock:
            for key, value, description, kind in values:
                db().execute(
                    """INSERT INTO settings(key,value,description,type,updated_at,updated_by)
                       VALUES(?,?,?,?,?,?)
                       ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                           description=excluded.description,type=excluded.type,
                           updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
                    (key, value, description, kind, now_text, int(user["telegram_id"])),
                )
            if payout_date:
                db().execute("UPDATE referral_cycles SET end_date=? WHERE status='active'", (payout_date,))
            db().commit()
            audit(user, "تعديل إعدادات الإحالات",
                  f"النسبة={percentage:g}%؛ الدورة={cycle_days} يوم؛ موعد الدفعة={payout_date or 'غير محدد'}")
        return jsonify({"ok": True, "message": "تم حفظ إعدادات الإحالات."}), 200

    @app.post("/api/admin/referrals/payout")
    def pay_referral_earnings():
        user = current()
        if not user:
            return denied()
        if user.get("role") != "owner" and int(user.get("telegram_id", 0)) != int(owner_id):
            return forbidden()
        audit(user, "referral_payout_blocked",
              "رفض الصرف من التطبيق قبل اعتماد معالج مالي ذري")
        return jsonify({
            "ok": False, "error": "financial_execution_disabled",
            "message": "صرف أرباح الإحالة الحقيقي مقفول؛ لم تتغير الأرصدة."
        }), 423

    CONTENT_TEXT_FIELDS = {
        "welcome_message": 4000, "subscription_message": 4000,
        "terms_message": 4000, "maintenance_message": 4000,
        "required_channel": 100,
    }

    @app.get("/api/admin/content")
    def get_admin_content():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        with db_lock:
            try:
                content = {}
                defaults = {
                    "welcome_message": "أهلاً وسهلاً بك في بوت مطر",
                    "subscription_message": "الاشتراك بالقناة إلزامي لاستخدام البوت.",
                    "terms_message": "",
                    "maintenance_message": "البوت في حالة صيانة حالياً.",
                    "required_channel": os.environ.get("CHANNEL_ID", "@Matar_ichancy"),
                    "force_subscription": "1",
                }
                for key, default in defaults.items():
                    row = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
                    value = str(row[0]) if row and row[0] is not None else str(default)
                    content[key] = value == "1" if key == "force_subscription" else value
            except Exception:
                app.logger.exception("Admin content settings query failed")
                return jsonify({"ok": False, "error": "content_unavailable"}), 503
        return jsonify({"ok": True, "content": content}), 200

    @app.put("/api/admin/content")
    def update_admin_content():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        payload = request.get_json(silent=True) or {}
        if not payload or any(key not in set(CONTENT_TEXT_FIELDS) | {"force_subscription"} for key in payload):
            return jsonify({"ok": False, "error": "invalid_content_field"}), 400
        values = {}
        for key, value in payload.items():
            if key == "force_subscription":
                if not isinstance(value, bool):
                    return jsonify({"ok": False, "error": "invalid_value"}), 400
                values[key] = "1" if value else "0"
            else:
                if not isinstance(value, str) or len(value) > CONTENT_TEXT_FIELDS[key]:
                    return jsonify({"ok": False, "error": "invalid_value"}), 400
                value = value.strip()
                if key == "required_channel" and value:
                    valid_username = value.startswith("@") and 6 <= len(value) <= 33 and value[1:].isascii() and value[1:].replace("_", "").isalnum()
                    valid_private_id = value.startswith("-100") and value[4:].isdigit()
                    if not (valid_username or valid_private_id):
                        return jsonify({"ok": False, "error": "invalid_channel",
                                        "message": "اكتب معرف القناة مثل @MyChannel أو رقم القناة الخاص الذي يبدأ بـ -100."}), 400
                values[key] = value
        now_text = _now().strftime("%Y-%m-%d %H:%M:%S")
        with db_lock:
            try:
                for key, value in values.items():
                    kind = "boolean" if key == "force_subscription" else "text"
                    description = {
                        "welcome_message": "رسالة الترحيب", "subscription_message": "رسالة الاشتراك الإلزامي",
                        "terms_message": "نص الشروط", "maintenance_message": "رسالة الصيانة",
                        "required_channel": "معرف قناة الاشتراك الإجباري",
                        "force_subscription": "تفعيل الاشتراك الإجباري لكل المستخدمين",
                    }[key]
                    db().execute(
                        """INSERT INTO settings(key,value,description,type,updated_at,updated_by)
                           VALUES(?,?,?,?,?,?)
                           ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                               description=excluded.description,type=excluded.type,
                               updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
                        (key, value, description, kind, now_text, int(user["telegram_id"])),
                    )
                db().commit()
                audit(user, "تعديل محتوى البوت", "تحديث إعدادات الترحيب والاشتراك والشروط والصيانة")
            except Exception:
                db().rollback()
                app.logger.exception("Admin content settings update failed")
                return jsonify({"ok": False, "error": "content_save_failed"}), 503
        return jsonify({"ok": True, "message": "تم حفظ إعدادات محتوى البوت."}), 200

    return True
