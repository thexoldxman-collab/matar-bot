"""Authenticated admin API for Matar Admin.

All authority is derived from the Telegram-authenticated server session.
Financial requests are never marked completed by this module.
"""
from __future__ import annotations

import json
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


def register_admin_api(app, bot, conn, db_lock, owner_id, check_permission):
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
            conn.execute(
                """INSERT INTO admin_logs
                   (admin_id, display_name, action_type, details, target_user, amount, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (int(user["telegram_id"]), "مدير التطبيق" if user.get("role") == "owner" else "مشرف التطبيق",
                 str(action)[:120], str(details)[:1000], target_user, amount,
                 _now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
        except Exception:
            app.logger.exception("Could not write admin app audit log")

    def permission_for_type(operation_type):
        return "can_handle_withdraws" if operation_type == "withdraw" else "can_handle_charges"

    def ensure_claims_table():
        # Expired claims are treated as free immediately; delete lazily to keep the table small.
        conn.execute("DELETE FROM admin_operation_claims WHERE expires_at<=?", (_iso(),))
        conn.commit()

    @app.get("/api/admin/dashboard")
    def admin_dashboard():
        user = current()
        if not user:
            return denied()
        if not allowed(user, "can_view_stats"):
            return forbidden()
        with db_lock:
            def count(sql, args=()):
                row = conn.execute(sql, args).fetchone()
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
                    rows = conn.execute(
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
                    rows = conn.execute(
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
                    claim = conn.execute(
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
                row = conn.execute(
                    f"SELECT status FROM {table} WHERE id=?", (operation_id,)
                ).fetchone()
                if not row:
                    return jsonify({"ok": False, "error": "operation_not_found"}), 404
                if row[0] not in ("pending", "processing"):
                    return jsonify({"ok": False, "error": "operation_not_open"}), 409
                existing = conn.execute(
                    """SELECT claimed_by,expires_at FROM admin_operation_claims
                       WHERE operation_type=? AND operation_id=?""",
                    (operation_type, operation_id),
                ).fetchone()
                uid = int(user["telegram_id"])
                if existing and str(existing[1]) > now_text and int(existing[0]) != uid:
                    return jsonify({"ok": False, "error": "already_claimed"}), 409
                if existing:
                    conn.execute(
                        """UPDATE admin_operation_claims SET claimed_by=?,claimed_at=?,expires_at=?
                           WHERE operation_type=? AND operation_id=?""",
                        (uid, now_text, expiry, operation_type, operation_id),
                    )
                else:
                    conn.execute(
                        """INSERT INTO admin_operation_claims
                           (operation_type,operation_id,claimed_by,claimed_at,expires_at)
                           VALUES (?,?,?,?,?)""",
                        (operation_type, operation_id, uid, now_text, expiry),
                    )
                conn.commit()
                audit(user, "استلام طلب", f"{operation_type}:{operation_id} لمدة 10 دقائق")
            except Exception:
                conn.rollback()
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
            row = conn.execute(
                """SELECT claimed_by FROM admin_operation_claims
                   WHERE operation_type=? AND operation_id=?""",
                (operation_type, operation_id),
            ).fetchone()
            if not row:
                return jsonify({"ok": True, "message": "الطلب غير مستلم حالياً."}), 200
            if int(row[0]) != int(user["telegram_id"]) and user.get("role") != "owner":
                return forbidden()
            conn.execute(
                "DELETE FROM admin_operation_claims WHERE operation_type=? AND operation_id=?",
                (operation_type, operation_id),
            )
            conn.commit()
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
        # Never mark a financial request as paid/completed from the app until the
        # owner explicitly enables and tests the real transaction integration.
        return jsonify({
            "ok": False,
            "error": "financial_execution_disabled",
            "message": "لم تتغير الأرصدة. اعتماد التنفيذ المالي من التطبيق غير مفعّل بعد.",
        }), 409

    @app.get("/api/admin/notifications")
    def get_notifications():
        user = current()
        if not user:
            return denied()
        with db_lock:
            row = conn.execute(
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
            conn.execute(
                """INSERT INTO admin_app_preferences(user_id,preferences,updated_at)
                   VALUES (?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET preferences=excluded.preferences,updated_at=excluded.updated_at""",
                (int(user["telegram_id"]), json.dumps(prefs, ensure_ascii=False), _iso()),
            )
            conn.commit()
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
            rows = conn.execute(
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
        fields = sorted(PERMISSION_COLUMNS)
        columns = ["user_id", "custom_name", "added_by", "added_at"] + fields
        values = [target, name, int(user["telegram_id"]), _now().strftime("%Y-%m-%d %H:%M:%S")]
        values.extend(1 if permissions.get(field, False) else 0 for field in fields)
        placeholders = ",".join("?" for _ in columns)
        with db_lock:
            exists = conn.execute("SELECT 1 FROM moderators WHERE user_id=?", (target,)).fetchone()
            if exists:
                return jsonify({"ok": False, "error": "moderator_exists"}), 409
            conn.execute(f"INSERT INTO moderators ({','.join(columns)}) VALUES ({placeholders})", tuple(values))
            conn.commit()
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
            for field, enabled in permissions.items():
                updates.append(f"{field}=?")
                values.append(1 if enabled else 0)
        if not updates:
            return jsonify({"ok": False, "error": "nothing_to_update"}), 400
        values.append(target_id)
        with db_lock:
            cur = conn.execute(f"UPDATE moderators SET {','.join(updates)} WHERE user_id=?", tuple(values))
            conn.commit()
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
        with db_lock:
            cur = conn.execute("DELETE FROM moderators WHERE user_id=?", (target_id,))
            conn.commit()
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
            rows = conn.execute(
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
            cur = conn.execute(f"UPDATE dynamic_buttons SET {','.join(updates)} WHERE id=?", tuple(values))
            conn.commit()
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
            rows = conn.execute(
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
            rows = conn.execute("SELECT user_id FROM users WHERE COALESCE(deleted,0)=0 AND COALESCE(status,'active')='active' ORDER BY user_id LIMIT 5000").fetchall()
            ids = [int(row[0]) for row in rows]
        else:
            rows = conn.execute("SELECT user_id FROM moderators ORDER BY user_id").fetchall()
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

    return True
