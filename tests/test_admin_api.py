import re
import sqlite3
import threading
import unittest
from types import SimpleNamespace

from flask import Flask

from matar_admin_auth import register_admin_auth
from matar_admin_api import register_admin_api


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
        return SimpleNamespace(message_id=len(self.messages))


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.lock = threading.RLock()
        self.bot = FakeBot()
        self.app = Flask(__name__)
        self.owner = 1001
        self.calls = []
        self.conn.executescript("""
            CREATE TABLE users(user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, custom_name TEXT,
                acc_name TEXT, status TEXT, created_at TEXT, balance REAL DEFAULT 0, site_balance REAL DEFAULT 0,
                ref_code TEXT, referred_by INTEGER, referral_count INTEGER DEFAULT 0, current_earnings REAL DEFAULT 0,
                total_earnings REAL DEFAULT 0, last_active TEXT, deleted INTEGER DEFAULT 0);
            CREATE TABLE transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount REAL,
                commission REAL, net_amount REAL, method TEXT, status TEXT, transaction_date TEXT, admin_id INTEGER,
                details TEXT, receipt_number TEXT);
            CREATE TABLE pending_charges(id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, method TEXT, status TEXT,
                created_at TEXT, receipt_number TEXT, processed_by INTEGER, processed_at TEXT);
            CREATE TABLE pending_withdraws(id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, net_amount REAL,
                method TEXT, status TEXT, created_at TEXT, account TEXT, processed_by INTEGER, processed_at TEXT);
            CREATE TABLE moderators(user_id INTEGER PRIMARY KEY);
            CREATE TABLE tickets(ticket_id INTEGER PRIMARY KEY, status TEXT);
            CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT, description TEXT, type TEXT, updated_at TEXT, updated_by INTEGER);
            CREATE TABLE ai_settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE ai_conversations(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT, content TEXT, created_at TEXT);
            CREATE TABLE admin_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, display_name TEXT, action_type TEXT,
                details TEXT, target_user INTEGER, amount REAL, created_at TEXT);
            CREATE TABLE api_configs(id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, is_active INTEGER, is_paused INTEGER,
                connection_status TEXT, last_verified TEXT);
            CREATE TABLE wheel_prizes(id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, prize_type TEXT, value REAL,
                weight REAL, is_active INTEGER, created_at TEXT, updated_at TEXT);
            INSERT INTO users VALUES(9001,'Ali','ali','', '', 'active','2026-01-01',100,20,'REF',NULL,0,0,0,'',0);
            INSERT INTO settings(key,value,description,type) VALUES
                ('syriatel_status','متوقف','','status'),('sham_status','متوقف','','status'),('usdt_status','متوقف','','status'),
                ('binance_status','متوقف','','status'),('wheel_enabled','0','','boolean'),('wheel_daily_charge_threshold','100000','','number'),
                ('wheel_title','عجلة','','text'),('wheel_spin_message','اضغط','','text');
            INSERT INTO ai_settings(key,value) VALUES('enabled','1');
        """)
        register_admin_auth(self.app, self.bot, self.conn, self.lock, self.owner, lambda uid: False, lambda uid, p: False)
        self.adjust_count = 0

        def adjust(target, amount, action, actor):
            self.adjust_count += 1
            self.conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, target))
            self.conn.commit()
            return 100 + amount, "ADM-1"

        register_admin_api(self.app, self.bot, self.conn, self.lock, self.owner, lambda uid, p: False,
                           adjust_balance=adjust, assistant_ask=lambda uid, prompt: ("تحليل آمن", None))
        self.client = self.app.test_client()

    def tearDown(self):
        self.conn.close()

    def login(self):
        message = SimpleNamespace(from_user=SimpleNamespace(id=self.owner), chat=SimpleNamespace(id=self.owner))
        self.bot.handlers["link"](message)
        code = re.search(r"رمز:\s*([A-HJ-NP-Z2-9]{8})", self.bot.messages[-1][1]).group(1)
        response = self.client.post("/api/admin/auth/verify", json={"code": code})
        return response.get_json()["access_token"]

    def headers(self):
        return {"Authorization": "Bearer " + self.login()}

    def test_user_list_and_detail_are_read_only(self):
        headers = self.headers()
        response = self.client.get("/api/admin/users?search=9001", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"][0]["user_id"], 9001)
        detail = self.client.get("/api/admin/users/9001", headers=headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["user"]["balance"], 100)

    def test_balance_adjustment_is_idempotent(self):
        headers = self.headers()
        payload = {"action": "bot_charge", "amount": 25, "idempotency_key": "same-key-001"}
        first = self.client.post("/api/admin/users/9001/balance", json=payload, headers=headers)
        second = self.client.post("/api/admin/users/9001/balance", json=payload, headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.get_json()["replayed"] is False)
        self.assertEqual(self.adjust_count, 1)
        self.assertEqual(self.conn.execute("SELECT balance FROM users WHERE user_id=9001").fetchone()[0], 125)

    def test_wheel_prize_and_service_controls(self):
        headers = self.headers()
        created = self.client.post("/api/admin/wheel/prizes", json={"label": "5000", "type": "fixed", "value": 5000, "weight": 2}, headers=headers)
        self.assertEqual(created.status_code, 201)
        listing = self.client.get("/api/admin/wheel", headers=headers)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.get_json()["prizes"][0]["label"], "5000")
        updated = self.client.put("/api/admin/services", json={"syriatel_status": "active"}, headers=headers)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.conn.execute("SELECT value FROM settings WHERE key='syriatel_status'").fetchone()[0], "active")

    def test_assistant_route_is_not_an_execution_route(self):
        response = self.client.post("/api/admin/assistant/ask", json={"prompt": "حلل حالة البوت"}, headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["executed"])


if __name__ == "__main__":
    unittest.main()
