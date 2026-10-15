"""Integration smoke test: run the real bot schema against PostgreSQL when configured."""
import importlib.util
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_startup_smoke():
    os.environ.setdefault("TOKEN", "123456:TESTTOKEN")
    os.environ.setdefault("ADMIN_ID", "999999")
    os.environ.setdefault("DATABASE_PATH", "/tmp/matar-postgres-smoke.db")
    os.environ.setdefault("BACKUP_DIR", "/tmp/matar-postgres-backups")
    os.environ.setdefault("LOG_DIR", "/tmp/matar-postgres-logs")
    os.environ["REQUIRE_PERSISTENT_DATABASE"] = "1"

    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL must point to a disposable PostgreSQL integration database.")

    spec = importlib.util.spec_from_file_location(
        "matar_postgres_smoke", ROOT / "Matar-bot-FINAL-merged.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the bot module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    try:
        if not module.is_postgres_connection(module.conn):
            raise AssertionError("The bot did not select PostgreSQL despite DATABASE_URL.")
        tables = module.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema=current_schema() AND table_type='BASE TABLE'"
        ).fetchone()[0]
        if tables < 30:
            raise AssertionError(f"Expected at least 30 bot tables, found {tables}.")
        if module.conn.in_transaction:
            module.conn.rollback()
            raise AssertionError("Startup left an unexpected open PostgreSQL transaction.")
        return tables
    finally:
        module.conn.close()


class PostgresStartupSmokeTests(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("DATABASE_URL"),
        "DATABASE_URL is not set; PostgreSQL integration is run in a dedicated CI step.",
    )
    def test_full_bot_schema_starts_on_postgres(self):
        tables = run_startup_smoke()
        self.assertGreaterEqual(tables, 30)


if __name__ == "__main__":
    unittest.main(verbosity=2)
