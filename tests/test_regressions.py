import importlib.util
import os
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ.pop('DATABASE_URL', None)
        os.environ.pop('REAL_DATABASE_URL', None)
        os.environ.pop('REQUIRE_PERSISTENT_DATABASE', None)
        os.environ.update({
            'TOKEN': '123456:TESTTOKEN',
            'ADMIN_ID': '999999',
            'DATABASE_PATH': os.path.join(cls.tmp.name, 'test.db'),
            'BACKUP_DIR': os.path.join(cls.tmp.name, 'backups'),
            'LOG_DIR': os.path.join(cls.tmp.name, 'logs'),
        })
        spec = importlib.util.spec_from_file_location('matar_regression', os.path.join(os.path.dirname(__file__), '..', 'Matar-bot-FINAL-merged.py'))
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fake_call(self, data):
        return SimpleNamespace(
            id='callback-1',
            data=data,
            from_user=SimpleNamespace(id=self.m.ADMIN_ID),
            message=SimpleNamespace(chat=SimpleNamespace(id=self.m.ADMIN_ID), message_id=1),
        )

    def test_button_actions_callback_responds(self):
        m = self.m
        with patch.object(m.bot, 'answer_callback_query') as answer, \
             patch.object(m.bot, 'edit_message_text') as edit:
            m.handle_all_callbacks(self.fake_call('button_management_actions'))
        self.assertGreaterEqual(answer.call_count, 1)
        edit.assert_called_once()

    def test_button_actions_continue_when_telegram_ack_fails(self):
        m = self.m
        with patch.object(m.bot, 'answer_callback_query', side_effect=RuntimeError('stale callback')), \
             patch.object(m.bot, 'edit_message_text') as edit:
            m.handle_all_callbacks(self.fake_call('button_management_actions'))
        edit.assert_called_once()

    def test_button_tree_callback_responds_and_contains_child(self):
        m = self.m
        m.add_new_button('جذر اختبار', action='show_balance', parent='main', admin_id=m.ADMIN_ID)
        m.add_new_button('فرع اختبار', action='show_terms', parent='جذر اختبار', level=2, admin_id=m.ADMIN_ID)
        sent = []
        with patch.object(m.bot, 'answer_callback_query'), \
             patch.object(m.bot, 'send_message', side_effect=lambda *a, **kw: sent.append((a, kw))):
            m.handle_all_callbacks(self.fake_call('list_buttons'))
        self.assertTrue(sent)
        self.assertIn('جذر اختبار', sent[-1][0][1])
        self.assertIn('فرع اختبار', sent[-1][0][1])
        self.assertEqual(sent[-1][1].get('parse_mode'), '')

    def test_button_tree_plain_text_handles_markdown_characters(self):
        m = self.m
        m.add_new_button('اسم_يحوي*محارف[خاصة]', action='show_balance', parent='main', admin_id=m.ADMIN_ID)
        sent = []
        with patch.object(m.bot, 'answer_callback_query'), \
             patch.object(m.bot, 'send_message', side_effect=lambda *a, **kw: sent.append((a, kw))):
            m.handle_all_callbacks(self.fake_call('list_buttons'))
        self.assertTrue(sent)
        self.assertEqual(sent[-1][1].get('parse_mode'), '')
        self.assertLessEqual(len(sent[-1][0][1]), 4096)

    def test_reset_user_state_clears_every_transient_mode(self):
        m = self.m
        uid = 12345
        m.user_states[uid] = {'pending': True}
        m.user_mode[uid] = 'ai_chat'
        m.user_section[uid] = 'button_management'
        m.withdraw_sessions[uid] = {'amount': 100}
        with patch.object(m.bot, 'clear_step_handler_by_chat_id'):
            m.reset_user_state(uid)
        self.assertNotIn(uid, m.user_states)
        self.assertNotIn(uid, m.user_mode)
        self.assertNotIn(uid, m.user_section)
        self.assertNotIn(uid, m.withdraw_sessions)

    def test_disabled_ai_never_captures_followup_messages(self):
        m = self.m
        uid = m.ADMIN_ID
        m.GEMINI_API_KEY = ''
        m.user_mode[uid] = 'button_management'
        with patch.object(m.bot, 'send_message') as send:
            m.start_ai_chat(uid, uid)
        self.assertNotEqual(m.user_mode.get(uid), m.AI_CHAT_STATE)
        send.assert_called_once()

    def test_database_migration_has_ai_permission_column(self):
        columns = {row[1] for row in self.m.cursor.execute('PRAGMA table_info(moderators)').fetchall()}
        self.assertIn('can_use_ai', columns)

    def test_account_name_is_random_unique_and_sanitized(self):
        m = self.m
        first = m.generate_unique_account_name('ali')
        self.assertRegex(first, r'^ali_[a-z0-9]{6}$')
        m.cursor.execute(
            "INSERT INTO users(user_id, acc_name, balance, site_balance, deleted) VALUES (?,?,?,?,?)",
            (810001, first, 10, 20, 0),
        )
        m.conn.commit()
        second = m.generate_unique_account_name('ali')
        self.assertRegex(second, r'^ali_[a-z0-9]{6}$')
        self.assertNotEqual(first, second)

    def test_account_creation_preserves_existing_balances(self):
        m = self.m
        uid = 810002
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, acc_name, acc_password, balance, site_balance, deleted, created_at) VALUES (?,?,?,?,?,?,?)",
            (uid, None, None, 12345, 67890, 0, '2026-01-01 00:00:00'),
        )
        m.conn.commit()
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=uid),
            chat=SimpleNamespace(id=uid),
            text='new-password',
        )
        with patch.object(m.bot, 'send_message'), \
             patch.object(m.bot, 'register_next_step_handler'), \
             patch.object(m.notifier, 'notify_new_user'), \
             patch.object(m.ActionSystem, 'show_ichancy_account'):
            m.ActionSystem.process_account_password(message, 'ali_ab12cd')
        row = m.cursor.execute(
            "SELECT acc_name, acc_password, balance, site_balance, created_at FROM users WHERE user_id=?",
            (uid,),
        ).fetchone()
        self.assertEqual(row, ('ali_ab12cd', 'new-password', 12345.0, 67890.0, '2026-01-01 00:00:00'))

    def test_existing_account_cannot_be_overwritten_by_create_flow(self):
        m = self.m
        uid = 810003
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, acc_name, acc_password, balance, site_balance, deleted) VALUES (?,?,?,?,?,?)",
            (uid, 'old_name_x1', 'old-pass', 99, 88, 0),
        )
        m.conn.commit()
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=uid),
            chat=SimpleNamespace(id=uid),
            text='new-password',
        )
        with patch.object(m.bot, 'send_message') as send, \
             patch.object(m.ActionSystem, 'show_ichancy_account'):
            m.ActionSystem.process_account_password(message, 'new_name_y2')
        row = m.cursor.execute(
            "SELECT acc_name, acc_password, balance, site_balance FROM users WHERE user_id=?",
            (uid,),
        ).fetchone()
        self.assertEqual(row, ('old_name_x1', 'old-pass', 99.0, 88.0))
        self.assertTrue(any('موجود مسبقاً' in str(call.args[1]) for call in send.call_args_list))

    def test_account_creation_creates_missing_user_row_and_verifies_save(self):
        m = self.m
        uid = 810004
        m.cursor.execute("DELETE FROM users WHERE user_id=?", (uid,))
        m.conn.commit()
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=uid, first_name='New', username='new_user'),
            chat=SimpleNamespace(id=uid),
            text='new-password',
        )
        with patch.object(m.bot, 'send_message'), \
             patch.object(m.bot, 'register_next_step_handler'), \
             patch.object(m.notifier, 'notify_new_user'), \
             patch.object(m.ActionSystem, 'show_ichancy_account'):
            m.ActionSystem.process_account_password(message, 'new_ab12cd')
        row = m.cursor.execute(
            "SELECT first_name, username, acc_name, acc_password, balance, site_balance, deleted FROM users WHERE user_id=?",
            (uid,),
        ).fetchone()
        self.assertEqual(row, ('New', 'new_user', 'new_ab12cd', 'new-password', 0.0, 0.0, 0))

    def test_referral_payout_updates_balance_cashier_and_ledger_atomically(self):
        m = self.m
        uid = 810005
        old_cashier = m.cursor.execute(
            "SELECT balance,last_updated FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)
        ).fetchone()
        m.cursor.execute(
            "UPDATE cashier_balance SET balance=1000,last_updated='2026-10-15 00:00:00' WHERE admin_id=?",
            (m.ADMIN_ID,),
        )
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, deleted) VALUES (?,?,0)",
            (uid, 100.0),
        )
        m.conn.commit()
        try:
            new_balance, receipt = m.credit_referral_payout_atomic(uid, 25, m.ADMIN_ID)
            row = m.cursor.execute(
                "SELECT balance FROM users WHERE user_id=?", (uid,)
            ).fetchone()
            cashier_balance = m.cursor.execute(
                "SELECT balance FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)
            ).fetchone()[0]
            ledger = m.cursor.execute(
                "SELECT type, amount, status, receipt_number, method FROM transactions WHERE receipt_number=?",
                (receipt,),
            ).fetchone()
            self.assertEqual(new_balance, 125.0)
            self.assertEqual(row[0], 125.0)
            self.assertEqual(cashier_balance, 975.0)
            self.assertEqual(ledger, ('referral_pay', 25.0, 'success', receipt, 'cashier'))
        finally:
            if old_cashier:
                m.cursor.execute(
                    "UPDATE cashier_balance SET balance=?,last_updated=? WHERE admin_id=?",
                    (old_cashier[0], old_cashier[1], m.ADMIN_ID),
                )
            m.cursor.execute("DELETE FROM users WHERE user_id=?", (uid,))
            m.conn.commit()

    def test_referral_payout_rolls_back_user_and_cashier_if_ledger_insert_fails(self):
        m = self.m
        uid = 810006
        old_cashier = m.cursor.execute(
            "SELECT balance,last_updated FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)
        ).fetchone()
        m.cursor.execute(
            "UPDATE cashier_balance SET balance=1000,last_updated='2026-10-15 00:00:00' WHERE admin_id=?",
            (m.ADMIN_ID,),
        )
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, deleted) VALUES (?,?,0)",
            (uid, 100.0),
        )
        m.conn.commit()
        m.cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS test_fail_referral_ledger
            BEFORE INSERT ON transactions
            WHEN NEW.type='referral_pay'
            BEGIN SELECT RAISE(ABORT, 'forced test failure'); END
        """)
        m.conn.commit()
        try:
            with self.assertRaises(Exception):
                m.credit_referral_payout_atomic(uid, 25, m.ADMIN_ID)
            balance = m.cursor.execute(
                "SELECT balance FROM users WHERE user_id=?", (uid,)
            ).fetchone()[0]
            cashier_balance = m.cursor.execute(
                "SELECT balance FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)
            ).fetchone()[0]
            self.assertEqual(balance, 100.0)
            self.assertEqual(cashier_balance, 1000.0)
        finally:
            m.cursor.execute("DROP TRIGGER IF EXISTS test_fail_referral_ledger")
            if old_cashier:
                m.cursor.execute(
                    "UPDATE cashier_balance SET balance=?,last_updated=? WHERE admin_id=?",
                    (old_cashier[0], old_cashier[1], m.ADMIN_ID),
                )
            m.cursor.execute("DELETE FROM users WHERE user_id=?", (uid,))
            m.conn.commit()

    def test_referral_payout_refuses_when_cashier_funds_are_insufficient(self):
        m = self.m
        uid = 810024
        old_cashier = m.cursor.execute(
            "SELECT balance,last_updated FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)
        ).fetchone()
        m.cursor.execute(
            "UPDATE cashier_balance SET balance=5,last_updated='2026-10-15 00:00:00' WHERE admin_id=?",
            (m.ADMIN_ID,),
        )
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id,balance,deleted) VALUES (?,?,0)",
            (uid, 100.0),
        )
        m.conn.commit()
        try:
            with self.assertRaises(ValueError):
                m.credit_referral_payout_atomic(uid, 25, m.ADMIN_ID)
            self.assertEqual(
                m.cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0],
                100.0,
            )
            self.assertEqual(
                m.cursor.execute("SELECT balance FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)).fetchone()[0],
                5.0,
            )
            self.assertFalse(m.cursor.execute(
                "SELECT 1 FROM transactions WHERE user_id=? AND type='referral_pay'", (uid,)
            ).fetchone())
        finally:
            if old_cashier:
                m.cursor.execute(
                    "UPDATE cashier_balance SET balance=?,last_updated=? WHERE admin_id=?",
                    (old_cashier[0], old_cashier[1], m.ADMIN_ID),
                )
            m.cursor.execute("DELETE FROM users WHERE user_id=?", (uid,))
            m.conn.commit()

    def test_referral_payout_rejects_nonfinite_and_nonpositive_amounts(self):
        m = self.m
        for amount in (0, -1, float('nan'), float('inf')):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    m.credit_referral_payout_atomic(810005, amount, m.ADMIN_ID)

    def test_internal_ichancy_transfer_updates_balances_and_ledger_atomically(self):
        m = self.m
        uid = 810007
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, site_balance, deleted) VALUES (?,?,?,0)",
            (uid, 100.0, 20.0),
        )
        m.conn.commit()

        balances = m.transfer_internal_balance(uid, 30, 'to_site')
        self.assertEqual(balances, (70.0, 50.0))
        charge = m.cursor.execute(
            "SELECT type, amount, method, status FROM transactions WHERE user_id=? AND type='ichancy_charge'",
            (uid,),
        ).fetchone()
        self.assertEqual(charge, ('ichancy_charge', 30.0, 'internal', 'success'))

        balances = m.transfer_internal_balance(uid, 15, 'to_bot')
        self.assertEqual(balances, (85.0, 35.0))
        withdraw = m.cursor.execute(
            "SELECT type, amount, method, status FROM transactions WHERE user_id=? AND type='ichancy_withdraw'",
            (uid,),
        ).fetchone()
        self.assertEqual(withdraw, ('ichancy_withdraw', 15.0, 'internal', 'success'))

    def test_internal_ichancy_transfer_rolls_back_balances_if_ledger_insert_fails(self):
        m = self.m
        uid = 810008
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, site_balance, deleted) VALUES (?,?,?,0)",
            (uid, 100.0, 20.0),
        )
        m.cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS test_fail_ichancy_ledger
            BEFORE INSERT ON transactions
            WHEN NEW.type IN ('ichancy_charge', 'ichancy_withdraw')
            BEGIN SELECT RAISE(ABORT, 'forced test failure'); END
        """)
        m.conn.commit()
        try:
            with self.assertRaises(Exception):
                m.transfer_internal_balance(uid, 30, 'to_site')
            balances = m.cursor.execute(
                "SELECT balance, site_balance FROM users WHERE user_id=?", (uid,)
            ).fetchone()
            self.assertEqual(balances, (100.0, 20.0))
        finally:
            m.cursor.execute("DROP TRIGGER IF EXISTS test_fail_ichancy_ledger")
            m.conn.commit()


    def test_admin_balance_actions_update_ledger_atomically(self):
        m = self.m
        uid = 810009
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, site_balance, deleted) VALUES (?,?,?,0)",
            (uid, 100.0, 40.0),
        )
        m.conn.commit()

        self.assertEqual(m.admin_adjust_balance_atomic(uid, 20, "bot_charge", m.ADMIN_ID)[0], 120.0)
        self.assertEqual(m.admin_adjust_balance_atomic(uid, 10, "site_charge", m.ADMIN_ID)[0], 50.0)
        self.assertEqual(m.admin_adjust_balance_atomic(uid, 30, "bot_withdraw", m.ADMIN_ID)[0], 90.0)
        self.assertEqual(m.admin_adjust_balance_atomic(uid, 15, "site_withdraw", m.ADMIN_ID)[0], 35.0)

        balances = m.cursor.execute(
            "SELECT balance, site_balance FROM users WHERE user_id=?", (uid,)
        ).fetchone()
        self.assertEqual(balances, (105.0, 35.0))
        types_found = {
            row[0] for row in m.cursor.execute(
                "SELECT type FROM transactions WHERE user_id=? AND type IN "
                "('admin_charge','admin_site_charge','admin_withdraw','admin_site_withdraw')",
                (uid,),
            ).fetchall()
        }
        self.assertEqual(types_found, {
            "admin_charge", "admin_site_charge", "admin_withdraw", "admin_site_withdraw"
        })

    def test_admin_withdraw_rolls_back_user_and_cashier_if_ledger_fails(self):
        m = self.m
        uid = 810010
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, site_balance, deleted) VALUES (?,?,?,0)",
            (uid, 100.0, 0.0),
        )
        before = m.cursor.execute(
            "SELECT balance FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)
        ).fetchone()[0]
        m.cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS test_fail_admin_withdraw_ledger
            BEFORE INSERT ON transactions
            WHEN NEW.type='admin_withdraw'
            BEGIN SELECT RAISE(ABORT, 'forced test failure'); END
        """)
        m.conn.commit()
        try:
            with self.assertRaises(Exception):
                m.admin_adjust_balance_atomic(uid, 25, "bot_withdraw", m.ADMIN_ID)
            balance = m.cursor.execute(
                "SELECT balance FROM users WHERE user_id=?", (uid,)
            ).fetchone()[0]
            after = m.cursor.execute(
                "SELECT balance FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)
            ).fetchone()[0]
            self.assertEqual(balance, 100.0)
            self.assertEqual(after, before)
        finally:
            m.cursor.execute("DROP TRIGGER IF EXISTS test_fail_admin_withdraw_ledger")
            m.conn.commit()


    def test_charge_completion_rejects_other_claimant_without_crediting(self):
        m = self.m
        uid = 810011
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, site_balance, deleted) VALUES (?,?,?,0)",
            (uid, 50.0, 0.0),
        )
        m.cursor.execute(
            "INSERT INTO pending_charges(user_id, method, receipt_number, amount, status, created_at, processed_by) "
            "VALUES (?,?,?,?,?,?,?)",
            (uid, 'test', 'CLAIM-810011', 10.0, 'processing', '2026-10-15 00:00:00', 555551),
        )
        charge_id = m.cursor.lastrowid
        m.conn.commit()

        result, status = m.complete_pending_charge(charge_id, 555552, 10)
        balance = m.cursor.execute(
            "SELECT balance FROM users WHERE user_id=?", (uid,)
        ).fetchone()[0]
        self.assertIsNone(result)
        self.assertEqual(status, 'claimed_by_other')
        self.assertEqual(balance, 50.0)

    def test_auto_verification_cannot_be_enabled_without_a_verified_provider(self):
        m = self.m
        previous = m.get_db_setting('auto_verify_charges')
        try:
            m.update_db_setting('auto_verify_charges', '1', m.ADMIN_ID)
            with patch.object(m.bot, 'answer_callback_query'):
                m.handle_all_callbacks(self.fake_call('toggle_auto_verify'))
            self.assertEqual(m.get_db_setting('auto_verify_charges'), '0')
            with patch.object(m.bot, 'answer_callback_query'):
                m.handle_all_callbacks(self.fake_call('toggle_auto_verify'))
            self.assertEqual(m.get_db_setting('auto_verify_charges'), '0')
        finally:
            m.update_db_setting('auto_verify_charges', previous or '0', m.ADMIN_ID)

    def test_unverified_payment_api_flags_are_forced_off(self):
        m = self.m
        previous_sy = m.get_db_setting('syriatel_api_enabled')
        previous_sh = m.get_db_setting('sham_api_enabled')
        try:
            m.update_db_setting('syriatel_api_enabled', '1', m.ADMIN_ID)
            m.update_db_setting('sham_api_enabled', '1', m.ADMIN_ID)
            with patch.object(m.bot, 'answer_callback_query'):
                m.handle_all_callbacks(self.fake_call('toggle_api'))
            self.assertEqual(m.get_db_setting('syriatel_api_enabled'), '0')
            self.assertEqual(m.get_db_setting('sham_api_enabled'), '0')
        finally:
            m.update_db_setting('syriatel_api_enabled', previous_sy or '0', m.ADMIN_ID)
            m.update_db_setting('sham_api_enabled', previous_sh or '0', m.ADMIN_ID)

    def test_charge_menus_refuse_missing_payment_destinations(self):
        m = self.m
        values = {
            'syriatel_status': 'active', 'syriatel_numbers': '',
            'sham_status': 'active', 'sham_address': 'sham_example@sham',
            'usdt_status': 'active', 'usdt_address': '',
            'binance_status': 'active', 'binance_address': '', 'binance_pay_id': '',
        }
        previous = {key: m.get_db_setting(key) for key in values}
        try:
            for key, value in values.items():
                m.update_db_setting(key, value, m.ADMIN_ID)
            for callback in ('charge_syria', 'charge_sham', 'charge_usdt', 'charge_binance'):
                with patch.object(m.bot, 'answer_callback_query'), \
                     patch.object(m.bot, 'send_message'), \
                     patch.object(m.bot, 'register_next_step_handler') as next_step:
                    m.handle_all_callbacks(self.fake_call(callback))
                next_step.assert_not_called()
        finally:
            for key, value in previous.items():
                m.update_db_setting(key, value or ('متوقف' if key.endswith('_status') else ''), m.ADMIN_ID)

    def test_crypto_charge_receipts_are_rejected_when_methods_are_disabled(self):
        m = self.m
        for method, handler, status_key, address_key, pay_id_key in (
            ('USDT', m.process_usdt_charge_receipt, 'usdt_status', 'usdt_address', None),
            ('Binance', m.process_binance_charge_receipt, 'binance_status', 'binance_address', 'binance_pay_id'),
        ):
            previous = {status_key: m.get_db_setting(status_key), address_key: m.get_db_setting(address_key)}
            if pay_id_key:
                previous[pay_id_key] = m.get_db_setting(pay_id_key)
            receipt = 'TEST-DISABLED-' + method.upper()
            try:
                m.update_db_setting(status_key, 'متوقف', m.ADMIN_ID)
                m.update_db_setting(address_key, '', m.ADMIN_ID)
                if pay_id_key:
                    m.update_db_setting(pay_id_key, '', m.ADMIN_ID)
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=810027),
                    chat=SimpleNamespace(id=810027),
                    text=receipt,
                )
                with patch.object(m.bot, 'send_message'):
                    handler(message)
                self.assertFalse(m.cursor.execute(
                    "SELECT 1 FROM pending_charges WHERE receipt_number=?", (receipt,)
                ).fetchone())
            finally:
                for key, value in previous.items():
                    m.update_db_setting(key, value or ('متوقف' if key.endswith('_status') else ''), m.ADMIN_ID)

    def test_sham_service_cannot_open_with_placeholder_address(self):
        m = self.m
        previous_status = m.get_db_setting('sham_status')
        previous_address = m.get_db_setting('sham_address')
        try:
            m.update_db_setting('sham_status', 'متوقف', m.ADMIN_ID)
            m.update_db_setting('sham_address', 'sham_example@sham', m.ADMIN_ID)
            with patch.object(m.bot, 'answer_callback_query'), patch.object(m.bot, 'edit_message_reply_markup'):
                m.handle_all_callbacks(self.fake_call('toggle_sham'))
            self.assertNotEqual(m.get_db_setting('sham_status'), 'active')
        finally:
            m.update_db_setting('sham_status', previous_status or 'متوقف', m.ADMIN_ID)
            m.update_db_setting('sham_address', previous_address or '', m.ADMIN_ID)

    def test_sham_charge_receipt_is_rejected_when_destination_is_placeholder(self):
        m = self.m
        previous_status = m.get_db_setting('sham_status')
        previous_address = m.get_db_setting('sham_address')
        receipt = 'TEST-SHAM-PLACEHOLDER-REJECT'
        try:
            m.update_db_setting('sham_status', 'active', m.ADMIN_ID)
            m.update_db_setting('sham_address', 'sham_example@sham', m.ADMIN_ID)
            message = SimpleNamespace(
                from_user=SimpleNamespace(id=810026),
                chat=SimpleNamespace(id=810026),
                text=receipt,
            )
            with patch.object(m.bot, 'send_message'):
                m.process_sham_charge_receipt(message)
            self.assertFalse(m.cursor.execute(
                "SELECT 1 FROM pending_charges WHERE receipt_number=?", (receipt,)
            ).fetchone())
        finally:
            m.update_db_setting('sham_status', previous_status or 'متوقف', m.ADMIN_ID)
            m.update_db_setting('sham_address', previous_address or '', m.ADMIN_ID)

    def test_usdt_service_cannot_open_without_a_destination_address(self):
        m = self.m
        previous_status = m.get_db_setting('usdt_status')
        previous_address = m.get_db_setting('usdt_address')
        try:
            m.update_db_setting('usdt_status', 'متوقف', m.ADMIN_ID)
            m.update_db_setting('usdt_address', '', m.ADMIN_ID)
            with patch.object(m.bot, 'answer_callback_query'):
                m.handle_all_callbacks(self.fake_call('toggle_usdt'))
            self.assertNotEqual(m.get_db_setting('usdt_status'), 'active')
        finally:
            m.update_db_setting('usdt_status', previous_status or 'متوقف', m.ADMIN_ID)
            m.update_db_setting('usdt_address', previous_address or '', m.ADMIN_ID)

    def test_binance_service_cannot_open_without_a_destination(self):
        m = self.m
        previous_status = m.get_db_setting('binance_status')
        previous_address = m.get_db_setting('binance_address')
        previous_pay_id = m.get_db_setting('binance_pay_id')
        try:
            m.update_db_setting('binance_status', 'متوقف', m.ADMIN_ID)
            m.update_db_setting('binance_address', '', m.ADMIN_ID)
            m.update_db_setting('binance_pay_id', '', m.ADMIN_ID)
            with patch.object(m.bot, 'answer_callback_query'):
                m.handle_all_callbacks(self.fake_call('toggle_binance'))
            self.assertNotEqual(m.get_db_setting('binance_status'), 'active')
        finally:
            m.update_db_setting('binance_status', previous_status or 'متوقف', m.ADMIN_ID)
            m.update_db_setting('binance_address', previous_address or '', m.ADMIN_ID)
            m.update_db_setting('binance_pay_id', previous_pay_id or '', m.ADMIN_ID)

    def test_neon_restore_document_handler_is_registered_for_documents(self):
        m = self.m
        handlers = [
            item for item in m.bot.message_handlers
            if item.get('function') is m.handle_backup_document
        ]
        self.assertTrue(handlers)
        self.assertTrue(any(
            'document' in item.get('filters', {}).get('content_types', [])
            for item in handlers
        ))

    def test_backup_menu_no_longer_reports_unimplemented_actions_as_success(self):
        m = self.m
        with patch.object(m.bot, 'answer_callback_query'), patch.object(m.bot, 'send_message') as send:
            m.handle_all_callbacks(self.fake_call('auto_backup_settings'))
        self.assertTrue(any('غير مفعّل' in str(call.args) or 'غير مفعّل' in str(call.kwargs) for call in send.call_args_list))

    def test_backup_listing_handler_returns_a_user_message(self):
        m = self.m
        with patch.object(m.bot, 'answer_callback_query'), patch.object(m.bot, 'send_message') as send:
            m.handle_all_callbacks(self.fake_call('list_backups'))
        send.assert_called()

    def test_api_test_button_does_not_claim_unconfigured_payment_api_is_connected(self):
        m = self.m
        with patch.object(m.bot, 'answer_callback_query') as answer:
            m.handle_all_callbacks(self.fake_call('test_api_connection'))
        self.assertTrue(any('غير متاح' in str(call) for call in answer.call_args_list))

    def test_ai_pr_checks_require_every_check_to_pass(self):
        m = self.m
        self.assertEqual(m._ai_pr_checks_ready([])[0], False)
        self.assertEqual(m._ai_pr_checks_ready([
            {'status': 'in_progress', 'conclusion': None}
        ])[0], False)
        self.assertEqual(m._ai_pr_checks_ready([
            {'status': 'completed', 'conclusion': 'failure'}
        ])[0], False)
        self.assertEqual(m._ai_pr_checks_ready([
            {'status': 'completed', 'conclusion': 'success'},
            {'status': 'completed', 'conclusion': 'success'},
        ])[0], True)

    def test_ai_text_change_applies_only_unique_literal_replacement(self):
        source = "alpha\\nold block\\nomega"
        updated = self.m.apply_ai_text_changes(source, [
            {"old_text": "old block", "new_text": "new block"}
        ])
        self.assertEqual(updated, "alpha\\nnew block\\nomega")

    def test_ai_text_change_rejects_ambiguous_or_missing_source(self):
        with self.assertRaises(ValueError):
            self.m.apply_ai_text_changes("repeat repeat", [
                {"old_text": "repeat", "new_text": "changed"}
            ])
        with self.assertRaises(ValueError):
            self.m.apply_ai_text_changes("some source", [
                {"old_text": "not present", "new_text": "changed"}
            ])

    def test_ai_text_change_rejects_empty_or_too_many_changes(self):
        with self.assertRaises(ValueError):
            self.m.apply_ai_text_changes("source", [])
        with self.assertRaises(ValueError):
            self.m.apply_ai_text_changes("source", [
                {"old_text": "source", "new_text": "one"},
                {"old_text": "one", "new_text": "two"},
                {"old_text": "two", "new_text": "three"},
                {"old_text": "three", "new_text": "four"},
                {"old_text": "four", "new_text": "five"},
                {"old_text": "five", "new_text": "six"},
            ])

    def test_ai_dev_preserves_existing_test_names_and_assertions(self):
        m = self.m
        path = 'tests/test_regressions.py'
        source = "def test_keep():\n    assert True\n"
        with self.assertRaises(ValueError):
            m.apply_ai_file_changes(
                {path: source},
                [{'path': path, 'changes': [{'old_text': 'def test_keep():\n    assert True\n',
                                             'new_text': 'def test_replacement():\n    assert True\n'}]}],
            )
        with self.assertRaises(ValueError):
            m.apply_ai_file_changes(
                {path: source},
                [{'path': path, 'changes': [{'old_text': 'assert True',
                                             'new_text': 'pass'}]}],
            )
        accepted = m.apply_ai_file_changes(
            {path: source},
            [{'path': path, 'changes': [{'old_text': 'def test_keep():\n    assert True\n',
                                         'new_text': 'def test_keep():\n    assert True\n\ndef test_extra():\n    assert True\n'}]}],
        )
        self.assertIn('def test_extra', accepted[path])
        self.assertIn('test_keep', accepted[path])

    def test_ai_setting_validator_rejects_unsupported_key_and_nonfinite_value(self):
        m = self.m
        with self.assertRaises(ValueError):
            m.validate_ai_setting_change('TOKEN', 'secret')
        with self.assertRaises(ValueError):
            m.validate_ai_setting_change('withdraw_commission', float('nan'))
        with self.assertRaises(ValueError):
            m.validate_ai_setting_change('referral_cycle_days', 1.5)

    def test_ai_setting_validator_normalizes_boolean_and_respects_withdrawal_bounds(self):
        m = self.m
        self.assertEqual(m.validate_ai_setting_change('wheel_enabled', 'تشغيل'), '1')
        self.assertEqual(m.validate_ai_setting_change('wheel_enabled', False), '0')
        with patch.object(m, 'get_db_setting', return_value='500000'):
            with self.assertRaises(ValueError):
                m.validate_ai_setting_change('min_withdraw_syria', 600000)

    def test_ai_setting_validator_accepts_forced_subscription_message(self):
        m = self.m
        value = "اشترك بالقناة ثم اضغط تحقق"
        self.assertEqual(m.validate_ai_setting_change('subscription_message', value), value)
        self.assertIn("الاشتراك", str(m.get_db_setting('subscription_message')))

    def test_ai_setting_confirmation_is_owner_only(self):
        m = self.m
        m.ai_pending_actions[m.ADMIN_ID] = {
            'token': 'token1111', 'key': 'welcome_message', 'value': 'new welcome', 'old_value': 'old welcome'
        }
        try:
            with patch.object(m, 'update_db_setting') as update, \
                 patch.object(m.bot, 'send_message'):
                m.confirm_ai_setting_change(123456, 123456, 'token1111')
            update.assert_not_called()
            self.assertIn(m.ADMIN_ID, m.ai_pending_actions)
        finally:
            m.ai_pending_actions.pop(m.ADMIN_ID, None)

    def test_ai_setting_confirmation_rejects_stale_button_token(self):
        m = self.m
        m.ai_pending_actions[m.ADMIN_ID] = {
            'token': 'newtoken', 'key': 'welcome_message', 'value': 'new', 'old_value': 'old'
        }
        try:
            with patch.object(m, 'update_db_setting') as update, \
                 patch.object(m.bot, 'send_message'):
                m.confirm_ai_setting_change(m.ADMIN_ID, m.ADMIN_ID, 'oldtoken')
            update.assert_not_called()
            self.assertEqual(m.ai_pending_actions[m.ADMIN_ID]['token'], 'newtoken')
        finally:
            m.ai_pending_actions.pop(m.ADMIN_ID, None)

    def test_ai_setting_confirmation_refuses_to_overwrite_a_newer_value(self):
        m = self.m
        m.ai_pending_actions[m.ADMIN_ID] = {
            'token': 'token2222', 'key': 'welcome_message', 'value': 'proposed', 'old_value': 'original'
        }
        try:
            with patch.object(m, 'get_db_setting', return_value='changed elsewhere'), \
                 patch.object(m, 'update_db_setting') as update, \
                 patch.object(m.bot, 'send_message'):
                m.confirm_ai_setting_change(m.ADMIN_ID, m.ADMIN_ID, 'token2222')
            update.assert_not_called()
            self.assertNotIn(m.ADMIN_ID, m.ai_pending_actions)
        finally:
            m.ai_pending_actions.pop(m.ADMIN_ID, None)

    def test_ai_submenu_requests_are_routed_to_safe_preview(self):
        m = self.m
        self.assertTrue(m.looks_like_ai_setting_request('أنشئ قائمة فرعية جديدة باسم العروض'))
        self.assertTrue(m.looks_like_ai_setting_request('أضف زر فرعي جديد'))
        self.assertFalse(m.looks_like_ai_setting_request('مرحبا كيفك'))

    def test_ai_submenu_creation_validation_rejects_duplicate_and_missing_parent(self):
        m = self.m
        now = '2026-10-15 00:00:00'
        m.cursor.execute(
            "INSERT INTO dynamic_buttons(button_name,button_text,parent_button,action,message_text,level,sort_order,is_active,created_at,updated_at,created_by,path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ('ai_submenu_parent', 'قائمة أب لاختبار القائمة الفرعية', 'main', 'show_submenu', None, 1, 0, 1, now, now, m.ADMIN_ID, '/main/ai_submenu_parent'),
        )
        m.conn.commit()
        try:
            valid = m.validate_ai_submenu_creation('قائمة فرعية جديدة للاختبار', 'قائمة أب لاختبار القائمة الفرعية')
            self.assertEqual(valid, {
                'kind': 'create_submenu',
                'button_text': 'قائمة فرعية جديدة للاختبار',
                'parent_button': 'قائمة أب لاختبار القائمة الفرعية',
            })
            with self.assertRaises(ValueError):
                m.validate_ai_submenu_creation('قائمة أب لاختبار القائمة الفرعية', 'main')
            with self.assertRaises(ValueError):
                m.validate_ai_submenu_creation('قائمة غير صالحة', 'أب غير موجود')
        finally:
            m.cursor.execute("DELETE FROM dynamic_buttons WHERE button_name='ai_submenu_parent'")
            m.conn.commit()

    def test_ai_submenu_creation_requires_owner_confirmation(self):
        m = self.m
        name = 'قائمة فرعية جديدة من AI'
        m.ai_pending_actions[m.ADMIN_ID] = {
            'token': 'submenu123', 'kind': 'create_submenu',
            'button_text': name, 'parent_button': 'main',
            'value': 'إنشاء قائمة فرعية فارغة', 'old_value': '', 'label': 'قائمة فرعية جديدة',
        }
        try:
            with patch.object(m.bot, 'send_message'):
                m.confirm_ai_setting_change(123456, 123456, 'submenu123')
            self.assertFalse(m.cursor.execute(
                "SELECT 1 FROM dynamic_buttons WHERE button_text=?", (name,)
            ).fetchone())
            with patch.object(m.bot, 'send_message'):
                m.confirm_ai_setting_change(m.ADMIN_ID, m.ADMIN_ID, 'submenu123')
            row = m.cursor.execute(
                "SELECT parent_button,action,message_text,is_active FROM dynamic_buttons WHERE button_text=?",
                (name,),
            ).fetchone()
            self.assertEqual(row, ('main', 'show_submenu', None, 1))
            self.assertNotIn(m.ADMIN_ID, m.ai_pending_actions)
        finally:
            m.ai_pending_actions.pop(m.ADMIN_ID, None)
            m.cursor.execute("DELETE FROM dynamic_buttons WHERE button_text=?", (name,))
            m.conn.commit()

    def test_ai_created_submenu_can_open_its_child_buttons(self):
        m = self.m
        now = '2026-10-15 00:00:00'
        parent = 'قائمة AI قابلة للفتح'
        child = 'زر طفل داخل قائمة AI'
        m.cursor.execute(
            "INSERT INTO dynamic_buttons(button_name,button_text,parent_button,action,message_text,level,sort_order,is_active,created_at,updated_at,created_by,path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ('ai_submenu_open_parent', parent, 'main', 'show_submenu', None, 1, 0, 1, now, now, m.ADMIN_ID, '/main/ai_submenu_open_parent'),
        )
        m.cursor.execute(
            "INSERT INTO dynamic_buttons(button_name,button_text,parent_button,action,message_text,level,sort_order,is_active,created_at,updated_at,created_by,path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ('ai_submenu_open_child', child, parent, 'send_message', 'رسالة طفل', 2, 0, 1, now, now, m.ADMIN_ID, '/main/ai_submenu_open_parent/ai_submenu_open_child'),
        )
        m.conn.commit()
        try:
            with patch.object(m.bot, 'send_message') as send:
                m.ActionSystem.show_submenu(m.ADMIN_ID, m.ADMIN_ID, {'button_text': parent, 'level': 1})
            send.assert_called_once()
            self.assertIsNotNone(send.call_args.kwargs.get('reply_markup'))
        finally:
            m.cursor.execute("DELETE FROM dynamic_buttons WHERE button_name IN ('ai_submenu_open_parent','ai_submenu_open_child')")
            m.conn.commit()

    def test_ai_button_creation_validation_rejects_duplicate_and_missing_parent(self):
        m = self.m
        now = '2026-10-15 00:00:00'
        m.cursor.execute(
            "INSERT INTO dynamic_buttons(button_name,button_text,parent_button,action,message_text,level,sort_order,is_active,created_at,updated_at,created_by,path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ('ai_test_parent', 'قائمة AI اختبار', 'main', 'show_submenu', None, 1, 0, 1, now, now, m.ADMIN_ID, '/main/ai_test_parent'),
        )
        m.conn.commit()
        try:
            valid = m.validate_ai_button_creation(
                'زر AI جديد', 'قائمة AI اختبار', 'رسالة تجريبية'
            )
            self.assertEqual(valid['kind'], 'create_button')
            self.assertEqual(valid['parent_button'], 'قائمة AI اختبار')
            with self.assertRaises(ValueError):
                m.validate_ai_button_creation('قائمة AI اختبار', 'main', 'رسالة')
            with self.assertRaises(ValueError):
                m.validate_ai_button_creation('زر غير صالح', 'قائمة غير موجودة', 'رسالة')
        finally:
            m.cursor.execute("DELETE FROM dynamic_buttons WHERE button_name='ai_test_parent'")
            m.conn.commit()

    def test_ai_button_creation_requires_owner_confirmation_and_creates_message_button(self):
        m = self.m
        name = 'زر AI جديد للاختبار'
        m.ai_pending_actions[m.ADMIN_ID] = {
            'token': 'create123', 'kind': 'create_button',
            'button_text': name, 'parent_button': 'main',
            'message_text': 'رسالة الزر الجديدة', 'value': 'رسالة الزر الجديدة',
            'old_value': '', 'label': 'زر جديد للاختبار',
        }
        try:
            with patch.object(m.bot, 'send_message'):
                m.confirm_ai_setting_change(123456, 123456, 'create123')
            self.assertFalse(m.cursor.execute(
                "SELECT 1 FROM dynamic_buttons WHERE button_text=?", (name,)
            ).fetchone())
            with patch.object(m.bot, 'send_message'):
                m.confirm_ai_setting_change(m.ADMIN_ID, m.ADMIN_ID, 'create123')
            row = m.cursor.execute(
                "SELECT parent_button,action,message_text,is_active FROM dynamic_buttons WHERE button_text=?",
                (name,),
            ).fetchone()
            self.assertEqual(row, ('main', 'send_message', 'رسالة الزر الجديدة', 1))
            self.assertNotIn(m.ADMIN_ID, m.ai_pending_actions)
        finally:
            m.ai_pending_actions.pop(m.ADMIN_ID, None)
            m.cursor.execute("DELETE FROM dynamic_buttons WHERE button_text=?", (name,))
            m.conn.commit()

    def test_ai_button_change_validates_existing_button_and_duplicate_name(self):
        m = self.m
        now = '2026-10-15 00:00:00'
        m.cursor.execute(
            "INSERT INTO dynamic_buttons(button_name,button_text,parent_button,action,message_text,level,sort_order,is_active,created_at,updated_at,created_by,path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ('ai_test_button_a', 'زر اختبار أ', 'main', 'show_balance', 'رسالة قديمة', 1, 0, 1, now, now, m.ADMIN_ID, '/'),
        )
        first_id = m.cursor.lastrowid
        m.cursor.execute(
            "INSERT INTO dynamic_buttons(button_name,button_text,parent_button,action,message_text,level,sort_order,is_active,created_at,updated_at,created_by,path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ('ai_test_button_b', 'زر اختبار ب', 'main', 'show_balance', 'رسالة ثانية', 1, 0, 1, now, now, m.ADMIN_ID, '/'),
        )
        second_id = m.cursor.lastrowid
        m.conn.commit()
        try:
            valid = m.validate_ai_button_change(second_id, 'message_text', 'رسالة جديدة')
            self.assertEqual(valid, {
                'kind': 'button', 'button_id': second_id,
                'field': 'message_text', 'value': 'رسالة جديدة'
            })
            with self.assertRaises(ValueError):
                m.validate_ai_button_change(second_id, 'button_text', 'زر اختبار أ')
            with self.assertRaises(ValueError):
                m.validate_ai_button_change(second_id, 'action', 'dangerous_action')
        finally:
            m.cursor.execute("DELETE FROM dynamic_buttons WHERE id IN (?,?)", (first_id, second_id))
            m.conn.commit()

    def test_ai_button_confirmation_updates_requested_field_after_owner_approval(self):
        m = self.m
        now = '2026-10-15 00:00:00'
        m.cursor.execute(
            "INSERT INTO dynamic_buttons(button_name,button_text,parent_button,action,message_text,level,sort_order,is_active,created_at,updated_at,created_by,path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ('ai_test_button_confirm', 'زر تأكيد AI', 'main', 'show_balance', 'قبل التعديل', 1, 0, 1, now, now, m.ADMIN_ID, '/'),
        )
        button_id = m.cursor.lastrowid
        m.conn.commit()
        m.ai_pending_actions[m.ADMIN_ID] = {
            'token': 'btn12345', 'kind': 'button', 'button_id': button_id,
            'field': 'message_text', 'value': 'بعد التعديل',
            'old_value': 'قبل التعديل', 'label': 'رسالة الزر',
        }
        try:
            with patch.object(m.bot, 'send_message'):
                m.confirm_ai_setting_change(m.ADMIN_ID, m.ADMIN_ID, 'btn12345')
            row = m.cursor.execute(
                "SELECT button_text,message_text,updated_at FROM dynamic_buttons WHERE id=?",
                (button_id,),
            ).fetchone()
            self.assertEqual(row[0], 'زر تأكيد AI')
            self.assertEqual(row[1], 'بعد التعديل')
            self.assertTrue(row[2])
            self.assertNotIn(m.ADMIN_ID, m.ai_pending_actions)
        finally:
            m.ai_pending_actions.pop(m.ADMIN_ID, None)
            m.cursor.execute("DELETE FROM dynamic_buttons WHERE id=?", (button_id,))
            m.conn.commit()

    def test_ai_dev_from_chat_uses_latest_owner_request(self):
        m = self.m
        request_text = 'أضف رسالة ترحيب واضحة للمستخدم الجديد'
        m.conn.execute("DELETE FROM ai_conversations WHERE user_id=?", (m.ADMIN_ID,))
        m.conn.execute(
            "INSERT INTO ai_conversations(user_id,role,content,created_at) VALUES (?,?,?,?)",
            (m.ADMIN_ID, 'user', request_text, '2026-10-15 00:00:00'),
        )
        m.conn.commit()

        with patch.object(m, '_github_config', return_value=('token', 'repo/name', 'main')), \
             patch.object(m, 'create_ai_draft_pr', return_value=({
                 'number': 123, 'summary': 'تعديل ترحيب', 'url': 'https://example.test/pr/123'
             }, None)) as create, \
             patch.object(m.bot, 'send_message'):
            m.create_ai_draft_from_last_message(m.ADMIN_ID, m.ADMIN_ID)

        create.assert_called_once_with(request_text, m.ADMIN_ID)

    def test_ai_dev_from_chat_rejects_non_owner(self):
        m = self.m
        with patch.object(m, 'create_ai_draft_pr') as create, \
             patch.object(m.bot, 'send_message') as send:
            m.create_ai_draft_from_last_message(123456, 123456)
        create.assert_not_called()
        send.assert_called_once()

    def test_gift_transfer_rejects_nan_amount_without_changing_balances(self):
        m = self.m
        sender, target = 810019, 810020
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id,balance,site_balance,deleted) VALUES (?,?,?,0)",
            (sender, 100.0, 0.0),
        )
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id,balance,site_balance,deleted) VALUES (?,?,?,0)",
            (target, 10.0, 0.0),
        )
        m.conn.commit()
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=sender),
            chat=SimpleNamespace(id=sender),
            text='nan',
        )
        with patch.object(m.bot, 'send_message'):
            m.ActionSystem.process_gift_amount(message, target)
        balances = m.cursor.execute(
            "SELECT user_id,balance FROM users WHERE user_id IN (?,?) ORDER BY user_id",
            (sender, target),
        ).fetchall()
        self.assertEqual(balances, [(sender, 100.0), (target, 10.0)])

    def test_gift_code_rejects_infinite_value(self):
        m = self.m
        code = 'TESTINFINITE'
        m.cursor.execute(
            "INSERT OR REPLACE INTO gifts(code,value,limit_count,used_count,created_by,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (code, float('inf'), 1, 0, None, '2026-10-15 00:00:00'),
        )
        m.conn.commit()
        try:
            status, amount = m.redeem_gift_atomic(810021, code)
            self.assertEqual(status, 'invalid')
            self.assertEqual(amount, 0)
        finally:
            m.cursor.execute("DELETE FROM gifts WHERE code=?", (code,))
            m.conn.commit()

    def test_gift_creation_rolls_back_when_cashier_balance_is_insufficient(self):
        m = self.m
        admin = m.ADMIN_ID
        old_cashier = m.cursor.execute(
            "SELECT balance,last_updated FROM cashier_balance WHERE admin_id=?", (admin,)
        ).fetchone()
        m.cursor.execute(
            "INSERT OR REPLACE INTO cashier_balance(admin_id,balance,last_updated) VALUES (?,?,?)",
            (admin, 10.0, '2026-10-15 00:00:00'),
        )
        m.conn.commit()
        try:
            with patch.object(m, 'generate_gift_code', return_value='TESTINSUFFICIENTGIFT'), \
                 patch.object(m, 'log_admin_action'):
                with self.assertRaises(ValueError):
                    m.GiftManager.create_gift(admin, 20.0, 1, 'individual', 0)
            self.assertIsNone(m.cursor.execute(
                "SELECT 1 FROM gifts WHERE code='TESTINSUFFICIENTGIFT'"
            ).fetchone())
            self.assertEqual(
                m.cursor.execute("SELECT balance FROM cashier_balance WHERE admin_id=?", (admin,)).fetchone()[0],
                10.0,
            )
        finally:
            m.cursor.execute("DELETE FROM gifts WHERE code='TESTINSUFFICIENTGIFT'")
            m.cursor.execute("DELETE FROM transactions WHERE type='gift_create' AND external_ref='TESTINSUFFICIENTGIFT'")
            if old_cashier:
                m.cursor.execute(
                    "UPDATE cashier_balance SET balance=?,last_updated=? WHERE admin_id=?",
                    (old_cashier[0], old_cashier[1], admin),
                )
            m.conn.commit()

    def test_gift_refund_rolls_back_if_ledger_insert_fails(self):
        m = self.m
        admin, code = m.ADMIN_ID, 'TESTGIFTREFUNDROLLBACK'
        old_cashier = m.cursor.execute(
            "SELECT balance,last_updated FROM cashier_balance WHERE admin_id=?", (admin,)
        ).fetchone()
        m.cursor.execute(
            "INSERT OR REPLACE INTO cashier_balance(admin_id,balance,last_updated) VALUES (?,?,?)",
            (admin, 50.0, '2026-10-15 00:00:00'),
        )
        m.cursor.execute(
            "INSERT OR REPLACE INTO gifts(code,value,limit_count,used_count,created_by,created_at,expires_at,auto_returned) "
            "VALUES (?,?,?,?,?,?,?,0)",
            (code, 10.0, 5, 2, admin, '2000-01-01 00:00:00', '2000-01-02 00:00:00'),
        )
        m.conn.commit()
        m.conn.execute("DROP TRIGGER IF EXISTS fail_gift_refund_ledger_test")
        m.conn.execute(
            "CREATE TRIGGER fail_gift_refund_ledger_test BEFORE INSERT ON transactions "
            "WHEN NEW.type='gift_refund' BEGIN SELECT RAISE(ABORT, 'forced gift refund ledger failure'); END"
        )
        m.conn.commit()
        try:
            with self.assertRaises(m.sqlite3.IntegrityError):
                m.close_gift_and_refund_atomic(code, admin, require_expired=True)
            self.assertEqual(
                m.cursor.execute("SELECT balance FROM cashier_balance WHERE admin_id=?", (admin,)).fetchone()[0],
                50.0,
            )
            self.assertEqual(
                m.cursor.execute("SELECT auto_returned FROM gifts WHERE code=?", (code,)).fetchone()[0],
                0,
            )
        finally:
            m.conn.rollback()
            m.conn.execute("DROP TRIGGER IF EXISTS fail_gift_refund_ledger_test")
            m.cursor.execute("DELETE FROM transactions WHERE type='gift_refund' AND external_ref=?", (code,))
            m.cursor.execute("DELETE FROM gifts WHERE code=?", (code,))
            if old_cashier:
                m.cursor.execute(
                    "UPDATE cashier_balance SET balance=?,last_updated=? WHERE admin_id=?",
                    (old_cashier[0], old_cashier[1], admin),
                )
            m.conn.commit()

    def test_gift_cancellation_refunds_cashier_and_closes_code_atomically(self):
        m = self.m
        admin, code = m.ADMIN_ID, 'TESTGIFTCANCELATOMIC'
        old_cashier = m.cursor.execute(
            "SELECT balance,last_updated FROM cashier_balance WHERE admin_id=?", (admin,)
        ).fetchone()
        m.cursor.execute(
            "INSERT OR REPLACE INTO cashier_balance(admin_id,balance,last_updated) VALUES (?,?,?)",
            (admin, 20.0, '2026-10-15 00:00:00'),
        )
        m.cursor.execute(
            "INSERT OR REPLACE INTO gifts(code,value,limit_count,used_count,created_by,created_at,auto_returned) "
            "VALUES (?,?,?,?,?,?,0)",
            (code, 5.0, 4, 1, admin, '2026-10-15 00:00:00'),
        )
        m.conn.commit()
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=admin),
            chat=SimpleNamespace(id=admin),
            text=code,
        )
        try:
            with patch.object(m.bot, 'send_message'):
                m.process_cancel_gift_code(message)
            gift = m.cursor.execute(
                "SELECT limit_count,used_count,auto_returned FROM gifts WHERE code=?", (code,)
            ).fetchone()
            self.assertEqual(gift, (1, 1, 1))
            self.assertEqual(
                m.cursor.execute("SELECT balance FROM cashier_balance WHERE admin_id=?", (admin,)).fetchone()[0],
                35.0,
            )
            self.assertEqual(
                m.cursor.execute("SELECT amount,type FROM transactions WHERE type='gift_refund' AND external_ref=?", (code,)).fetchone(),
                (15.0, 'gift_refund'),
            )
            # Repeating cancellation must not refund the same code twice.
            with patch.object(m.bot, 'send_message'):
                m.process_cancel_gift_code(message)
            self.assertEqual(
                m.cursor.execute("SELECT balance FROM cashier_balance WHERE admin_id=?", (admin,)).fetchone()[0],
                35.0,
            )
            self.assertEqual(
                m.cursor.execute("SELECT COUNT(*) FROM transactions WHERE type='gift_refund' AND external_ref=?", (code,)).fetchone()[0],
                1,
            )
        finally:
            m.cursor.execute("DELETE FROM transactions WHERE type='gift_refund' AND external_ref=?", (code,))
            m.cursor.execute("DELETE FROM gifts WHERE code=?", (code,))
            if old_cashier:
                m.cursor.execute(
                    "UPDATE cashier_balance SET balance=?,last_updated=? WHERE admin_id=?",
                    (old_cashier[0], old_cashier[1], admin),
                )
            m.conn.commit()

    def test_pending_charge_creation_is_atomic_and_rejects_duplicate_receipts(self):
        m = self.m
        uid, receipt = 810024, 'TEST-PENDING-RECEIPT'
        try:
            first, status = m.create_pending_charge_atomic(
                uid, 'USDT', 'usdt', receipt, details='test receipt'
            )
            self.assertEqual(status, 'ok')
            charge_id, transaction_receipt = first
            row = m.cursor.execute(
                "SELECT status,txn_receipt FROM pending_charges WHERE id=?", (charge_id,)
            ).fetchone()
            self.assertEqual(row, ('pending', transaction_receipt))
            ledger = m.cursor.execute(
                "SELECT type,status,external_ref FROM transactions WHERE receipt_number=?",
                (transaction_receipt,),
            ).fetchone()
            self.assertEqual(ledger, ('charge_request', 'pending', receipt))
            second, duplicate_status = m.create_pending_charge_atomic(
                uid + 1, 'USDT', 'usdt', receipt, details='duplicate'
            )
            self.assertIsNone(second)
            self.assertEqual(duplicate_status, 'duplicate_receipt')
            self.assertEqual(
                m.cursor.execute("SELECT COUNT(*) FROM pending_charges WHERE receipt_number=?", (receipt,)).fetchone()[0],
                1,
            )
            self.assertEqual(
                m.cursor.execute("SELECT COUNT(*) FROM transactions WHERE type='charge_request' AND external_ref=?", (receipt,)).fetchone()[0],
                1,
            )
        finally:
            m.cursor.execute("DELETE FROM transactions WHERE type='charge_request' AND external_ref=?", (receipt,))
            m.cursor.execute("DELETE FROM pending_charges WHERE receipt_number=?", (receipt,))
            m.conn.commit()

    def test_pending_charge_rolls_back_ledger_if_request_insert_fails(self):
        m = self.m
        uid, receipt = 810025, 'TEST-PENDING-FAIL'
        m.conn.execute("DROP TRIGGER IF EXISTS fail_pending_charge_insert_test")
        m.conn.execute(
            "CREATE TRIGGER fail_pending_charge_insert_test BEFORE INSERT ON pending_charges "
            "WHEN NEW.receipt_number='TEST-PENDING-FAIL' BEGIN SELECT RAISE(ABORT, 'forced pending insert failure'); END"
        )
        m.conn.commit()
        try:
            with self.assertRaises(m.sqlite3.IntegrityError):
                m.create_pending_charge_atomic(uid, 'USDT', 'usdt', receipt, details='forced failure')
            self.assertEqual(
                m.cursor.execute("SELECT COUNT(*) FROM transactions WHERE type='charge_request' AND external_ref=?", (receipt,)).fetchone()[0],
                0,
            )
            self.assertEqual(
                m.cursor.execute("SELECT COUNT(*) FROM pending_charges WHERE receipt_number=?", (receipt,)).fetchone()[0],
                0,
            )
        finally:
            m.conn.rollback()
            m.conn.execute("DROP TRIGGER IF EXISTS fail_pending_charge_insert_test")
            m.cursor.execute("DELETE FROM transactions WHERE type='charge_request' AND external_ref=?", (receipt,))
            m.cursor.execute("DELETE FROM pending_charges WHERE receipt_number=?", (receipt,))
            m.conn.commit()

    def test_gift_redemption_writes_ledger_atomically(self):
        m = self.m
        uid, code = 810022, 'TESTGIFTLEDGER'
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id,balance,deleted) VALUES (?,?,0)",
            (uid, 20.0),
        )
        m.cursor.execute(
            "INSERT OR REPLACE INTO gifts(code,value,limit_count,used_count,created_by,created_at) VALUES (?,?,?,?,?,?)",
            (code, 15.0, 1, 0, m.ADMIN_ID, '2026-10-15 00:00:00'),
        )
        m.conn.commit()
        try:
            status, amount = m.redeem_gift_atomic(uid, code)
            self.assertEqual((status, amount), ('ok', 15.0))
            self.assertEqual(m.cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0], 35.0)
            self.assertEqual(m.cursor.execute("SELECT used_count FROM gifts WHERE code=?", (code,)).fetchone()[0], 1)
            ledger = m.cursor.execute(
                "SELECT amount,type,status FROM transactions WHERE user_id=? AND type='gift_redeem' ORDER BY id DESC LIMIT 1",
                (uid,),
            ).fetchone()
            self.assertEqual(ledger, (15.0, 'gift_redeem', 'success'))
        finally:
            m.cursor.execute("DELETE FROM transactions WHERE user_id=? AND type='gift_redeem'", (uid,))
            m.cursor.execute("DELETE FROM gift_usage WHERE user_id=? AND code=?", (uid, code))
            m.cursor.execute("DELETE FROM gifts WHERE code=?", (code,))
            m.cursor.execute("DELETE FROM users WHERE user_id=?", (uid,))
            m.conn.commit()

    def test_gift_redemption_rolls_back_if_ledger_insert_fails(self):
        m = self.m
        uid, code = 810023, 'TESTGIFTLEDGERFAIL'
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id,balance,deleted) VALUES (?,?,0)",
            (uid, 20.0),
        )
        m.cursor.execute(
            "INSERT OR REPLACE INTO gifts(code,value,limit_count,used_count,created_by,created_at) VALUES (?,?,?,?,?,?)",
            (code, 15.0, 1, 0, m.ADMIN_ID, '2026-10-15 00:00:00'),
        )
        m.conn.commit()
        m.conn.execute("DROP TRIGGER IF EXISTS fail_gift_redeem_ledger_test")
        m.conn.execute(
            "CREATE TRIGGER fail_gift_redeem_ledger_test BEFORE INSERT ON transactions "
            "WHEN NEW.type='gift_redeem' BEGIN SELECT RAISE(ABORT, 'forced gift redeem ledger failure'); END"
        )
        m.conn.commit()
        try:
            with self.assertRaises(m.sqlite3.IntegrityError):
                m.redeem_gift_atomic(uid, code)
            self.assertEqual(m.cursor.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()[0], 20.0)
            self.assertEqual(m.cursor.execute("SELECT used_count FROM gifts WHERE code=?", (code,)).fetchone()[0], 0)
            self.assertIsNone(m.cursor.execute("SELECT 1 FROM gift_usage WHERE user_id=? AND code=?", (uid, code)).fetchone())
        finally:
            m.conn.rollback()
            m.conn.execute("DROP TRIGGER IF EXISTS fail_gift_redeem_ledger_test")
            m.cursor.execute("DELETE FROM transactions WHERE user_id=? AND type='gift_redeem'", (uid,))
            m.cursor.execute("DELETE FROM gift_usage WHERE user_id=? AND code=?", (uid, code))
            m.cursor.execute("DELETE FROM gifts WHERE code=?", (code,))
            m.cursor.execute("DELETE FROM users WHERE user_id=?", (uid,))
            m.conn.commit()

    def test_gift_transfer_rolls_back_if_transaction_ledger_insert_fails(self):
        m = self.m
        sender, target = 810016, 810017
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id,balance,site_balance,deleted) VALUES (?,?,?,0)",
            (sender, 100.0, 0.0),
        )
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id,balance,site_balance,deleted) VALUES (?,?,?,0)",
            (target, 10.0, 0.0),
        )
        m.conn.commit()
        m.conn.execute("DROP TRIGGER IF EXISTS fail_gift_ledger_test")
        m.conn.execute(
            "CREATE TRIGGER fail_gift_ledger_test BEFORE INSERT ON transactions "
            "WHEN NEW.type='gift' BEGIN SELECT RAISE(ABORT, 'forced gift ledger failure'); END"
        )
        m.conn.commit()
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=sender),
            chat=SimpleNamespace(id=sender),
            text='25',
        )
        try:
            with patch.object(m.bot, 'send_message'):
                with self.assertRaises(m.sqlite3.IntegrityError):
                    m.ActionSystem.process_gift_amount(message, target)
        finally:
            m.conn.rollback()
            m.conn.execute("DROP TRIGGER IF EXISTS fail_gift_ledger_test")
            m.conn.commit()

        balances = m.cursor.execute(
            "SELECT user_id,balance FROM users WHERE user_id IN (?,?) ORDER BY user_id",
            (sender, target),
        ).fetchall()
        self.assertEqual(balances, [(sender, 100.0), (target, 10.0)])

    def test_wheel_bonus_rolls_back_if_user_is_missing(self):
        m = self.m
        missing_uid = 819998
        m.cursor.execute("DELETE FROM users WHERE user_id=?", (missing_uid,))
        old_cashier = m.cursor.execute(
            "SELECT balance,last_updated FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)
        ).fetchone()
        m.cursor.execute(
            "INSERT OR REPLACE INTO cashier_balance(admin_id,balance,last_updated) VALUES (?,?,?)",
            (m.ADMIN_ID, 100.0, '2026-10-15 00:00:00'),
        )
        m.cursor.execute(
            "INSERT INTO wheel_bonuses(user_id,percent,source_spin_id,created_at) VALUES (?,?,?,?)",
            (missing_uid, 20.0, 910015, '2026-10-15 00:00:00'),
        )
        bonus_id = m.cursor.lastrowid
        m.conn.commit()
        try:
            result = m.apply_wheel_bonus_on_charge(missing_uid, 100.0, m.ADMIN_ID)
            cashier = m.cursor.execute(
                "SELECT balance FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)
            ).fetchone()[0]
            used_at = m.cursor.execute(
                "SELECT used_at FROM wheel_bonuses WHERE id=?", (bonus_id,)
            ).fetchone()[0]
            self.assertEqual(result, 0.0)
            self.assertEqual(cashier, 100.0)
            self.assertIsNone(used_at)
        finally:
            m.cursor.execute("DELETE FROM wheel_bonuses WHERE id=?", (bonus_id,))
            if old_cashier:
                m.cursor.execute(
                    "UPDATE cashier_balance SET balance=?,last_updated=? WHERE admin_id=?",
                    (old_cashier[0], old_cashier[1], m.ADMIN_ID),
                )
            else:
                m.cursor.execute("DELETE FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,))
            m.conn.commit()

    def test_expired_gift_refund_failure_does_not_mark_gift_returned(self):
        m = self.m
        code = 'TESTREFUNDFAIL'
        old_cashier = m.cursor.execute(
            "SELECT balance,last_updated FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,)
        ).fetchone()
        m.cursor.execute("DELETE FROM cashier_balance WHERE admin_id=?", (m.ADMIN_ID,))
        m.cursor.execute(
            "INSERT OR REPLACE INTO gifts(code,value,limit_count,used_count,created_by,created_at,expires_at,auto_returned) "
            "VALUES (?,?,?,?,?,?,?,0)",
            (code, 10.0, 3, 1, m.ADMIN_ID, '2026-01-01 00:00:00', '2000-01-01 00:00:00'),
        )
        m.conn.commit()
        try:
            status, amount = m.redeem_gift_atomic(810018, code)
            returned = m.cursor.execute(
                "SELECT auto_returned FROM gifts WHERE code=?", (code,)
            ).fetchone()[0]
            self.assertEqual(status, 'refund_failed')
            self.assertEqual(amount, 0)
            self.assertEqual(returned, 0)
        finally:
            m.cursor.execute("DELETE FROM gifts WHERE code=?", (code,))
            if old_cashier:
                m.cursor.execute(
                    "INSERT OR REPLACE INTO cashier_balance(admin_id,balance,last_updated) VALUES (?,?,?)",
                    (m.ADMIN_ID, old_cashier[0], old_cashier[1]),
                )
            m.conn.commit()

    def test_charge_claim_is_atomic_and_only_one_moderator_can_claim(self):
        m = self.m
        uid = 810015
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, site_balance, deleted) VALUES (?,?,?,0)",
            (uid, 0.0, 0.0),
        )
        m.cursor.execute(
            "INSERT INTO pending_charges(user_id,method,receipt_number,amount,status,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (uid, 'test', 'PAY-CLAIM-810015', 10.0, 'pending', '2026-10-15 00:00:00'),
        )
        charge_id = m.cursor.lastrowid
        m.conn.commit()

        first, first_status = m.claim_pending_charge(charge_id, 555551)
        second, second_status = m.claim_pending_charge(charge_id, 555552)
        row = m.cursor.execute(
            "SELECT status, processed_by FROM pending_charges WHERE id=?", (charge_id,)
        ).fetchone()

        self.assertEqual(first_status, 'ok')
        self.assertEqual(first['user_id'], uid)
        self.assertEqual(second_status, 'not_pending')
        self.assertIsNone(second)
        self.assertEqual(row, ('processing', 555551))

    def test_withdraw_completion_rejects_other_claimant_without_deducting(self):
        m = self.m
        uid = 810013
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, site_balance, deleted) VALUES (?,?,?,0)",
            (uid, 70.0, 0.0),
        )
        m.cursor.execute(
            "INSERT INTO pending_withdraws(user_id,method,account,amount,commission,net_amount,status,created_at,processed_by,reserved) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (uid, 'test', 'acct', 30.0, 0.0, 30.0, 'processing', '2026-10-15 00:00:00', 555551, 1),
        )
        withdraw_id = m.cursor.lastrowid
        m.conn.commit()

        result, status = m.complete_pending_withdraw(withdraw_id, 555552)
        balance = m.cursor.execute(
            "SELECT balance FROM users WHERE user_id=?", (uid,)
        ).fetchone()[0]
        self.assertIsNone(result)
        self.assertEqual(status, 'claimed_by_other')
        self.assertEqual(balance, 70.0)

    def test_withdraw_cancellation_refunds_reserved_amount_once(self):
        m = self.m
        uid = 810014
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, site_balance, deleted) VALUES (?,?,?,0)",
            (uid, 70.0, 0.0),
        )
        m.cursor.execute(
            "INSERT INTO transactions(user_id,type,amount,commission,net_amount,method,status,transaction_date,admin_id,details,receipt_number,external_ref) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid, 'withdraw_request', 30.0, 0.0, 30.0, 'test', 'pending', '2026-10-15 00:00:00', None, '', 'TXN-WITHDRAW-810014', ''),
        )
        m.cursor.execute(
            "INSERT INTO pending_withdraws(user_id,method,account,amount,commission,net_amount,status,created_at,processed_by,txn_receipt,reserved) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (uid, 'test', 'acct', 30.0, 0.0, 30.0, 'processing', '2026-10-15 00:00:00', m.ADMIN_ID, 'TXN-WITHDRAW-810014', 1),
        )
        withdraw_id = m.cursor.lastrowid
        m.conn.commit()

        result, status = m.cancel_pending_withdraw_atomic(withdraw_id, m.ADMIN_ID, 'بيانات الحساب غير صحيحة')
        self.assertEqual(status, 'ok')
        self.assertTrue(result['reserved'])
        balance = m.cursor.execute(
            "SELECT balance FROM users WHERE user_id=?", (uid,)
        ).fetchone()[0]
        txn_status = m.cursor.execute(
            "SELECT status FROM transactions WHERE receipt_number='TXN-WITHDRAW-810014'"
        ).fetchone()[0]
        self.assertEqual(balance, 100.0)
        self.assertEqual(txn_status, 'cancelled')

        _, second_status = m.cancel_pending_withdraw_atomic(withdraw_id, m.ADMIN_ID, 'محاولة ثانية')
        balance_after = m.cursor.execute(
            "SELECT balance FROM users WHERE user_id=?", (uid,)
        ).fetchone()[0]
        self.assertEqual(second_status, 'invalid_status')
        self.assertEqual(balance_after, 100.0)

    def test_withdraw_cancellation_rolls_back_if_reserved_balance_cannot_be_refunded(self):
        m = self.m
        missing_uid = 819999
        m.cursor.execute(
            "DELETE FROM users WHERE user_id=?", (missing_uid,)
        )
        m.cursor.execute(
            "INSERT INTO pending_withdraws(user_id,method,account,amount,commission,net_amount,status,created_at,processed_by,reserved) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (missing_uid, 'test', 'acct', 30.0, 0.0, 30.0, 'processing', '2026-10-15 00:00:00', m.ADMIN_ID, 1),
        )
        withdraw_id = m.cursor.lastrowid
        m.conn.commit()

        result, status = m.cancel_pending_withdraw_atomic(
            withdraw_id, m.ADMIN_ID, 'اختبار مستخدم غير موجود'
        )
        request_status = m.cursor.execute(
            "SELECT status FROM pending_withdraws WHERE id=?", (withdraw_id,)
        ).fetchone()[0]

        self.assertIsNone(result)
        self.assertEqual(status, 'user_not_found')
        self.assertEqual(request_status, 'processing')

    def test_charge_cancellation_is_atomic_and_refuses_completed_requests(self):
        m = self.m
        uid = 810012
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, site_balance, deleted) VALUES (?,?,?,0)",
            (uid, 50.0, 0.0),
        )
        m.cursor.execute(
            "INSERT INTO transactions(user_id,type,amount,commission,net_amount,method,status,transaction_date,admin_id,details,receipt_number,external_ref) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid, 'charge_request', 0, 0, 0, 'test', 'pending', '2026-10-15 00:00:00', None, '', 'TXN-CANCEL-810012', ''),
        )
        m.cursor.execute(
            "INSERT INTO pending_charges(user_id,method,receipt_number,amount,status,created_at,txn_receipt) "
            "VALUES (?,?,?,?,?,?,?)",
            (uid, 'test', 'PAY-CANCEL-810012', 10, 'pending', '2026-10-15 00:00:00', 'TXN-CANCEL-810012'),
        )
        charge_id = m.cursor.lastrowid
        m.conn.commit()

        result, status = m.cancel_pending_charge_atomic(charge_id, 555553, 'رقم العملية غير صحيح')
        self.assertEqual(status, 'ok')
        self.assertEqual(result['user_id'], uid)
        state = m.cursor.execute(
            "SELECT status FROM pending_charges WHERE id=?", (charge_id,)
        ).fetchone()[0]
        txn_state = m.cursor.execute(
            "SELECT status FROM transactions WHERE receipt_number='TXN-CANCEL-810012'"
        ).fetchone()[0]
        self.assertEqual(state, 'cancelled')
        self.assertEqual(txn_state, 'cancelled')

        _, second_status = m.cancel_pending_charge_atomic(charge_id, 555553, 'محاولة ثانية')
        self.assertEqual(second_status, 'invalid_status')

        m.cursor.execute(
            "INSERT INTO pending_charges(user_id,method,receipt_number,amount,status,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (uid, 'test', 'PAY-DONE-810012', 10, 'completed', '2026-10-15 00:00:00'),
        )
        completed_id = m.cursor.lastrowid
        m.conn.commit()
        _, completed_status = m.cancel_pending_charge_atomic(completed_id, 555553, 'إلغاء متأخر')
        self.assertEqual(completed_status, 'invalid_status')


    def test_admin_home_is_categorized_and_avoids_nested_owner_menu(self):
        m = self.m
        keyboard = m.get_full_admin_keyboard()
        callbacks = [
            button.callback_data
            for row in keyboard.keyboard
            for button in row
        ]
        self.assertIn('admin_cat_users', callbacks)
        self.assertIn('admin_cat_finance', callbacks)
        self.assertIn('admin_cat_services', callbacks)
        self.assertIn('admin_cat_content', callbacks)
        self.assertIn('admin_cat_reports', callbacks)
        self.assertIn('admin_cat_system', callbacks)
        self.assertNotIn('admin_buttons', callbacks)
        self.assertNotIn('admin_payment', callbacks)

    def test_admin_category_callback_opens_expected_section(self):
        m = self.m
        with patch.object(m.bot, 'answer_callback_query'), patch.object(m.bot, 'edit_message_text') as edit:
            m.handle_all_callbacks(self.fake_call('admin_cat_users'))
        edit.assert_called_once()
        kwargs = edit.call_args.kwargs
        self.assertIn('المستخدمون والمشرفون', edit.call_args.args[0])
        buttons = [
            button.callback_data
            for row in kwargs['reply_markup'].keyboard
            for button in row
        ]
        self.assertIn('admin_users', buttons)
        self.assertIn('admin_moderators', buttons)
        self.assertIn('back_to_full_admin', buttons)

    def test_log_search_keyboard_uses_registered_callback_ids(self):
        m = self.m
        keyboard = m.get_search_keyboard()
        callbacks = [
            button.callback_data
            for row in keyboard.keyboard
            for button in row
        ]
        self.assertIn('search_logs_date', callbacks)
        self.assertIn('search_logs_admin', callbacks)
        self.assertIn('search_logs_type', callbacks)
        self.assertIn('search_logs_amount', callbacks)
        self.assertIn('search_logs_user', callbacks)
        self.assertIn('admin_logs', callbacks)
        self.assertNotIn('search_by_date', callbacks)
        self.assertNotIn('back_to_logs', callbacks)

    def test_open_support_ticket_reply_button_registers_valid_reply_handler(self):
        m = self.m
        target_user_id = 812341
        m.cursor.execute(
            "INSERT INTO tickets(user_id, message, status, created_at) VALUES (?,?,?,?)",
            (target_user_id, "مشكلة اختبار", "open", "2026-10-17 00:00:00"),
        )
        ticket_id = m.cursor.lastrowid
        m.conn.commit()
        call = self.fake_call(f"reply_ticket_{ticket_id}_{target_user_id}")
        with patch.object(m.bot, 'answer_callback_query'), patch.object(m.bot, 'send_message'), patch.object(m.bot, 'register_next_step_handler_by_chat_id') as register:
            m.handle_all_callbacks(call)
        register.assert_called_once_with(
            m.ADMIN_ID,
            m.ActionSystem.process_ticket_reply,
            ticket_id,
            target_user_id,
        )

    def test_support_ticket_reply_is_saved_and_delivered(self):
        m = self.m
        target_user_id = 812342
        m.cursor.execute(
            "INSERT INTO tickets(user_id, message, status, created_at) VALUES (?,?,?,?)",
            (target_user_id, "مشكلة اختبار ثانية", "open", "2026-10-17 00:00:00"),
        )
        ticket_id = m.cursor.lastrowid
        m.conn.commit()
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=m.ADMIN_ID),
            chat=SimpleNamespace(id=m.ADMIN_ID),
            text="تم حل المشكلة، جرّب الآن.",
        )
        with patch.object(m.bot, 'send_message') as send:
            m.ActionSystem.process_ticket_reply(message, ticket_id, target_user_id)
        stored = m.cursor.execute(
            "SELECT sender_id, sender_type, message FROM ticket_conversations WHERE ticket_id=? ORDER BY id DESC LIMIT 1",
            (ticket_id,),
        ).fetchone()
        self.assertEqual(stored, (m.ADMIN_ID, 'admin', "تم حل المشكلة، جرّب الآن."))
        self.assertTrue(any(call.args[0] == target_user_id for call in send.call_args_list))
        status = m.cursor.execute(
            "SELECT status FROM tickets WHERE ticket_id=?", (ticket_id,)
        ).fetchone()[0]
        self.assertEqual(status, 'open')

    def test_owner_admin_entry_opens_categorized_panel_directly(self):
        m = self.m
        with patch.object(m.ActionSystem, 'show_full_admin_menu') as show_full:
            m.ActionSystem.show_admin_panel(m.ADMIN_ID, m.ADMIN_ID)
        show_full.assert_called_once_with(m.ADMIN_ID, m.ADMIN_ID)


    def test_control_center_contains_mode_maintenance_and_all_service_controls(self):
        m = self.m
        keyboard = m.get_operations_control_keyboard()
        callbacks = [button.callback_data for row in keyboard.keyboard for button in row]
        self.assertIn('request_real_mode', callbacks)
        self.assertIn('control_toggle_bot', callbacks)
        self.assertIn('toggle_syriatel', callbacks)
        self.assertIn('toggle_sham', callbacks)
        self.assertIn('toggle_usdt', callbacks)
        self.assertIn('toggle_binance', callbacks)
        self.assertIn('control_toggle_wheel', callbacks)
        self.assertIn('admin_api_connect', callbacks)
        self.assertIn('admin_payment', callbacks)

    def test_service_toggles_are_not_scattered_in_payment_limits_keyboard(self):
        m = self.m
        keyboard = m.get_payment_settings_keyboard()
        callbacks = [button.callback_data for row in keyboard.keyboard for button in row]
        self.assertIn('edit_limits', callbacks)
        self.assertIn('edit_commission', callbacks)
        self.assertNotIn('toggle_syriatel', callbacks)
        self.assertNotIn('toggle_sham', callbacks)
        self.assertNotIn('toggle_usdt', callbacks)
        self.assertNotIn('toggle_binance', callbacks)
        self.assertNotIn('toggle_bot', callbacks)

    def test_real_mode_switch_requires_a_separate_real_database(self):
        m = self.m
        with patch.dict(m.os.environ, {'REAL_DATABASE_URL': '', 'DATABASE_URL': ''}, clear=False):
            with self.assertRaisesRegex(ValueError, 'REAL_DATABASE_URL'):
                m.switch_operation_mode('real', m.ADMIN_ID)
        self.assertEqual(m.get_operation_mode(), 'demo')

    def test_full_admin_keyboard_includes_dedicated_control_category(self):
        m = self.m
        keyboard = m.get_full_admin_keyboard()
        callbacks = [button.callback_data for row in keyboard.keyboard for button in row]
        self.assertIn('admin_cat_control', callbacks)

    def test_non_owner_cannot_toggle_maintenance_from_control_center(self):
        m = self.m
        before = m.get_db_setting('bot_status')
        call = self.fake_call('control_toggle_bot')
        call.from_user.id = m.ADMIN_ID + 1
        with patch.object(m, 'safe_answer_callback') as answer:
            m.handle_all_callbacks(call)
        answer.assert_called_once()
        self.assertEqual(m.get_db_setting('bot_status'), before)


    def test_mode_configuration_sync_never_copies_users_or_financial_transactions(self):
        m = self.m
        source = sqlite3.connect(':memory:')
        target = sqlite3.connect(':memory:')
        schema = [
            "CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT, updated_by INTEGER)",
            "CREATE TABLE dynamic_buttons (id INTEGER PRIMARY KEY AUTOINCREMENT, button_text TEXT, parent_button TEXT)",
            "CREATE TABLE moderators (user_id INTEGER PRIMARY KEY, custom_name TEXT)",
            "CREATE TABLE notification_settings (user_id INTEGER PRIMARY KEY, notify_on_charge INTEGER)",
            "CREATE TABLE operations_room (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER UNIQUE, created_at TEXT)",
            "CREATE TABLE api_configs (id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT, name TEXT, api_key TEXT, api_secret TEXT, endpoint TEXT, extra_config TEXT, is_active INTEGER, is_paused INTEGER, created_at TEXT, updated_at TEXT, created_by INTEGER)",
            "CREATE TABLE api_connections (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, api_key TEXT, api_secret TEXT, endpoint TEXT, is_active INTEGER, last_verified TEXT, verified_by INTEGER, created_at TEXT, updated_at TEXT, connection_status TEXT)",
            "CREATE TABLE users (user_id INTEGER PRIMARY KEY, balance REAL)",
            "CREATE TABLE transactions (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)",
        ]
        for db in (source, target):
            for statement in schema:
                db.execute(statement)
        source.execute("INSERT INTO settings(key,value) VALUES('operation_mode','demo')")
        source.execute("INSERT INTO dynamic_buttons(button_text,parent_button) VALUES('زر تجريبي','main')")
        source.execute("INSERT INTO users(user_id,balance) VALUES(101,500)")
        source.execute("INSERT INTO transactions(id,user_id,amount) VALUES(1,101,500)")
        target.execute("INSERT INTO settings(key,value) VALUES('operation_mode','old')")
        target.execute("INSERT INTO users(user_id,balance) VALUES(202,900)")
        target.execute("INSERT INTO transactions(id,user_id,amount) VALUES(2,202,900)")
        source.commit()
        target.commit()
        try:
            m._copy_mode_configuration(source, target)
            self.assertEqual(
                target.execute("SELECT value FROM settings WHERE key='operation_mode'").fetchone()[0],
                'demo',
            )
            self.assertEqual(target.execute("SELECT user_id,balance FROM users").fetchall(), [(202, 900.0)])
            self.assertEqual(target.execute("SELECT id,user_id,amount FROM transactions").fetchall(), [(2, 202, 900.0)])
            self.assertEqual(target.execute("SELECT button_text FROM dynamic_buttons").fetchall(), [('زر تجريبي',)])
        finally:
            source.close()
            target.close()

    def test_control_category_routes_to_the_control_panel(self):
        m = self.m
        call = self.fake_call('admin_cat_control')
        with patch.object(m, 'render_operations_control') as render:
            m.handle_all_callbacks(call)
        render.assert_called_once_with(m.ADMIN_ID, 1)

    def test_maintenance_blocks_customer_callbacks(self):
        m = self.m
        call = self.fake_call('ai_chat')
        call.from_user.id = m.ADMIN_ID + 10
        with patch.object(m, 'check_bot_status', return_value=False), \\
             patch.object(m, 'safe_answer_callback') as answer, \\
             patch.object(m, 'start_ai_chat') as start_ai:
            m.handle_all_callbacks(call)
        answer.assert_called_once()
        start_ai.assert_not_called()


    def test_database_target_comparison_ignores_connection_query_parameters(self):
        m = self.m
        self.assertTrue(m._same_database_target(
            'postgresql://user:pass@db.example/neon?sslmode=require',
            'postgresql://user:pass@db.example/neon?sslmode=verify-full',
        ))
        self.assertFalse(m._same_database_target(
            'postgresql://user:pass@db.example/demo',
            'postgresql://user:pass@db.example/production',
        ))

    def test_operation_mode_cannot_be_changed_without_switching_database(self):
        m = self.m
        with self.assertRaisesRegex(ValueError, 'switch_operation_mode'):
            m.update_db_setting('operation_mode', 'real', m.ADMIN_ID)
        self.assertEqual(m.get_operation_mode(), 'demo')

    def test_ai_command_obeys_maintenance_mode(self):
        m = self.m
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=m.ADMIN_ID + 11),
            chat=SimpleNamespace(id=m.ADMIN_ID + 11),
        )
        with patch.object(m, 'check_bot_status', return_value=False), \\
             patch.object(m.bot, 'send_message') as send, \\
             patch.object(m, 'show_ai_menu') as show_ai:
            m.handle_ai_command(message)
        send.assert_called_once()
        show_ai.assert_not_called()


if __name__ == '__main__':
    unittest.main()
