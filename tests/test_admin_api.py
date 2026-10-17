import os
import re
import tempfile
import unittest
import sqlite3

from flask import Flask
from matar_admin_api import register_admin_api


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.replies = []

    def message_handler(self, commands=None, **kwargs):
        def decorator(func):
            for command in commands or []:
                self.handlers[command] = func
            return func
        return decorator

    def reply_to(self, message, text):
        self.replies.append(text)


class FakeUser:
    def __init__(self, user_id):
        self.id = user_id


class FakeChat:
    type = "private"


class FakeMessage:
    def __init__(self, user_id):
        self.from_user = FakeUser(user_id)
        self.chat = FakeChat()


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(handle)

        def db_factory():
            return sqlite3.connect(self.path, check_same_thread=False)

        db = db_factory()
        db.executescript("""
            CREATE TABLE users(user_id INTEGER PRIMARY KEY, deleted INTEGER DEFAULT 0);
            CREATE TABLE moderators(
                user_id INTEGER PRIMARY KEY, custom_name TEXT, can_reply_tickets INTEGER DEFAULT 0,
                can_handle_charges INTEGER DEFAULT 0, can_handle_withdraws INTEGER DEFAULT 0,
                can_send_broadcast INTEGER DEFAULT 0, can_manage_users INTEGER DEFAULT 0,
                can_charge_withdraw_users INTEGER DEFAULT 0, can_view_stats INTEGER DEFAULT 0,
                can_manage_buttons INTEGER DEFAULT 0, can_access_full_admin INTEGER DEFAULT 0,
                can_manage_moderators INTEGER DEFAULT 0, can_use_ai INTEGER DEFAULT 0, permissions TEXT
            );
            CREATE TABLE pending_charges(id INTEGER PRIMARY KEY, user_id INTEGER, method TEXT, amount REAL, status TEXT, created_at TEXT, processed_by INTEGER);
            CREATE TABLE pending_withdraws(id INTEGER PRIMARY KEY, user_id INTEGER, method TEXT, amount REAL, status TEXT, created_at TEXT, processed_by INTEGER);
        """)
        db.commit()
        db.close()

        self.bot = FakeBot()
        self.app = Flask(__name__)
        self.app.config["TESTING"] = True
        register_admin_api(self.app, self.bot, 123456, db_factory)
        self.client = self.app.test_client()

    def tearDown(self):
        os.unlink(self.path)

    def test_pairing_code_is_one_time_and_returns_owner_session(self):
        self.bot.handlers["adminapp"](FakeMessage(123456))
        code = re.findall(r"\b[A-Z0-9]{8}\b", self.bot.replies[-1])[-1]

        response = self.client.post("/api/admin/pairing/exchange", json={"code": code})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["user"]["role"], "owner")
        token = payload["access_token"]

        me = self.client.get("/api/admin/me", headers={"Authorization": "Bearer " + token})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["user"]["telegram_user_id"], 123456)

        reused = self.client.post("/api/admin/pairing/exchange", json={"code": code})
        self.assertEqual(reused.status_code, 401)

    def test_unknown_telegram_user_cannot_request_pairing_code(self):
        self.bot.handlers["adminapp"](FakeMessage(777777))
        self.assertIn("غير مخوّل", self.bot.replies[-1])

    def _owner_token(self):
        self.bot.handlers["adminapp"](FakeMessage(123456))
        code = re.findall(r"\b[A-Z0-9]{8}\b", self.bot.replies[-1])[-1]
        response = self.client.post("/api/admin/pairing/exchange", json={"code": code})
        return response.get_json()["access_token"]

    def test_operation_claim_is_expiring_and_financial_completion_is_blocked(self):
        db = sqlite3.connect(self.path)
        db.execute(
            "INSERT INTO pending_charges(id,user_id,method,amount,status,created_at,processed_by) VALUES (1,42,'test',100,'pending','2026-01-01',NULL)"
        )
        db.commit()
        db.close()
        token = self._owner_token()
        headers = {"Authorization": "Bearer " + token}

        claimed = self.client.post("/api/admin/operations/charge/1/claim", headers=headers)
        self.assertEqual(claimed.status_code, 200)
        self.assertTrue(claimed.get_json()["claimed"])

        blocked = self.client.post("/api/admin/operations/charge/1/complete", headers=headers)
        self.assertEqual(blocked.status_code, 423)
        self.assertEqual(blocked.get_json()["error"], "financial_workflow_not_integrated")

        db = sqlite3.connect(self.path)
        status = db.execute("SELECT status FROM pending_charges WHERE id=1").fetchone()[0]
        db.close()
        self.assertEqual(status, "pending")

    def test_notification_preferences_require_authenticated_session(self):
        self.assertEqual(self.client.get("/api/admin/notifications").status_code, 401)


if __name__ == "__main__":
    unittest.main()
