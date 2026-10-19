"""Authenticated admin API for Matar Admin.

All authority is derived from the Telegram-authenticated server session.
Financial requests are never marked completed by this module.
"""
from __future__ import annotations

import json
import math
import os
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
    cancel_charge=None, cancel_withdraw=None, get_conn=None,
    adjust_balance=None, assistant_ask=None
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
    conn.execute("""CREATE TABLE IF NOT EXISTS admin_balance_idempotency (
        actor_id BIGINT NOT NULL,
        idempotency_key TEXT NOT NULL,
        action TEXT NOT NULL,
        target_user BIGINT NOT NULL,
        amount REAL NOT NULL,
        new_balance REAL,
        receipt TEXT,
        created_at TEXT NOT NULL,
        PRIMARY KEY (actor_id, idempotency_key)
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
            active.execute("""CREATE TABLE IF NOT EXISTS admin_balance_idempotency (
                actor_id BIGINT NOT NULL,
                idempotency_key TEXT NOT NULL,
                action TEXT NOT NULL,
                target_user BIGINT NOT NULL,
                amount REAL NOT NULL,
                new_balance REAL,
                receipt TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (actor_id, idempotency_key)
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

    def operation_mode_value():
        try:
            if callable(get_operation_mode):
                return str(get_operation_mode())
        except Exception:
            app.logger.exception("Could not read operation mode")
        return str(app.config.get("MATAR_OPERATION_MODE", "demo"))

    def financial_actions_enabled():
        # Require both an explicit server-side opt-in and the bot's real mode.
        # Never trust a client/UI toggle to authorize changes to balances.
        enabled = os.environ.get("MATAR_ADMIN_FINANCIAL_ACTIONS_ENABLED", "0").strip().lower() in {
            "1", "true", "yes", "on"
        }
        return enabled and operation_mode_value().strip().lower() == "real"

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

    @app.get("/api/admin/my-permissions")
    def admin_my_permissions():
        user = current()
        if not user:
            return denied()
        keys = (
            "can_reply_tickets", "can_handle_charges", "can_handle_withdraws",
            "can_send_broadcast", "can_manage_users", "can_charge_withdraw_users",
            "can_view_stats", "can_manage_buttons", "can_access_full_admin",
            "can_manage_moderators", "can_use_ai",
        )
        user_id = int(user["telegram_id"])
        permissions = {
            key: bool(user.get("role") == "owner" or check_permission(user_id, key))
            for key in keys
        }
        return jsonify({"ok": True, "permissions": permissions}), 200

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
                    "operation_mode": operation_mode_value(),
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
        if not financial_actions_enabled():
            audit(user, "financial_completion_blocked", f"{operation_type}:{operation_id}; explicit real-mode opt-in missing")
            return jsonify({"ok": False, "error": "financial_execution_disabled",
                            "message": "التنفيذ المالي من التطبيق مقفول افتراضياً؛ لم تتغير الأرصدة."}), 423
        handler = complete_charge if operation_type == "charge" else complete_withdraw
        if not callable(handler):
            audit(user, "financial_completion_blocked", f"{operation_type}:{operation_id}; handler unavailable")
            return jsonify({"ok": False, "error": "financial_execution_disabled",
                            "message": "معالج العملية غير متاح؛ لم تتغير الأرصدة ولم يتم تأكيد العملية."}), 423
        body = request.get_json(silent=True) or {}
        amount = body.get("amount") if operation_type == "charge" else None
        actor_id = int(user["telegram_id"])
        try:
            result = handler(operation_id, actor_id, amount) if operation_type == "charge" else handler(operation_id, actor_id)
        except Exception:
            app.logger.exception("Atomic financial completion failed")
            audit(user, "financial_completion_failed", f"{operation_type}:{operation_id}")
            return jsonify({"ok": False, "error": "financial_execution_failed", "message": "فشل التنفيذ الذري؛ لم يتم تأكيد النجاح."}), 409
        new_value, status = result if isinstance(result, tuple) and len(result) == 2 else (None, "unknown")
        if status != "ok":
            audit(user, "financial_completion_rejected", f"{operation_type}:{operation_id}:{status}")
            return jsonify({"ok": False, "error": status, "message": "لم يتم تنفيذ العملية ولم يتغير الرصيد."}), 409
        audit(user, "financial_completion", f"{operation_type}:{operation_id}; confirmed_by_server", amount=amount)
        return jsonify({"ok": True, "type": operation_type, "id": operation_id, "new_balance": new_value,
                        "operation_mode": operation_mode_value()}), 200

    @app.post("/api/admin/operations/<operation_type>/<int:operation_id>/cancel")
    def cancel_operation(operation_type, operation_id):
        user = current()
        if not user:
            return denied()
        if operation_type not in ("charge", "withdraw"):
            return jsonify({"ok": False, "error": "operation_not_found"}), 404
        if not allowed(user, permission_for_type(operation_type)):
            return forbidden()
        if not financial_actions_enabled():
            audit(user, "financial_cancellation_blocked", f"{operation_type}:{operation_id}; explicit real-mode opt-in missing")
            return jsonify({"ok": False, "error": "financial_execution_disabled",
                            "message": "الإلغاء المالي من التطبيق مقفول افتراضياً؛ لم تتغير الأرصدة."}), 423
        handler = cancel_charge if operation_type == "charge" else cancel_withdraw
        if not callable(handler):
            audit(user, "financial_cancellation_blocked", f"{operation_type}:{operation_id}; handler unavailable")
            return jsonify({"ok": False, "error": "financial_execution_disabled",
                            "message": "معالج الإلغاء غير متاح؛ لم تتغير الأرصدة."}), 423
        body = request.get_json(silent=True) or {}
        reason = str(body.get("reason", "")).strip()[:1000]
        if not reason:
            return jsonify({"ok": False, "error": "reason_required"}), 400
        actor_id = int(user["telegram_id"])
        try:
            result = handler(operation_id, actor_id, reason)
        except Exception:
            app.logger.exception("Atomic financial cancellation failed")
            audit(user, "financial_cancellation_failed", f"{operation_type}:{operation_id}")
            return jsonify({"ok": False, "error": "financial_cancellation_failed", "message": "فشل الإلغاء الذري."}), 409
        _payload, status = result if isinstance(result, tuple) and len(result) == 2 else (None, "unknown")
        if status != "ok":
            audit(user, "financial_cancellation_rejected", f"{operation_type}:{operation_id}:{status}")
            return jsonify({"ok": False, "error": status, "message": "لم يتم إلغاء العملية ولم تتغير الأرصدة."}), 409
        audit(user, "financial_cancellation", f"{operation_type}:{operation_id}; {reason}")
        return jsonify({"ok": True, "type": operation_type, "id": operation_id, "status": "cancelled"}), 200

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

    @app.get("/api/admin/users")
    def list_users():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_users"):
            return forbidden()
        search = str(request.args.get("search", "")).strip()[:120]
        try:
            limit = max(1, min(int(request.args.get("limit", 50)), 100))
            offset = max(0, int(request.args.get("offset", 0)))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_pagination"}), 400
        where = "WHERE COALESCE(deleted,0)=0"
        params = []
        if search:
            where += " AND (CAST(user_id AS TEXT)=? OR username LIKE ? OR acc_name LIKE ? OR first_name LIKE ? OR custom_name LIKE ?)"
            params.extend([search, f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
        with db_lock:
            try:
                total = int(db().execute(f"SELECT COUNT(*) FROM users {where}", params).fetchone()[0] or 0)
                rows = db().execute(
                    f"""SELECT user_id,first_name,username,custom_name,acc_name,status,created_at,
                               balance,site_balance,referral_count,last_active
                        FROM users {where} ORDER BY user_id DESC LIMIT ? OFFSET ?""",
                    params + [limit, offset],
                ).fetchall()
            except Exception:
                app.logger.exception("User list query failed")
                return jsonify({"ok": False, "error": "users_unavailable"}), 503
        items = [{"user_id": int(r[0]), "first_name": r[1] or "", "username": r[2] or "",
                  "custom_name": r[3] or "", "account_name": r[4] or "", "status": r[5] or "active",
                  "created_at": r[6] or "", "balance": float(r[7] or 0), "site_balance": float(r[8] or 0),
                  "referral_count": int(r[9] or 0), "last_active": r[10] or ""} for r in rows]
        return jsonify({"ok": True, "items": items, "total": total, "limit": limit, "offset": offset}), 200

    @app.get("/api/admin/users/<int:target_id>")
    def user_detail(target_id):
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_users"):
            return forbidden()
        with db_lock:
            row = db().execute(
                """SELECT user_id,first_name,username,custom_name,acc_name,status,created_at,balance,
                           site_balance,ref_code,referred_by,referral_count,current_earnings,total_earnings,last_active,deleted
                    FROM users WHERE user_id=?""", (target_id,)
            ).fetchone()
            if not row:
                return jsonify({"ok": False, "error": "user_not_found"}), 404
            txs = db().execute(
                """SELECT id,type,amount,commission,net_amount,method,status,transaction_date,details,receipt_number
                   FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 50""", (target_id,)
            ).fetchall()
        profile = {"user_id": int(row[0]), "first_name": row[1] or "", "username": row[2] or "",
                   "custom_name": row[3] or "", "account_name": row[4] or "", "status": row[5] or "active",
                   "created_at": row[6] or "", "balance": float(row[7] or 0), "site_balance": float(row[8] or 0),
                   "referral_code": row[9] or "", "referred_by": row[10], "referral_count": int(row[11] or 0),
                   "current_earnings": float(row[12] or 0), "total_earnings": float(row[13] or 0),
                   "last_active": row[14] or "", "deleted": bool(row[15]), "has_ichancy_account": bool(row[4])}
        history = [{"id": int(r[0]), "type": r[1] or "", "amount": float(r[2] or 0),
                    "commission": float(r[3] or 0), "net_amount": float(r[4] or 0), "method": r[5] or "",
                    "status": r[6] or "", "date": r[7] or "", "details": r[8] or "", "receipt": r[9] or ""}
                   for r in txs]
        return jsonify({"ok": True, "user": profile, "transactions": history}), 200

    @app.put("/api/admin/users/<int:target_id>/status")
    def update_user_status(target_id):
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_users"):
            return forbidden()
        status = str((request.get_json(silent=True) or {}).get("status", "")).strip().lower()
        if status not in {"active", "banned"}:
            return jsonify({"ok": False, "error": "invalid_status"}), 400
        with db_lock:
            changed = db().execute("UPDATE users SET status=? WHERE user_id=? AND COALESCE(deleted,0)=0", (status, target_id))
            if changed.rowcount != 1:
                db().rollback()
                return jsonify({"ok": False, "error": "user_not_found"}), 404
            db().commit()
            audit(user, "تغيير حالة مستخدم", f"user={target_id}; status={status}", target_user=target_id)
        return jsonify({"ok": True, "user_id": target_id, "status": status}), 200

    @app.post("/api/admin/users/<int:target_id>/message")
    def message_user(target_id):
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_users"):
            return forbidden()
        text = str((request.get_json(silent=True) or {}).get("text", "")).strip()
        if not text or len(text) > 4000:
            return jsonify({"ok": False, "error": "invalid_message"}), 400
        with db_lock:
            exists = db().execute("SELECT 1 FROM users WHERE user_id=? AND COALESCE(deleted,0)=0", (target_id,)).fetchone()
        if not exists:
            return jsonify({"ok": False, "error": "user_not_found"}), 404
        try:
            sent = bot.send_message(target_id, text)
        except Exception:
            app.logger.exception("Direct admin message failed")
            return jsonify({"ok": False, "error": "delivery_failed"}), 502
        audit(user, "إرسال رسالة فردية", f"user={target_id}; message_id={getattr(sent, 'message_id', '')}", target_user=target_id)
        return jsonify({"ok": True, "delivered": True, "message_id": getattr(sent, "message_id", None)}), 200

    @app.post("/api/admin/users/<int:target_id>/balance")
    def adjust_user_balance(target_id):
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_charge_withdraw_users"):
            return forbidden()
        if not financial_actions_enabled():
            audit(user, "balance_adjustment_blocked", f"user={target_id}; explicit real-mode opt-in missing", target_user=target_id)
            return jsonify({"ok": False, "error": "financial_execution_disabled",
                            "message": "تعديل الأرصدة من التطبيق مقفول افتراضياً؛ لم يتغير أي رصيد."}), 423
        if not callable(adjust_balance):
            return jsonify({"ok": False, "error": "financial_handler_unavailable"}), 503
        payload = request.get_json(silent=True) or {}
        action = str(payload.get("action", "")).strip()
        key = str(payload.get("idempotency_key") or request.headers.get("Idempotency-Key", "")).strip()
        try:
            amount = float(payload.get("amount"))
            if not math.isfinite(amount) or amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_amount"}), 400
        if action not in {"bot_charge", "bot_withdraw", "site_charge", "site_withdraw"} or not (8 <= len(key) <= 128):
            return jsonify({"ok": False, "error": "invalid_action_or_idempotency_key"}), 400
        actor_id = int(user["telegram_id"])
        with db_lock:
            prior = db().execute(
                "SELECT action,target_user,amount,new_balance,receipt FROM admin_balance_idempotency WHERE actor_id=? AND idempotency_key=?",
                (actor_id, key),
            ).fetchone()
            if prior:
                if prior[0] != action or int(prior[1]) != target_id or float(prior[2]) != amount:
                    return jsonify({"ok": False, "error": "idempotency_key_reused"}), 409
                return jsonify({"ok": True, "replayed": True, "new_balance": prior[3], "receipt": prior[4]}), 200
            try:
                new_balance, receipt = adjust_balance(target_id, amount, action, actor_id)
                db().execute(
                    "INSERT INTO admin_balance_idempotency(actor_id,idempotency_key,action,target_user,amount,new_balance,receipt,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (actor_id, key, action, target_id, amount, new_balance, receipt, _iso()),
                )
                db().commit()
            except ValueError as exc:
                db().rollback()
                return jsonify({"ok": False, "error": "financial_rejected", "message": str(exc)}), 409
            except Exception:
                db().rollback()
                app.logger.exception("Admin balance adjustment failed")
                return jsonify({"ok": False, "error": "financial_failed"}), 409
            audit(user, "تعديل رصيد ذري من التطبيق", f"action={action}; key={key[:12]}", target_user=target_id, amount=amount)
        return jsonify({"ok": True, "replayed": False, "action": action, "user_id": target_id,
                        "new_balance": new_balance, "receipt": receipt}), 200

    EDITABLE_SETTINGS = {
        "syriatel_numbers": "text", "sham_address": "text", "syriatel_status": "status", "sham_status": "status",
        "usdt_status": "status", "binance_status": "status", "usdt_address": "text", "usdt_network": "text",
        "binance_address": "text", "binance_pay_id": "text", "min_charge": "number", "min_withdraw_syria": "number",
        "max_withdraw_syria": "number", "min_withdraw_sham": "number", "max_withdraw_sham": "number",
        "withdraw_commission": "number", "referral_percentage": "number", "bot_status": "status",
        "wheel_enabled": "boolean", "wheel_daily_charge_threshold": "number", "wheel_title": "text", "wheel_spin_message": "text",
    }

    @app.get("/api/admin/settings")
    def get_admin_settings():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        placeholders = ",".join("?" for _ in EDITABLE_SETTINGS)
        with db_lock:
            rows = db().execute(f"SELECT key,value,description,type,updated_at FROM settings WHERE key IN ({placeholders})", tuple(EDITABLE_SETTINGS)).fetchall()
        return jsonify({"ok": True, "settings": {str(r[0]): {"value": r[1] or "", "description": r[2] or "", "type": r[3] or "text", "updated_at": r[4] or ""} for r in rows}}), 200

    @app.put("/api/admin/settings")
    def update_admin_settings():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        payload = request.get_json(silent=True) or {}
        if not payload or any(key not in EDITABLE_SETTINGS for key in payload):
            return jsonify({"ok": False, "error": "invalid_setting"}), 400
        normalized = {}
        for key, value in payload.items():
            kind = EDITABLE_SETTINGS[key]
            if kind == "boolean":
                if not isinstance(value, bool):
                    return jsonify({"ok": False, "error": "invalid_value", "key": key}), 400
                normalized[key] = "1" if value else "0"
            elif kind == "number":
                try:
                    number = float(value)
                    if not math.isfinite(number) or number < 0 or number > 1_000_000_000:
                        raise ValueError
                    normalized[key] = str(int(number) if number.is_integer() else number)
                except (TypeError, ValueError):
                    return jsonify({"ok": False, "error": "invalid_value", "key": key}), 400
            else:
                text = str(value).strip()
                if len(text) > 4000 or (kind == "status" and text not in {"active", "متوقف", "stopped", "paused"}):
                    return jsonify({"ok": False, "error": "invalid_value", "key": key}), 400
                normalized[key] = text
        now = _now().strftime("%Y-%m-%d %H:%M:%S")
        with db_lock:
            for key, value in normalized.items():
                db().execute("UPDATE settings SET value=?,updated_at=?,updated_by=? WHERE key=?", (value, now, int(user["telegram_id"]), key))
            db().commit()
            audit(user, "تعديل إعدادات البوت", "keys=" + ",".join(sorted(normalized)))
        return jsonify({"ok": True, "updated": sorted(normalized)}), 200

    @app.get("/api/admin/services")
    def get_services():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        names = ("syriatel", "sham", "usdt", "binance")
        with db_lock:
            settings = {}
            for name in names:
                key = name + "_status" if name != "usdt" else "usdt_status"
                row = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
                settings[name] = row[0] if row else "متوقف"
            configs = db().execute("SELECT provider,is_active,is_paused,connection_status,last_verified FROM api_configs").fetchall()
        api_state = [{"provider": r[0] or "", "active": bool(r[1]), "paused": bool(r[2]), "status": r[3] or "disconnected", "last_verified": r[4] or ""} for r in configs]
        return jsonify({"ok": True, "services": settings, "api_connections": api_state}), 200

    @app.put("/api/admin/services")
    def update_services():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        payload = request.get_json(silent=True) or {}
        accepted = {"syriatel_status", "sham_status", "usdt_status", "binance_status"}
        if not payload or any(key not in accepted for key in payload):
            return jsonify({"ok": False, "error": "invalid_service"}), 400
        for key, value in payload.items():
            if str(value) not in {"active", "متوقف", "stopped", "paused"}:
                return jsonify({"ok": False, "error": "invalid_service_status", "key": key}), 400
        now = _now().strftime("%Y-%m-%d %H:%M:%S")
        with db_lock:
            for key, value in payload.items():
                db().execute("UPDATE settings SET value=?,updated_at=?,updated_by=? WHERE key=?", (str(value), now, int(user["telegram_id"]), key))
            db().commit(); audit(user, "تعديل حالة خدمات الدفع", str(payload))
        return jsonify({"ok": True, "updated": sorted(payload)}), 200

    @app.get("/api/admin/wheel")
    def get_wheel_admin():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        with db_lock:
            keys = ("wheel_enabled", "wheel_daily_charge_threshold", "wheel_title", "wheel_spin_message")
            settings = {key: ((db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone() or [""])[0]) for key in keys}
            rows = db().execute("SELECT id,label,prize_type,value,weight,is_active,created_at,updated_at FROM wheel_prizes ORDER BY id").fetchall()
        prizes = [{"id": int(r[0]), "label": r[1] or "", "type": r[2], "value": float(r[3]), "weight": float(r[4]), "active": bool(r[5]), "created_at": r[6] or "", "updated_at": r[7] or ""} for r in rows]
        return jsonify({"ok": True, "settings": settings, "prizes": prizes}), 200

    @app.post("/api/admin/wheel/prizes")
    def create_wheel_prize():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        payload = request.get_json(silent=True) or {}
        label, kind = str(payload.get("label", "")).strip()[:120], str(payload.get("type", "")).strip()
        try:
            value, weight = float(payload.get("value")), float(payload.get("weight", 1))
            if not label or kind not in {"fixed", "percent"} or not math.isfinite(value) or value < 0 or not math.isfinite(weight) or weight < 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_prize"}), 400
        now = _now().strftime("%Y-%m-%d %H:%M:%S")
        with db_lock:
            db().execute("INSERT INTO wheel_prizes(label,prize_type,value,weight,is_active,created_at,updated_at) VALUES (?,?,?,?,1,?,?)", (label, kind, value, weight, now, now))
            db().commit(); audit(user, "إضافة جائزة للعجلة", f"label={label}")
        return jsonify({"ok": True}), 201

    @app.put("/api/admin/wheel/prizes/<int:prize_id>")
    def update_wheel_prize(prize_id):
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_manage_buttons"):
            return forbidden()
        payload = request.get_json(silent=True) or {}
        updates, params = [], []
        if "label" in payload:
            label = str(payload["label"]).strip()[:120]
            if not label: return jsonify({"ok": False, "error": "invalid_label"}), 400
            updates += ["label=?"]; params += [label]
        if "type" in payload:
            if payload["type"] not in {"fixed", "percent"}: return jsonify({"ok": False, "error": "invalid_type"}), 400
            updates += ["prize_type=?"]; params += [payload["type"]]
        for field in ("value", "weight"):
            if field in payload:
                try:
                    number = float(payload[field])
                    if not math.isfinite(number) or number < 0: raise ValueError
                except (TypeError, ValueError): return jsonify({"ok": False, "error": "invalid_value"}), 400
                updates += [field + "=?"]; params += [number]
        if "active" in payload:
            if not isinstance(payload["active"], bool): return jsonify({"ok": False, "error": "invalid_active"}), 400
            updates += ["is_active=?"]; params += [1 if payload["active"] else 0]
        if not updates: return jsonify({"ok": False, "error": "no_changes"}), 400
        updates += ["updated_at=?"]; params += [_now().strftime("%Y-%m-%d %H:%M:%S"), prize_id]
        with db_lock:
            changed = db().execute("UPDATE wheel_prizes SET " + ",".join(updates) + " WHERE id=?", tuple(params))
            if changed.rowcount != 1: db().rollback(); return jsonify({"ok": False, "error": "prize_not_found"}), 404
            db().commit(); audit(user, "تعديل جائزة العجلة", f"id={prize_id}")
        return jsonify({"ok": True, "id": prize_id}), 200

    @app.get("/api/admin/ai/status")
    def assistant_status():
        user = current()
        if not user: return denied()
        if not allowed(user, "can_use_ai"): return forbidden()
        with db_lock: row = db().execute("SELECT value FROM ai_settings WHERE key='enabled'").fetchone()
        return jsonify({"ok": True, "enabled": bool(row and str(row[0]).lower() in {"1", "true", "on"}), "configured": bool(os.environ.get("GEMINI_API_KEY", "").strip()), "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")}), 200

    @app.get("/api/admin/assistant/history")
    def assistant_history():
        user = current()
        if not user: return denied()
        if not allowed(user, "can_use_ai"): return forbidden()
        with db_lock: rows = db().execute("SELECT role,content,created_at FROM ai_conversations WHERE user_id=? ORDER BY id DESC LIMIT 40", (int(user["telegram_id"]),)).fetchall()
        return jsonify({"ok": True, "items": [{"role": r[0], "content": r[1], "created_at": r[2]} for r in reversed(rows)]}), 200

    @app.post("/api/admin/assistant/ask")
    def assistant_ask_route():
        user = current()
        if not user: return denied()
        if not allowed(user, "can_use_ai"): return forbidden()
        prompt = str((request.get_json(silent=True) or {}).get("prompt", "")).strip()
        if not prompt or len(prompt) > 4000: return jsonify({"ok": False, "error": "invalid_prompt"}), 400
        if not callable(assistant_ask): return jsonify({"ok": False, "error": "assistant_unavailable"}), 503
        try: answer, error = assistant_ask(int(user["telegram_id"]), prompt)
        except Exception:
            app.logger.exception("Admin assistant request failed")
            return jsonify({"ok": False, "error": "assistant_failed"}), 502
        if error: return jsonify({"ok": False, "error": "assistant_unavailable", "message": error}), 503
        return jsonify({"ok": True, "answer": answer, "executed": False}), 200

    return True
