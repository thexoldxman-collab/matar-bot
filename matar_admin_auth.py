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


    app.config["MATAR_ADMIN_AUTH_SESSION"] = authenticated_session
    return issue_link_code_for_user
