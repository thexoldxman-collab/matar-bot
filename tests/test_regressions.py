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


if __name__ == '__main__':
    unittest.main()
