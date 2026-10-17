import sqlite3
import unittest
from flask import Flask

from matar_admin_api import register_admin_api


class FakeBot:
    def __init__(self):
        self.sent = []

    def send_message(self, target, message):
        self.sent.append((target, message))


class AdminApiTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = __import__("threading").RLock()
        self.bot = FakeBot()
        self.user = {"telegram_id": 100, "role": "owner", "permissions": {}}
        self.app.config["MATAR_ADMIN_AUTH_SESSION"] = lambda: (self.user, "digest")
        self.conn.executescript("""
            CREATE TABLE users(user_id INTEGER PRIMARY KEY, deleted INTEGER DEFAULT 0, status TEXT DEFAULT 'active', balance REAL DEFAULT 0, last_active TEXT);
            CREATE TABLE pending_charges(id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, method TEXT, status TEXT, created_at TEXT, receipt_number TEXT, processed_by INTEGER, processed_at TEXT);
            CREATE TABLE pending_withdraws(id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, net_amount REAL, method TEXT, status TEXT, created_at TEXT, account TEXT, processed_by INTEGER, processed_at TEXT);
            CREATE TABLE moderators(user_id INTEGER PRIMARY KEY, custom_name TEXT, added_by INTEGER, added_at TEXT,
                can_reply_tickets INTEGER DEFAULT 0, can_handle_charges INTEGER DEFAULT 0,
                can_handle_withdraws INTEGER DEFAULT 0, can_send_broadcast INTEGER DEFAULT 0,
                can_manage_users INTEGER DEFAULT 0, can_charge_withdraw_users INTEGER DEFAULT 0,
                can_view_stats INTEGER DEFAULT 0, can_manage_buttons INTEGER DEFAULT 0,
                can_access_full_admin INTEGER DEFAULT 0, can_manage_moderators INTEGER DEFAULT 0,
                can_use_ai INTEGER DEFAULT 0, permissions TEXT);
            CREATE TABLE tickets(ticket_id INTEGER PRIMARY KEY, status TEXT);
            CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT, description TEXT, type TEXT, updated_at TEXT, updated_by INTEGER);
            CREATE TABLE referrals_log(id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, referred_id INTEGER UNIQUE, joined_at TEXT);
            CREATE TABLE referral_earnings(id INTEGER PRIMARY KEY AUTOINCREMENT, referrer_id INTEGER, theoretical_amount REAL, paid_amount REAL DEFAULT 0, from_user_id INTEGER, transaction_id INTEGER, cycle_start TEXT, cycle_end TEXT, earned_at TEXT, paid_at TEXT, paid_by INTEGER);
            CREATE TABLE referral_cycles(id INTEGER PRIMARY KEY AUTOINCREMENT, start_date TEXT, end_date TEXT, status TEXT DEFAULT 'active', total_theoretical REAL DEFAULT 0, total_paid REAL DEFAULT 0);
            CREATE TABLE cashier_balance(admin_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, last_updated TEXT);
            CREATE TABLE transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, amount REAL, commission REAL, net_amount REAL, method TEXT, status TEXT, transaction_date TEXT, admin_id INTEGER, details TEXT, receipt_number TEXT, external_ref TEXT);
            CREATE TABLE admin_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, display_name TEXT,
                action_type TEXT, details TEXT, target_user INTEGER, amount REAL, created_at TEXT);
            CREATE TABLE dynamic_buttons(id INTEGER PRIMARY KEY, button_name TEXT, button_text TEXT,
                parent_button TEXT, button_type TEXT, action TEXT, message_text TEXT, level INTEGER,
                sort_order INTEGER, is_active INTEGER, requires_subscription INTEGER, requires_admin INTEGER,
                requires_moderator INTEGER, path TEXT, updated_at TEXT);
            INSERT INTO users(user_id,deleted,status,balance) VALUES (200,0,'active',100),(201,1,'active',0);
            INSERT INTO cashier_balance(admin_id,balance,last_updated) VALUES (100,5000,'2026-01-01');
            INSERT INTO referrals_log(referrer_id,referred_id,joined_at) VALUES (200,201,'2026-01-01'),(200,202,'2026-01-02');
            INSERT INTO referral_earnings(referrer_id,theoretical_amount,paid_amount,from_user_id,cycle_start,cycle_end,earned_at) VALUES (200,3000,500,201,'2026-01-01','2026-01-10','2026-01-10');
            INSERT INTO settings(key,value,description,type) VALUES ('referral_percentage','10','نسبة الإحالات','number'),('referral_cycle_days','10','مدة الدورة','number'),('next_referral_payout','2026-11-01','موعد الدفعة','text');
            INSERT INTO referral_cycles(start_date,end_date,status,total_theoretical,total_paid) VALUES ('2026-10-01','2026-11-01','active',3000,500);
            INSERT INTO pending_charges VALUES (1,200,25000,'syriatel','pending','2026-01-01 10:00:00','R-1',NULL,NULL);
            INSERT INTO pending_withdraws VALUES (2,200,10000,9000,'syriatel','pending','2026-01-01 10:01:00','account-1',NULL,NULL);
            INSERT INTO moderators(user_id,custom_name,added_by,added_at) VALUES (300,'مشرف اختبار',100,'2026-01-01');
            INSERT INTO tickets(ticket_id,status) VALUES (1,'open');
            INSERT INTO dynamic_buttons VALUES (1,'welcome','أهلاً','main','reply','welcome','رسالة ترحيب',1,0,1,0,0,0,'/',NULL);
        """)
        self.conn.commit()
        self.permissions = {}
        register_admin_api(self.app, self.bot, self.conn, self.lock, 100,
                           lambda uid, key: self.permissions.get((uid, key), False))
        self.client = self.app.test_client()

    def tearDown(self):
        self.conn.close()

    def test_my_permissions_are_derived_from_current_server_records(self):
        self.user = {"telegram_id": 101, "role": "moderator", "permissions": {}}
        self.permissions[(101, "can_send_broadcast")] = True
        response = self.client.get("/api/admin/my-permissions")
        self.assertEqual(response.status_code, 200)
        permissions = response.get_json()["permissions"]
        self.assertTrue(permissions["can_send_broadcast"])
        self.assertFalse(permissions["can_manage_moderators"])

    def test_operations_claim_is_exclusive_and_releasable(self):
        response = self.client.get("/api/admin/operations")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        self.assertEqual({(x["type"], x["id"]) for x in items}, {("charge", 1), ("withdraw", 2)})

        response = self.client.post("/api/admin/operations/charge/1/claim")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["claimed_by"], 100)

        self.user = {"telegram_id": 101, "role": "moderator", "permissions": {}}
        self.permissions[(101, "can_handle_charges")] = True
        response = self.client.post("/api/admin/operations/charge/1/claim")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "already_claimed")

        self.user = {"telegram_id": 100, "role": "owner", "permissions": {}}
        response = self.client.post("/api/admin/operations/charge/1/release")
        self.assertEqual(response.status_code, 200)

    def test_financial_completion_is_never_faked(self):
        response = self.client.post("/api/admin/operations/charge/1/complete")
        self.assertEqual(response.status_code, 423)
        self.assertEqual(response.get_json()["error"], "financial_execution_disabled")
        status = self.conn.execute("SELECT status FROM pending_charges WHERE id=1").fetchone()[0]
        self.assertEqual(status, "pending")

    def test_notification_preferences_round_trip(self):
        response = self.client.put("/api/admin/notifications", json={
            "preferences": {"charge_new": False, "withdraw_new": True}
        })
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/api/admin/notifications")
        self.assertEqual(response.status_code, 200)
        prefs = response.get_json()["preferences"]
        self.assertFalse(prefs["charge_new"])
        self.assertTrue(prefs["withdraw_new"])

    def test_moderator_permissions_are_server_managed(self):
        response = self.client.get("/api/admin/moderators")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["items"][0]["user_id"], 300)
        response = self.client.post("/api/admin/moderators", json={
            "user_id": 301, "custom_name": "مشرف جديد",
            "permissions": {"can_handle_charges": True, "can_handle_withdraws": False}
        })
        self.assertEqual(response.status_code, 201)
        row = self.conn.execute("SELECT can_handle_charges,can_handle_withdraws FROM moderators WHERE user_id=301").fetchone()
        self.assertEqual(tuple(row), (1, 0))

    def test_referral_settings_and_payout_remain_safe(self):
        summary = self.client.get("/api/admin/referrals")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.get_json()["data"]["total_referrals"], 2)
        self.assertEqual(summary.get_json()["data"]["unpaid_total"], 2500)

        response = self.client.put("/api/admin/referrals/settings", json={
            "percentage": 12.5, "cycle_days": 10, "next_payout": "2026-11-15"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.conn.execute("SELECT value FROM settings WHERE key='referral_percentage'").fetchone()[0], "12.5")

        # Even if an environment variable is mistakenly set, the mobile API
        # cannot pay referral earnings until a reviewed atomic handler is wired.
        from unittest.mock import patch
        before_user = self.conn.execute("SELECT balance FROM users WHERE user_id=200").fetchone()[0]
        before_cashier = self.conn.execute("SELECT balance FROM cashier_balance WHERE admin_id=100").fetchone()[0]
        with patch.dict("os.environ", {"ADMIN_APP_FINANCIAL_EXECUTION_ENABLED": "1"}):
            response = self.client.post("/api/admin/referrals/payout", json={"user_id": 200, "amount": 1000})
        self.assertEqual(response.status_code, 423)
        self.assertEqual(self.conn.execute("SELECT balance FROM users WHERE user_id=200").fetchone()[0], before_user)
        self.assertEqual(self.conn.execute("SELECT balance FROM cashier_balance WHERE admin_id=100").fetchone()[0], before_cashier)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM transactions WHERE type='referral_pay'").fetchone()[0], 0)

    def test_referral_payout_is_blocked_without_live_switch(self):
        response = self.client.post("/api/admin/referrals/payout", json={"user_id": 200, "amount": 100})
        self.assertEqual(response.status_code, 423)
        self.assertEqual(self.conn.execute("SELECT balance FROM users WHERE user_id=200").fetchone()[0], 100)

    def test_content_settings_update_welcome_and_subscription_gate(self):
        response = self.client.get("/api/admin/content")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["content"]["force_subscription"])

        response = self.client.put("/api/admin/content", json={
            "welcome_message": "أهلاً من التطبيق",
            "subscription_message": "اشترك أولاً",
            "required_channel": "@Matar_TestChannel",
            "force_subscription": False
        })
        self.assertEqual(response.status_code, 200)
        values = {row[0]: row[1] for row in self.conn.execute("SELECT key,value FROM settings").fetchall()}
        self.assertEqual(values["welcome_message"], "أهلاً من التطبيق")
        self.assertEqual(values["required_channel"], "@Matar_TestChannel")
        self.assertEqual(values["force_subscription"], "0")

        response = self.client.put("/api/admin/content", json={"required_channel": "not a channel"})
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_requests_are_rejected(self):
        self.app.config["MATAR_ADMIN_AUTH_SESSION"] = lambda: None
        response = self.client.get("/api/admin/operations")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
