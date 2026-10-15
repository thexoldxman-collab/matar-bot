import unittest

from matar_db import translate_sql


class SQLTranslationTests(unittest.TestCase):
    def test_ignores_sqlite_runtime_pragmas(self):
        self.assertEqual(translate_sql("PRAGMA journal_mode=WAL"), (None, None))
        self.assertEqual(translate_sql("PRAGMA foreign_keys=ON"), (None, None))

    def test_table_info_uses_compatibility_marker(self):
        self.assertEqual(
            translate_sql("PRAGMA table_info('dynamic_buttons')"),
            ("__MATAR_TABLE_INFO__:dynamic_buttons", None),
        )

    def test_insert_generates_expected_id_column_and_postgres_placeholder(self):
        sql, generated = translate_sql(
            "INSERT INTO tickets(user_id,message) VALUES (?,?)"
        )
        self.assertEqual(generated, "ticket_id")
        self.assertEqual(
            sql,
            "INSERT INTO tickets(user_id,message) VALUES (%s,%s) RETURNING ticket_id",
        )

    def test_pending_charge_insert_has_generated_id(self):
        sql, generated = translate_sql(
            "INSERT INTO pending_charges(user_id,method) VALUES (?,?)"
        )
        self.assertEqual(generated, "id")
        self.assertTrue(sql.endswith("RETURNING id"))

    def test_begin_immediate_becomes_begin(self):
        self.assertEqual(translate_sql("BEGIN IMMEDIATE"), ("BEGIN", None))

    def test_replace_only_allows_explicitly_mapped_tables(self):
        sql, _ = translate_sql(
            "INSERT OR REPLACE INTO operations_room(chat_id,created_at) VALUES (?,?)"
        )
        self.assertIn("ON CONFLICT (chat_id) DO UPDATE", sql)
        self.assertIn("VALUES (%s,%s)", sql)
        with self.assertRaises(ValueError):
            translate_sql("INSERT OR REPLACE INTO users(id) VALUES (?)")

    def test_insert_or_ignore_translates_to_on_conflict_do_nothing(self):
        sql, _ = translate_sql(
            "INSERT OR IGNORE INTO pending_charges(user_id,method) VALUES (?,?)"
        )
        self.assertIn("ON CONFLICT DO NOTHING", sql)
        self.assertIn("RETURNING id", sql)


    def test_sqlite_relative_date_modifiers_translate_safely(self):
        sql, _ = translate_sql(
            "SELECT COUNT(*) FROM transactions WHERE transaction_date >= DATE('now', '-7 days')"
        )
        self.assertIn("TO_CHAR(CURRENT_DATE - INTERVAL '7 day', 'YYYY-MM-DD')", sql)
        self.assertNotIn("DATE('now', '-7 days')", sql)
        sql, _ = translate_sql("SELECT DATE('now', '+2 weeks')")
        self.assertIn("TO_CHAR(CURRENT_DATE + INTERVAL '2 week', 'YYYY-MM-DD')", sql)

if __name__ == "__main__":
    unittest.main()
