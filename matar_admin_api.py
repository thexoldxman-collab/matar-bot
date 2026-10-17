"""Secure, read-only-first mobile admin API for Matar Bot.

The API deliberately does not settle financial requests. A request can only be
marked financially complete after a separately reviewed integration calls the
bot's existing atomic business logic.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import string
import time
from functools import wraps
from typing import Callable

from flask import Blueprint, jsonify, request

PAIRING_TTL_SECONDS = 300
SESSION_TTL_SECONDS = 12 * 60 * 60
NOTIFICATION_KEYS = {
    "charge_new",
    "withdraw_new",
    "financial_error",
    "moderator_actions",
    "referrals",
    "bot_offline",
    "ai_decisions",
}
PERMISSION_COLUMNS = (
    "can_reply_tickets",
    "can_handle_charges",
    "can_handle_withdraws",
    "can_send_broadcast",
    "can_manage_users",
    "can_charge_withdraw_users",
    "can_view_stats",
    "can_manage_buttons",
    "can_access_full_admin",
    "can_manage_moderators",
    "can_use_ai",
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> int:
    return int(time.time())


def _fetchone(db, sql: str, params=()):
    return db.execute(sql, params).fetchone()


def _audit(db, actor_id: int, action: str, details: dict | None = None, result: str = "success"):
    db.execute(
        "INSERT INTO admin_app_audit(actor_id, action, details, created_at, result) VALUES (?,?,?,?,?)",
        (actor_id, action, json.dumps(details or {}, ensure_ascii=False), _now(), result),
    )
    db.commit()


def _moderator_record(db, user_id: int):
    cursor = db.execute(
        "SELECT user_id, custom_name, can_reply_tickets, can_handle_charges, "
        "can_handle_withdraws, can_send_broadcast, can_manage_users, "
        "can_charge_withdraw_users, can_view_stats, can_manage_buttons, "
        "can_access_full_admin, can_manage_moderators, can_use_ai, permissions "
        "FROM moderators WHERE user_id=?",
        (user_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    keys = [column[0] for column in cursor.description]
    record = dict(zip(keys, row))
    permissions = {}
    try:
        permissions = json.loads(record.get("permissions") or "{}")
        if not isinstance(permissions, dict):
            permissions = {}
    except (TypeError, ValueError):
        permissions = {}
    for key in PERMISSION_COLUMNS:
        permissions[key] = bool(record.get(key, 0)) or bool(permissions.get(key, False))
    return {"user_id": int(record["user_id"]), "name": record.get("custom_name") or "", "permissions": permissions}


def _actor(db, user_id: int, owner_id: int):
    if user_id == owner_id:
        return {"user_id": user_id, "role": "owner", "name": "المالك", "permissions": {key: True for key in PERMISSION_COLUMNS}}
    moderator = _moderator_record(db, user_id)
    if moderator:
        return {"user_id": user_id, "role": "moderator", "name": moderator["name"], "permissions": moderator["permissions"]}
    return None


def register_admin_api(app, bot, owner_id: int, db_factory: Callable):
    """Register routes and /adminapp Telegram pairing command on the existing bot app."""
    bp = Blueprint("matar_admin_api", __name__, url_prefix="/api/admin")

    def ensure_schema():
        db = db_factory()
        try:
            db.execute("""CREATE TABLE IF NOT EXISTS admin_app_pairing_codes (
                code_hash TEXT PRIMARY KEY,
                telegram_user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                used_at INTEGER
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS admin_app_sessions (
                token_hash TEXT PRIMARY KEY,
                telegram_user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked_at INTEGER
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS admin_app_notification_preferences (
                telegram_user_id INTEGER NOT NULL,
                event_key TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (telegram_user_id, event_key)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS admin_app_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL,
                result TEXT NOT NULL DEFAULT 'success'
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS admin_app_operation_claims (
                operation_type TEXT NOT NULL,
                operation_id INTEGER NOT NULL,
                claimed_by INTEGER NOT NULL,
                claimed_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                PRIMARY KEY (operation_type, operation_id)
            )""")
            db.commit()
        finally:
            db.close()

    ensure_schema()

    def require_session(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            auth = (request.headers.get("Authorization") or "").strip()
            if not auth.startswith("Bearer "):
                return jsonify({"error": "authentication_required"}), 401
            token = auth[7:].strip()
            if len(token) < 32:
                return jsonify({"error": "authentication_required"}), 401
            db = db_factory()
            try:
                session = _fetchone(
                    db,
                    "SELECT telegram_user_id, expires_at, revoked_at FROM admin_app_sessions WHERE token_hash=?",
                    (_digest(token),),
                )
                if not session or session[2] is not None or int(session[1]) <= _now():
                    return jsonify({"error": "session_expired"}), 401
                actor_id = int(session[0])
                actor = _actor(db, actor_id, owner_id)
                if not actor:
                    _audit(db, actor_id, "session_denied_removed_admin", {}, "denied")
                    return jsonify({"error": "admin_access_revoked"}), 403
                request.admin_actor = actor
                request.admin_db = db
                response = handler(*args, **kwargs)
                return response
            finally:
                db.close()
        return wrapped

    def require_permission(permission):
        def decorator(handler):
            @wraps(handler)
            @require_session
            def wrapped(*args, **kwargs):
                actor = request.admin_actor
                if actor["role"] != "owner" and not actor["permissions"].get(permission, False):
                    _audit(request.admin_db, actor["user_id"], "permission_denied", {"permission": permission}, "denied")
                    return jsonify({"error": "permission_denied", "permission": permission}), 403
                return handler(*args, **kwargs)
            return wrapped
        return decorator

    @bp.post("/pairing/exchange")
    def exchange_pairing_code():
        body = request.get_json(silent=True) or {}
        code = str(body.get("code", "")).strip().upper().replace("-", "")
        if len(code) != 8 or any(char not in string.ascii_uppercase + string.digits for char in code):
            return jsonify({"error": "invalid_or_expired_code"}), 401
        db = db_factory()
        try:
            record = _fetchone(
                db,
                "SELECT telegram_user_id, expires_at, used_at FROM admin_app_pairing_codes WHERE code_hash=?",
                (_digest(code),),
            )
            now = _now()
            if not record or record[2] is not None or int(record[1]) <= now:
                return jsonify({"error": "invalid_or_expired_code"}), 401
            actor_id = int(record[0])
            actor = _actor(db, actor_id, owner_id)
            if not actor:
                _audit(db, actor_id, "pairing_denied_removed_admin", {}, "denied")
                return jsonify({"error": "admin_access_revoked"}), 403
            changed = db.execute(
                "UPDATE admin_app_pairing_codes SET used_at=? WHERE code_hash=? AND used_at IS NULL AND expires_at>?",
                (now, _digest(code), now),
            )
            if changed.rowcount != 1:
                db.rollback()
                return jsonify({"error": "invalid_or_expired_code"}), 401
            token = secrets.token_urlsafe(40)
            db.execute(
                "INSERT INTO admin_app_sessions(token_hash, telegram_user_id, created_at, expires_at, revoked_at) VALUES (?,?,?,?,NULL)",
                (_digest(token), actor_id, now, now + SESSION_TTL_SECONDS),
            )
            _audit(db, actor_id, "mobile_login", {"role": actor["role"]})
            db.commit()
            return jsonify({
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": SESSION_TTL_SECONDS,
                "user": {"telegram_user_id": actor_id, "role": actor["role"], "display_name": actor["name"]},
                "permissions": actor["permissions"],
            })
        finally:
            db.close()

    @bp.get("/me")
    @require_session
    def me():
        actor = request.admin_actor
        return jsonify({"user": {"telegram_user_id": actor["user_id"], "role": actor["role"], "display_name": actor["name"]}, "permissions": actor["permissions"]})

    @bp.get("/overview")
    @require_permission("can_view_stats")
    def overview():
        db = request.admin_db
        def count(sql):
            row = _fetchone(db, sql)
            return int(row[0] or 0)
        return jsonify({
            "mode": "demo",
            "real_financial_operations_enabled": False,
            "users": count("SELECT COUNT(*) FROM users WHERE deleted=0"),
            "pending_charges": count("SELECT COUNT(*) FROM pending_charges WHERE status='pending'"),
            "pending_withdraws": count("SELECT COUNT(*) FROM pending_withdraws WHERE status='pending'"),
            "moderators": count("SELECT COUNT(*) FROM moderators"),
        })

    @bp.get("/operations")
    @require_session
    def operations():
        actor = request.admin_actor
        db = request.admin_db
        results = []
        if actor["role"] == "owner" or actor["permissions"].get("can_handle_charges", False):
            rows = db.execute(
                "SELECT id, user_id, method, amount, status, created_at, processed_by FROM pending_charges "
                "WHERE status IN ('pending','processing') ORDER BY id DESC LIMIT 100"
            ).fetchall()
            results.extend([{"id": int(r[0]), "type": "charge", "user_id": r[1], "method": r[2], "amount": r[3], "status": r[4], "created_at": r[5], "processed_by": r[6]} for r in rows])
        if actor["role"] == "owner" or actor["permissions"].get("can_handle_withdraws", False):
            rows = db.execute(
                "SELECT id, user_id, method, amount, status, created_at, processed_by FROM pending_withdraws "
                "WHERE status IN ('pending','processing') ORDER BY id DESC LIMIT 100"
            ).fetchall()
            results.extend([{"id": int(r[0]), "type": "withdraw", "user_id": r[1], "method": r[2], "amount": r[3], "status": r[4], "created_at": r[5], "processed_by": r[6]} for r in rows])
        for item in results:
            claim = _fetchone(
                db,
                "SELECT claimed_by, expires_at FROM admin_app_operation_claims "
                "WHERE operation_type=? AND operation_id=? AND expires_at>?",
                (item["type"], item["id"], _now()),
            )
            item["claim"] = {"claimed_by": int(claim[0]), "expires_at": int(claim[1])} if claim else None
        results.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return jsonify({"items": results, "mode": "demo_until_financial_workflow_integration"})

    def _operation_permission(kind):
        if kind == "charge":
            return "can_handle_charges", "pending_charges"
        if kind == "withdraw":
            return "can_handle_withdraws", "pending_withdraws"
        return None, None

    @bp.post("/operations/<kind>/<int:operation_id>/claim")
    @require_session
    def claim_operation(kind, operation_id):
        permission, table = _operation_permission(kind)
        actor = request.admin_actor
        db = request.admin_db
        if not permission:
            return jsonify({"error": "invalid_operation_type"}), 400
        if actor["role"] != "owner" and not actor["permissions"].get(permission, False):
            _audit(db, actor["user_id"], "permission_denied", {"permission": permission}, "denied")
            return jsonify({"error": "permission_denied"}), 403
        operation = _fetchone(db, f"SELECT id, status, processed_by FROM {table} WHERE id=?", (operation_id,))
        if not operation:
            return jsonify({"error": "operation_not_found"}), 404
        if str(operation[1]).lower() not in ("pending", "processing"):
            return jsonify({"error": "operation_not_open"}), 409
        now = _now()
        db.execute(
            "DELETE FROM admin_app_operation_claims WHERE operation_type=? AND operation_id=? AND expires_at<=?",
            (kind, operation_id, now),
        )
        db.execute(
            "INSERT OR IGNORE INTO admin_app_operation_claims(operation_type,operation_id,claimed_by,claimed_at,expires_at) VALUES (?,?,?,?,?)",
            (kind, operation_id, actor["user_id"], now, now + 600),
        )
        claim = _fetchone(
            db,
            "SELECT claimed_by, claimed_at, expires_at FROM admin_app_operation_claims WHERE operation_type=? AND operation_id=?",
            (kind, operation_id),
        )
        if not claim or int(claim[0]) != actor["user_id"]:
            db.commit()
            return jsonify({"error": "already_claimed", "claimed_by": int(claim[0]) if claim else None}), 409
        _audit(db, actor["user_id"], "operation_claimed", {"type": kind, "id": operation_id, "expires_at": int(claim[2])})
        db.commit()
        return jsonify({"claimed": True, "type": kind, "id": operation_id, "claimed_at": int(claim[1]), "expires_at": int(claim[2])})

    @bp.post("/operations/<kind>/<int:operation_id>/release")
    @require_session
    def release_operation(kind, operation_id):
        permission, _table = _operation_permission(kind)
        actor = request.admin_actor
        db = request.admin_db
        if not permission:
            return jsonify({"error": "invalid_operation_type"}), 400
        if actor["role"] != "owner" and not actor["permissions"].get(permission, False):
            return jsonify({"error": "permission_denied"}), 403
        claim = _fetchone(
            db,
            "SELECT claimed_by FROM admin_app_operation_claims WHERE operation_type=? AND operation_id=?",
            (kind, operation_id),
        )
        if not claim:
            return jsonify({"released": True})
        if int(claim[0]) != actor["user_id"] and actor["role"] != "owner":
            return jsonify({"error": "claim_owned_by_another_admin"}), 403
        db.execute(
            "DELETE FROM admin_app_operation_claims WHERE operation_type=? AND operation_id=?",
            (kind, operation_id),
        )
        _audit(db, actor["user_id"], "operation_claim_released", {"type": kind, "id": operation_id})
        db.commit()
        return jsonify({"released": True})

    @bp.post("/operations/<kind>/<int:operation_id>/complete")
    @require_session
    def block_financial_completion(kind, operation_id):
        permission, _table = _operation_permission(kind)
        actor = request.admin_actor
        db = request.admin_db
        if not permission:
            return jsonify({"error": "invalid_operation_type"}), 400
        if actor["role"] != "owner" and not actor["permissions"].get(permission, False):
            return jsonify({"error": "permission_denied"}), 403
        _audit(db, actor["user_id"], "financial_completion_blocked", {"type": kind, "id": operation_id}, "blocked")
        db.commit()
        return jsonify({
            "error": "financial_workflow_not_integrated",
            "message": "لم يتم اعتماد التنفيذ المالي الحقيقي؛ لم تُغيّر أرصدة ولم يُعلن نجاح العملية."
        }), 423

    @bp.get("/notifications")
    @require_session
    def get_notifications():
        db = request.admin_db
        actor_id = request.admin_actor["user_id"]
        rows = db.execute(
            "SELECT event_key, enabled FROM admin_app_notification_preferences WHERE telegram_user_id=?",
            (actor_id,),
        ).fetchall()
        saved = {str(row[0]): bool(row[1]) for row in rows}
        defaults = {
            "charge_new": True, "withdraw_new": True, "financial_error": True,
            "moderator_actions": True, "referrals": False, "bot_offline": True, "ai_decisions": False,
        }
        defaults.update(saved)
        return jsonify({"preferences": defaults, "push_delivery_configured": False})

    @bp.put("/notifications")
    @require_session
    def save_notifications():
        body = request.get_json(silent=True) or {}
        prefs = body.get("preferences")
        if not isinstance(prefs, dict) or not prefs or any(key not in NOTIFICATION_KEYS or not isinstance(value, bool) for key, value in prefs.items()):
            return jsonify({"error": "invalid_preferences"}), 400
        db = request.admin_db
        actor_id = request.admin_actor["user_id"]
        now = _now()
        for key, enabled in prefs.items():
            db.execute(
                "INSERT OR REPLACE INTO admin_app_notification_preferences(telegram_user_id,event_key,enabled,updated_at) VALUES (?,?,?,?)",
                (actor_id, key, 1 if enabled else 0, now),
            )
        _audit(db, actor_id, "notification_preferences_updated", {"keys": sorted(prefs.keys())})
        db.commit()
        return jsonify({"saved": True, "preferences": prefs, "push_delivery_configured": False})

    @bp.get("/audit")
    @require_session
    def audit():
        actor = request.admin_actor
        if actor["role"] != "owner" and not actor["permissions"].get("can_access_full_admin", False):
            _audit(request.admin_db, actor["user_id"], "permission_denied", {"permission": "audit"}, "denied")
            return jsonify({"error": "permission_denied"}), 403
        rows = request.admin_db.execute(
            "SELECT actor_id, action, details, created_at, result FROM admin_app_audit ORDER BY id DESC LIMIT 100"
        ).fetchall()
        return jsonify({"items": [{"actor_id": r[0], "action": r[1], "details": r[2], "created_at": r[3], "result": r[4]} for r in rows]})

    @bp.post("/logout")
    @require_session
    def logout():
        actor_id = request.admin_actor["user_id"]
        request.admin_db.execute(
            "UPDATE admin_app_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
            (_now(), _digest(request.headers.get("Authorization", "")[7:].strip())),
        )
        _audit(request.admin_db, actor_id, "mobile_logout")
        request.admin_db.commit()
        return jsonify({"logged_out": True})

    app.register_blueprint(bp)

    def issue_pairing_code(message):
        user_id = int(message.from_user.id)
        if getattr(message.chat, "type", "private") != "private":
            bot.reply_to(message, "لأمان حسابك، اطلب رمز التطبيق بمحادثة خاصة مع البوت.")
            return
        db = db_factory()
        try:
            actor = _actor(db, user_id, owner_id)
            if not actor:
                bot.reply_to(message, "عذراً، هذا الحساب غير مخوّل لدخول تطبيق الإدارة.")
                _audit(db, user_id, "pairing_code_denied", {}, "denied")
                return
            alphabet = string.ascii_uppercase + string.digits
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            now = _now()
            db.execute(
                "UPDATE admin_app_pairing_codes SET used_at=? WHERE telegram_user_id=? AND used_at IS NULL",
                (now, user_id),
            )
            db.execute(
                "INSERT INTO admin_app_pairing_codes(code_hash,telegram_user_id,created_at,expires_at,used_at) VALUES (?,?,?,?,NULL)",
                (_digest(code), user_id, now, now + PAIRING_TTL_SECONDS),
            )
            _audit(db, user_id, "pairing_code_issued", {"expires_in": PAIRING_TTL_SECONDS})
            db.commit()
            bot.reply_to(message, "رمز ربط Matar Admin (صالح لمدة 5 دقائق ولمرة واحدة):\n\n" + code + "\n\nلا تشارك الرمز مع أي شخص.")
        finally:
            db.close()

    # The bot has an earlier catch-all text router; it dispatches /adminapp
    # to this callback explicitly so the pairing command cannot be swallowed.
    app.config["matar_admin_app_pairing_handler"] = issue_pairing_code
    return bp
