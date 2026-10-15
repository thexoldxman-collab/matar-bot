import unittest

from matar_db import translate_sql


class DatabaseTranslationTests(unittest.TestCase):
    def test_autoincrement_schema_uses_postgres_serial(self):
        sql, generated_id = translate_sql(
            "CREATE TABLE IF NOT EXISTS tickets (ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER)"
        )
        self.assertIn("ticket_id BIGSERIAL PRIMARY KEY", sql)
        self.assertEqual(generated_id, None)

    def test_insert_ignore_uses_conflict_safe_postgres_syntax(self):
        sql, generated_id = translate_sql(
            "INSERT OR IGNORE INTO settings(key, value) VALUES (?,?)"
        )
        self.assertTrue(sql.startswith("INSERT INTO settings"))
        self.assertIn("VALUES (%s,%s) ON CONFLICT DO NOTHING", sql)
        self.assertIsNone(generated_id)

    def test_generated_id_is_returned_for_legacy_lastrowid_usage(self):
        sql, generated_id = translate_sql(
            "INSERT INTO tickets(user_id, message) VALUES (?,?)"
        )
        self.assertTrue(sql.endswith("RETURNING id"))
        self.assertEqual(generated_id, "id")

    def test_replace_semantics_are_preserved_for_operations_room(self):
        sql, generated_id = translate_sql(
            "INSERT OR REPLACE INTO operations_room(chat_id, created_at) VALUES (?,?)"
        )
        self.assertIn("ON CONFLICT (chat_id) DO UPDATE SET created_at=EXCLUDED.created_at", sql)
        self.assertTrue(sql.endswith("RETURNING id"))
        self.assertEqual(generated_id, "id")

    def test_replace_semantics_are_preserved_for_deleted_accounts(self):
        sql, generated_id = translate_sql(
            "INSERT OR REPLACE INTO deleted_accounts(user_id, acc_name, balance) VALUES (?,?,?)"
        )
        self.assertIn("ON CONFLICT (user_id) DO UPDATE SET", sql)
        self.assertIn("acc_name=EXCLUDED.acc_name", sql)
        self.assertIsNone(generated_id)

    def test_sqlite_datetime_and_date_functions_are_translated(self):
        sql, _ = translate_sql(
            "SELECT DATE(created_at) FROM users WHERE expires_at > datetime('now') AND created_at >= DATE('now')"
        )
        self.assertIn("CAST(created_at AS DATE)", sql)
        self.assertIn("TO_CHAR(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS')", sql)
        self.assertIn("CURRENT_DATE", sql)

    def test_begin_immediate_and_placeholders_are_translated(self):
        sql, _ = translate_sql("BEGIN IMMEDIATE")
        self.assertEqual(sql, "BEGIN")
        sql, _ = translate_sql("UPDATE users SET balance=balance+? WHERE user_id=?")
        self.assertEqual(sql, "UPDATE users SET balance=balance+%s WHERE user_id=%s")

    def test_pragma_table_info_is_marked_for_compatibility_query(self):
        sql, _ = translate_sql("PRAGMA table_info(moderators)")
        self.assertEqual(sql, "__MATAR_TABLE_INFO__:moderators")

    def test_pragma_journal_settings_are_ignored_on_postgres(self):
        sql, _ = translate_sql("PRAGMA journal_mode=WAL")
        self.assertIsNone(sql)


if __name__ == "__main__":
    unittest.main()
