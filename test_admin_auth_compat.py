import hashlib
import sqlite3
import threading
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from flask import Flask

from matar_admin_auth import register_admin_auth


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.messages = []

    def message_handler(self, commands):
        def decorate(function):
            for command in commands:
                self.handlers[command] = function
            return function
        return decorate

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


class AdminAuthCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.lock = threading.RLock()
        self.bot = FakeBot()
        register_admin_auth(
            self.app, self.bot, self.conn, self.lock, 42,
            lambda user_id: False,
            lambda user_id, permission: False,
        )

    def tearDown(self):
        self.conn.close()

    def _issue_code(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=42),
            chat=SimpleNamespace(id=42),
        )
        self.bot.handlers["adminapp"](message)
        text = self.bot.messages[-1][1]
        return text.split("الرمز: ", 1)[1].splitlines()[0]

    def test_adminapp_issues_eight_character_code_and_exchange_logs_in(self):
        code = self._issue_code()
        self.assertRegex(code, r"^[A-HJ-NP-Z2-9]{8}$")
        response = self.client.post(
            "/api/admin/pairing/exchange", json={"code": code}
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["token"], payload["access_token"])
        self.assertEqual(payload["user"]["role"], "owner")
        self.assertEqual(payload["user"]["telegram_id"], 42)
        replay = self.client.post(
            "/api/admin/pairing/exchange", json={"code": code}
        )
        self.assertEqual(replay.status_code, 401)

    def test_operations_and_notifications_require_login_and_return_pending_items(self):
        unauthorized = self.client.get("/api/admin/operations")
        self.assertEqual(unauthorized.status_code, 401)

        self.conn.execute("""CREATE TABLE pending_charges (
            id INTEGER PRIMARY KEY, user_id INTEGER, method TEXT, amount REAL,
            status TEXT, created_at TEXT)""")
        self.conn.execute("""CREATE TABLE pending_withdraws (
            id INTEGER PRIMARY KEY, user_id INTEGER, method TEXT, amount REAL,
            net_amount REAL, status TEXT, created_at TEXT)""")
        self.conn.execute(
            "INSERT INTO pending_charges VALUES (1, 77, 'Syriatel', 1000, 'pending', '2026-10-17 07:00:00')"
        )
        self.conn.execute(
            "INSERT INTO pending_withdraws VALUES (2, 88, 'Cash', 500, 450, 'processing', '2026-10-17 07:01:00')"
        )
        self.conn.commit()

        code = self._issue_code()
        login = self.client.post("/api/admin/pairing/exchange", json={"code": code})
        token = login.get_json()["token"]
        headers = {"Authorization": "Bearer " + token}

        response = self.client.get("/api/admin/operations", headers=headers)
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual({item["type"] for item in payload["items"]}, {"charge", "withdraw"})

        notifications = self.client.get("/api/admin/notifications", headers=headers)
        self.assertEqual(notifications.status_code, 200)
        self.assertEqual(notifications.get_json()["count"], 2)

    def test_operations_do_not_expose_rows_to_moderator_without_permissions(self):
        app = Flask(__name__)
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        lock = threading.RLock()
        bot = FakeBot()
        register_admin_auth(app, bot, conn, lock, 42,
                            lambda user_id: user_id == 7,
                            lambda user_id, permission: False)
        client = app.test_client()
        # A moderator cannot be granted owner privileges by supplying a role.
        conn.execute("""CREATE TABLE pending_charges (
            id INTEGER PRIMARY KEY, user_id INTEGER, method TEXT, amount REAL,
            status TEXT, created_at TEXT)""")
        conn.execute("""CREATE TABLE pending_withdraws (
            id INTEGER PRIMARY KEY, user_id INTEGER, method TEXT, amount REAL,
            net_amount REAL, status TEXT, created_at TEXT)""")
        conn.commit()
        code = "ABCDEFGH"
        now = datetime.now(timezone.utc).replace(microsecond=0)
        iso = lambda value: value.isoformat().replace("+00:00", "Z")
        conn.execute(
            """INSERT INTO admin_link_codes
               (user_id, role, code_hash, created_at, expires_at, used)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (7, "moderator", hashlib.sha256(code.encode()).hexdigest(),
             iso(now), iso(now + timedelta(minutes=5))),
        )
        conn.commit()
        login = client.post("/api/admin/pairing/exchange", json={"code": code})
        self.assertEqual(login.status_code, 200)
        token = login.get_json()["token"]
        response = client.get("/api/admin/operations",
                              headers={"Authorization": "Bearer " + token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"], [])
        conn.close()

    def test_legacy_six_digit_link_code_still_works(self):
        code = "055461"
        now = datetime.now(timezone.utc).replace(microsecond=0)
        iso = lambda value: value.isoformat().replace("+00:00", "Z")
        self.conn.execute(
            """INSERT INTO admin_link_codes
               (user_id, role, code_hash, created_at, expires_at, used)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (42, "owner", hashlib.sha256(code.encode()).hexdigest(),
             iso(now), iso(now + timedelta(minutes=5))),
        )
        self.conn.commit()
        response = self.client.post(
            "/api/admin/auth/verify", json={"code": code}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
