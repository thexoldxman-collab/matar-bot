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
