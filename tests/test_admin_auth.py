import re
import sqlite3
import threading
import unittest
from types import SimpleNamespace

from flask import Flask

from matar_admin_auth import register_admin_auth
from matar_db import translate_sql


class FakeBot:
    def __init__(self):
        self.handlers = {}
        self.messages = []

    def message_handler(self, commands=None, **kwargs):
        command = (commands or [None])[0]
        def decorate(function):
            self.handlers[command] = function
            return function
        return decorate

    def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))


class AdminAuthTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.lock = threading.RLock()
        self.bot = FakeBot()
        self.app = Flask(__name__)
        self.moderators = {2002}
        register_admin_auth(
            self.app,
            self.bot,
            self.conn,
            self.lock,
            1001,
            lambda uid: uid in self.moderators,
            lambda uid, permission: uid == 2002 and permission == "can_view_stats",
        )
        self.conn.executescript("""
            CREATE TABLE pending_charges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, method TEXT, receipt_number TEXT, amount REAL,
                syriatel_code TEXT, status TEXT DEFAULT 'pending', created_at TEXT,
                processed_by INTEGER, processed_at TEXT, notification_msg_id INTEGER,
                txn_receipt TEXT
            );
            CREATE TABLE pending_withdraws (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, method TEXT, account TEXT, amount REAL,
                commission REAL, net_amount REAL, currency TEXT DEFAULT 'ليرة سورية',
                status TEXT DEFAULT 'pending', created_at TEXT, processed_by INTEGER,
                processed_at TEXT, notification_msg_id INTEGER, txn_receipt TEXT,
                reserved INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO pending_charges(user_id,method,receipt_number,amount,status,created_at)
            VALUES (3003,'syriatel','receipt-1',25000,'pending','2026-10-17T04:00:00Z');
            INSERT INTO pending_withdraws(user_id,method,account,amount,commission,net_amount,status,created_at)
            VALUES (3004,'sham','account-1',10000,500,9500,'pending','2026-10-17T04:01:00Z');
        """)
        self.conn.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        self.conn.close()

    def issue_code(self, user_id):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=user_id),
            chat=SimpleNamespace(id=user_id),
        )
        self.bot.handlers["link"](message)
        return re.search(r"رمز:\s*(\d{6})", self.bot.messages[-1][1]).group(1)

    def test_owner_code_is_single_use_and_session_can_logout(self):
        code = self.issue_code(1001)
        response = self.client.post("/api/admin/auth/verify", json={"code": code})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["user"]["role"], "owner")
        self.assertTrue(data["user"]["is_owner"])
        token = data["access_token"]

        second_use = self.client.post("/api/admin/auth/verify", json={"code": code})
        self.assertEqual(second_use.status_code, 401)

        me = self.client.get(
            "/api/admin/auth/me",
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["user"]["role"], "owner")

        logout = self.client.post(
            "/api/admin/auth/logout",
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(logout.status_code, 200)
        after_logout = self.client.get(
            "/api/admin/auth/me",
            headers={"Authorization": "Bearer " + token},
        )
        self.assertEqual(after_logout.status_code, 401)

    def test_moderator_role_and_permissions_are_server_derived(self):
        code = self.issue_code(2002)
        response = self.client.post("/api/admin/auth/verify", json={"code": code})
        self.assertEqual(response.status_code, 200)
        user = response.get_json()["user"]
        self.assertEqual(user["role"], "moderator")
        self.assertFalse(user["is_owner"])
        self.assertTrue(user["permissions"]["can_view_stats"])
        self.assertFalse(user["permissions"]["can_manage_users"])

    def test_non_admin_cannot_request_link_code(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=9999),
            chat=SimpleNamespace(id=9999),
        )
        self.bot.handlers["link"](message)
        self.assertIn("غير", self.bot.messages[-1][1])
        count = self.conn.execute("SELECT COUNT(*) FROM admin_link_codes").fetchone()[0]
        self.assertEqual(count, 0)


    def test_owner_can_load_and_claim_operations_but_completion_stays_locked(self):
        code = self.issue_code(1001)
        login = self.client.post("/api/admin/auth/verify", json={"code": code}).get_json()
        headers = {"Authorization": "Bearer " + login["access_token"]}

        listed = self.client.get("/api/admin/operations", headers=headers)
        self.assertEqual(listed.status_code, 200)
        items = listed.get_json()["items"]
        self.assertEqual({item["type"] for item in items}, {"charge", "withdraw"})

        claimed = self.client.post("/api/admin/operations/charge/1/claim", json={}, headers=headers)
        self.assertEqual(claimed.status_code, 200)
        self.assertIn("expires_at", claimed.get_json())

        completed = self.client.post("/api/admin/operations/charge/1/complete", json={}, headers=headers)
        self.assertEqual(completed.status_code, 423)
        self.assertEqual(completed.get_json()["error"], "financial_actions_locked")
        status = self.conn.execute("SELECT status FROM pending_charges WHERE id=1").fetchone()[0]
        self.assertEqual(status, "pending")

    def test_moderator_cannot_claim_financial_queue_without_permission(self):
        code = self.issue_code(2002)
        login = self.client.post("/api/admin/auth/verify", json={"code": code}).get_json()
        headers = {"Authorization": "Bearer " + login["access_token"]}
        response = self.client.post("/api/admin/operations/charge/1/claim", json={}, headers=headers)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "permission_denied")

    def test_notification_preferences_are_persisted_per_account(self):
        code = self.issue_code(1001)
        login = self.client.post("/api/admin/auth/verify", json={"code": code}).get_json()
        headers = {"Authorization": "Bearer " + login["access_token"]}
        saved = self.client.put(
            "/api/admin/notifications",
            json={"preferences": {"charge_new": False, "ai_decisions": True}},
            headers=headers,
        )
        self.assertEqual(saved.status_code, 200)
        loaded = self.client.get("/api/admin/notifications", headers=headers)
        self.assertEqual(loaded.status_code, 200)
        prefs = loaded.get_json()["preferences"]
        self.assertFalse(prefs["charge_new"])
        self.assertTrue(prefs["ai_decisions"])
        self.assertTrue(prefs["withdraw_new"])

    def test_sqlite_begin_immediate_is_translated_for_postgres(self):
        self.assertEqual(translate_sql("BEGIN IMMEDIATE"), ("BEGIN", None))


if __name__ == "__main__":
    unittest.main()
