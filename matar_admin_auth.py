"""Secure Telegram one-time-code authentication for the Matar Admin app.

The app never supplies its own role. The server derives owner/moderator status
from the configured owner ID and the bot's current moderator records.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import jsonify, request


PERMISSION_KEYS = (
    "can_handle_charges",
    "can_handle_withdraws",
    "can_manage_users",
    "can_view_stats",
    "can_use_ai",
    "can_manage_buttons",
    "can_manage_moderators",
)


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value):
    return value.isoformat().replace("+00:00", "Z")


def _token_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def register_admin_auth(app, bot, conn, db_lock, owner_id, is_moderator, check_permission):
    """Register /link and API endpoints; call once after creating the Flask app."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS admin_link_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            role TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS admin_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.commit()

    def current_role(user_id):
        if int(user_id) == int(owner_id):
            return "owner"
        try:
            return "moderator" if is_moderator(int(user_id)) else None
        except Exception:
            return None

    def permissions_for(user_id, role):
        if role == "owner":
            return {key: True for key in PERMISSION_KEYS}
        result = {}
        for key in PERMISSION_KEYS:
            try:
                result[key] = bool(check_permission(int(user_id), key))
            except Exception:
                result[key] = False
        return result

    def issue_link_code_for_user(user_id, chat_id):
        user_id = int(user_id)
        role = current_role(user_id)
        if role is None:
            bot.send_message(
                chat_id,
                "❌ هذا الحساب غير مخوّل لربط التطبيق؛ الربط متاح للمالك والمشرفين المضافين فقط.",
            )
            return
        code = f"{secrets.randbelow(1_000_000):06d}"
        now = _now()
        created_at = _iso(now)
        expires_at = _iso(now + timedelta(minutes=5))
        with db_lock:
            conn.execute("UPDATE admin_link_codes SET used=1 WHERE user_id=? AND used=0", (user_id,))
            conn.execute(
                """INSERT INTO admin_link_codes
                   (user_id, role, code_hash, created_at, expires_at, used)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (user_id, role, _token_hash(code), created_at, expires_at),
            )
            conn.commit()
        bot.send_message(
            chat_id,
            "🔐 رمز ربط تطبيق إدارة ماتر\n\n"
            f"الرمز: {code}\n"
            "صالح لمدة 5 دقائق ولمرة واحدة فقط. لا تشاركه مع أي شخص.",
        )

    @bot.message_handler(commands=["link"])
    def issue_link_code(message):
        issue_link_code_for_user(message.from_user.id, message.chat.id)

    @app.post("/api/admin/auth/verify")
    def verify_link_code():
        payload = request.get_json(silent=True) or {}
        code = str(payload.get("code", "")).strip()
        if not re.fullmatch(r"\d{6}", code):
            return jsonify({"ok": False, "error": "invalid_code"}), 400

        now_text = _iso(_now())
        raw_token = secrets.token_urlsafe(32)
        role = None
        user_id = None
        with db_lock:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    """SELECT id, user_id FROM admin_link_codes
                       WHERE code_hash=? AND used=0 AND expires_at>?
                       ORDER BY id DESC LIMIT 1""",
                    (_token_hash(code), now_text),
                ).fetchone()
                if not row:
                    conn.rollback()
                    return jsonify({"ok": False, "error": "invalid_or_expired_code"}), 401

                code_id, user_id = int(row[0]), int(row[1])
                role = current_role(user_id)
                if role is None:
                    conn.execute(
                        "UPDATE admin_link_codes SET used=1 WHERE id=? AND used=0",
                        (code_id,),
                    )
                    conn.commit()
                    return jsonify({"ok": False, "error": "access_revoked"}), 403

                changed = conn.execute(
                    """UPDATE admin_link_codes SET used=1
                       WHERE id=? AND used=0 AND expires_at>?""",
                    (code_id, now_text),
                )
                if changed.rowcount != 1:
                    conn.rollback()
                    return jsonify({"ok": False, "error": "invalid_or_expired_code"}), 401

                session_expiry = _iso(_now() + timedelta(hours=12))
                conn.execute(
                    """INSERT INTO admin_sessions
                       (token_hash, user_id, role, created_at, expires_at, revoked)
                       VALUES (?, ?, ?, ?, ?, 0)""",
                    (_token_hash(raw_token), user_id, role, now_text, session_expiry),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                app.logger.exception("Admin app authentication failed")
                return jsonify({"ok": False, "error": "authentication_unavailable"}), 503

        return jsonify({
            "ok": True,
            "access_token": raw_token,
            "token_type": "Bearer",
            "expires_at": session_expiry,
            "user": {
                "telegram_id": user_id,
                "role": role,
                "is_owner": role == "owner",
                "permissions": permissions_for(user_id, role),
            },
        }), 200

    def authenticated_session():
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        token = header[7:].strip()
        if len(token) < 30:
            return None
        now_text = _iso(_now())
        with db_lock:
            row = conn.execute(
                """SELECT user_id FROM admin_sessions
                   WHERE token_hash=? AND revoked=0 AND expires_at>?""",
                (_token_hash(token), now_text),
            ).fetchone()
        if not row:
            return None
        user_id = int(row[0])
        role = current_role(user_id)
        if role is None:
            return None
        return {
            "telegram_id": user_id,
            "role": role,
            "is_owner": role == "owner",
            "permissions": permissions_for(user_id, role),
        }, _token_hash(token)

    @app.get("/api/admin/auth/me")
    def admin_auth_me():
        session = authenticated_session()
        if not session:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        user, _ = session
        return jsonify({"ok": True, "user": user}), 200

    @app.post("/api/admin/auth/logout")
    def admin_auth_logout():
        session = authenticated_session()
        if not session:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        _, digest = session
        with db_lock:
            conn.execute("UPDATE admin_sessions SET revoked=1 WHERE token_hash=?", (digest,))
            conn.commit()
        return jsonify({"ok": True}), 200


    # App-only preferences are per Telegram identity; they do not alter bot-wide settings.
    conn.execute(
        """CREATE TABLE IF NOT EXISTS admin_app_preferences (
            user_id BIGINT PRIMARY KEY,
            preferences_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    # Claims expire after ten minutes and never change a financial status by themselves.
    conn.execute(
        """CREATE TABLE IF NOT EXISTS admin_operation_claims (
            operation_type TEXT NOT NULL,
            operation_id BIGINT NOT NULL,
            claimed_by BIGINT NOT NULL,
            claimed_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            PRIMARY KEY (operation_type, operation_id)
        )"""
    )
    conn.commit()

    default_preferences = {
        "charge_new": True,
        "withdraw_new": True,
        "financial_error": True,
        "moderator_actions": True,
        "referrals": False,
        "bot_offline": True,
        "ai_decisions": False,
    }

    def app_session():
        session = authenticated_session()
        if not session:
            return None, (jsonify({"ok": False, "error": "unauthorized"}), 401)
        user, _ = session
        return user, None

    def operation_permission(operation_type):
        return "can_handle_charges" if operation_type == "charge" else "can_handle_withdraws"

    def operation_exists(operation_type, operation_id):
        table = "pending_charges" if operation_type == "charge" else "pending_withdraws"
        row = conn.execute(
            f"SELECT id, user_id, amount, status, created_at, method FROM {table} WHERE id=?",
            (operation_id,),
        ).fetchone()
        return row

    @app.get("/api/admin/operations")
    def admin_operations_list():
        user, error = app_session()
        if error:
            return error
        items = []
        now_text = _iso(_now())
        with db_lock:
            conn.execute("DELETE FROM admin_operation_claims WHERE expires_at<=?", (now_text,))
            for operation_type, table, permission in (
                ("charge", "pending_charges", "can_handle_charges"),
                ("withdraw", "pending_withdraws", "can_handle_withdraws"),
            ):
                if not (user.get("is_owner") or permissions_for(user["telegram_id"], user["role"]).get(permission, False)):
                    continue
                rows = conn.execute(
                    f"""SELECT id, user_id, amount, status, created_at, method
                        FROM {table} WHERE status IN ('pending','processing')
                        ORDER BY id DESC LIMIT 100"""
                ).fetchall()
                for row in rows:
                    operation_id, user_id, amount, status, created_at, method = row
                    claim = conn.execute(
                        """SELECT claimed_by, claimed_at, expires_at FROM admin_operation_claims
                           WHERE operation_type=? AND operation_id=? AND expires_at>?""",
                        (operation_type, int(operation_id), now_text),
                    ).fetchone()
                    if operation_type == "withdraw":
                        extra = conn.execute(
                            "SELECT account, net_amount, currency FROM pending_withdraws WHERE id=?",
                            (int(operation_id),),
                        ).fetchone()
                        account = extra[0] if extra else None
                        net_amount = extra[1] if extra else None
                        currency = extra[2] if extra else None
                    else:
                        extra = conn.execute(
                            "SELECT receipt_number, syriatel_code, txn_receipt FROM pending_charges WHERE id=?",
                            (int(operation_id),),
                        ).fetchone()
                        account = extra[0] if extra else None
                        net_amount = None
                        currency = None
                    items.append({
                        "id": int(operation_id),
                        "type": operation_type,
                        "user_id": int(user_id) if user_id is not None else None,
                        "amount": float(amount or 0),
                        "status": status,
                        "created_at": created_at,
                        "method": method,
                        "account": account,
                        "net_amount": float(net_amount) if net_amount is not None else None,
                        "currency": currency,
                        "claim": ({
                            "claimed_by": int(claim[0]),
                            "claimed_at": claim[1],
                            "expires_at": claim[2],
                        } if claim else None),
                    })
        items.sort(key=lambda item: (item.get("created_at") or "", item["id"]), reverse=True)
        return jsonify({"ok": True, "items": items}), 200

    @app.post("/api/admin/operations/<operation_type>/<int:operation_id>/claim")
    def admin_operation_claim(operation_type, operation_id):
        user, error = app_session()
        if error:
            return error
        if operation_type not in ("charge", "withdraw"):
            return jsonify({"ok": False, "error": "operation_not_found"}), 404
        permission = operation_permission(operation_type)
        if not (user.get("is_owner") or permissions_for(user["telegram_id"], user["role"]).get(permission, False)):
            return jsonify({"ok": False, "error": "permission_denied"}), 403
        now = _now()
        now_text = _iso(now)
        expires_text = _iso(now + timedelta(minutes=10))
        table = "pending_charges" if operation_type == "charge" else "pending_withdraws"
        with db_lock:
            conn.execute("DELETE FROM admin_operation_claims WHERE expires_at<=?", (now_text,))
            row = conn.execute(f"SELECT status FROM {table} WHERE id=?", (operation_id,)).fetchone()
            if not row:
                return jsonify({"ok": False, "error": "operation_not_found"}), 404
            if row[0] not in ("pending", "processing"):
                return jsonify({"ok": False, "error": "operation_not_open"}), 409
            existing = conn.execute(
                """SELECT claimed_by FROM admin_operation_claims
                   WHERE operation_type=? AND operation_id=? AND expires_at>?""",
                (operation_type, operation_id, now_text),
            ).fetchone()
            if existing and int(existing[0]) != int(user["telegram_id"]):
                return jsonify({"ok": False, "error": "already_claimed"}), 409
            conn.execute(
                """INSERT INTO admin_operation_claims
                   (operation_type, operation_id, claimed_by, claimed_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(operation_type, operation_id) DO UPDATE SET
                   claimed_by=excluded.claimed_by, claimed_at=excluded.claimed_at,
                   expires_at=excluded.expires_at""",
                (operation_type, operation_id, int(user["telegram_id"]), now_text, expires_text),
            )
            conn.commit()
        return jsonify({"ok": True, "claimed_by": int(user["telegram_id"]), "expires_at": expires_text}), 200

    @app.post("/api/admin/operations/<operation_type>/<int:operation_id>/complete")
    def admin_operation_complete(operation_type, operation_id):
        user, error = app_session()
        if error:
            return error
        if operation_type not in ("charge", "withdraw"):
            return jsonify({"ok": False, "error": "operation_not_found"}), 404
        permission = operation_permission(operation_type)
        if not (user.get("is_owner") or permissions_for(user["telegram_id"], user["role"]).get(permission, False)):
            return jsonify({"ok": False, "error": "permission_denied"}), 403
        # Deliberately fail closed: marking a request complete is not the same as
        # performing and verifying the actual provider/balance transaction.
        return jsonify({
            "ok": False,
            "error": "financial_actions_locked",
            "message": "لم يتم تنفيذ أي حركة مالية. يجب ربط واعتماد إجراء مالي حقيقي قبل إغلاق الطلب.",
        }), 423

    @app.get("/api/admin/notifications")
    def admin_get_notification_preferences():
        user, error = app_session()
        if error:
            return error
        with db_lock:
            row = conn.execute(
                "SELECT preferences_json FROM admin_app_preferences WHERE user_id=?",
                (int(user["telegram_id"]),),
            ).fetchone()
        try:
            prefs = json.loads(row[0]) if row else dict(default_preferences)
        except (TypeError, ValueError):
            prefs = dict(default_preferences)
        safe = {key: bool(prefs.get(key, default)) for key, default in default_preferences.items()}
        return jsonify({"ok": True, "preferences": safe, "delivery": "not_configured"}), 200

    @app.put("/api/admin/notifications")
    def admin_save_notification_preferences():
        user, error = app_session()
        if error:
            return error
        payload = request.get_json(silent=True) or {}
        supplied = payload.get("preferences")
        if not isinstance(supplied, dict) or any(key not in default_preferences for key in supplied):
            return jsonify({"ok": False, "error": "invalid_preferences"}), 400
        with db_lock:
            existing = conn.execute(
                "SELECT preferences_json FROM admin_app_preferences WHERE user_id=?",
                (int(user["telegram_id"]),),
            ).fetchone()
            try:
                prefs = json.loads(existing[0]) if existing else dict(default_preferences)
            except (TypeError, ValueError):
                prefs = dict(default_preferences)
            prefs.update({key: bool(value) for key, value in supplied.items()})
            conn.execute(
                """INSERT INTO admin_app_preferences(user_id, preferences_json, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                   preferences_json=excluded.preferences_json, updated_at=excluded.updated_at""",
                (int(user["telegram_id"]), json.dumps(prefs, sort_keys=True), _iso(_now())),
            )
            conn.commit()
        return jsonify({"ok": True, "preferences": prefs, "delivery": "not_configured"}), 200

    app.config["MATAR_ADMIN_AUTH_SESSION"] = authenticated_session
    return issue_link_code_for_user
