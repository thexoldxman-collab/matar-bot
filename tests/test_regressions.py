import importlib.util
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
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

    def test_referral_payout_updates_balance_and_ledger_atomically(self):
        m = self.m
        uid = 810005
        m.cursor.execute(
            "INSERT OR REPLACE INTO users(user_id, balance, deleted) VALUES (?,?,0)",
            (uid, 100.0),
        )
        m.conn.commit()
        new_balance, receipt = m.credit_referral_payout_atomic(uid, 25, m.ADMIN_ID)
        row = m.cursor.execute(
            "SELECT balance FROM users WHERE user_id=?", (uid,)
        ).fetchone()
        ledger = m.cursor.execute(
            "SELECT type, amount, status, receipt_number FROM transactions WHERE receipt_number=?",
            (receipt,),
        ).fetchone()
        self.assertEqual(new_balance, 125.0)
        self.assertEqual(row[0], 125.0)
        self.assertEqual(ledger, ('referral_pay', 25.0, 'success', receipt))

    def test_referral_payout_rolls_back_balance_if_ledger_insert_fails(self):
        m = self.m
        uid = 810006
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
            self.assertEqual(balance, 100.0)
        finally:
            m.cursor.execute("DROP TRIGGER IF EXISTS test_fail_referral_ledger")
            m.conn.commit()

    def test_referral_payout_rejects_nonfinite_and_nonpositive_amounts(self):
        m = self.m
        for amount in (0, -1, float('nan'), float('inf')):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    m.credit_referral_payout_atomic(810005, amount, m.ADMIN_ID)


if __name__ == '__main__':
    unittest.main()
