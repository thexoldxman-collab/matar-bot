"""Integration smoke test: run the real bot schema and compatibility checks on PostgreSQL."""
import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("ADMIN_ID", "999999")
os.environ.setdefault("DATABASE_PATH", "/tmp/matar-postgres-smoke.db")
os.environ.setdefault("BACKUP_DIR", "/tmp/matar-postgres-backups")
os.environ.setdefault("LOG_DIR", "/tmp/matar-postgres-logs")
os.environ["REQUIRE_PERSISTENT_DATABASE"] = "1"

if not os.environ.get("DATABASE_URL"):
    raise SystemExit("DATABASE_URL must point to the disposable PostgreSQL integration database.")

spec = importlib.util.spec_from_file_location("matar_postgres_smoke", ROOT / "Matar-bot-FINAL-merged.py")
if spec is None or spec.loader is None:
    raise SystemExit("Unable to load the bot module.")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if not module.is_postgres_connection(module.conn):
    raise SystemExit("The bot did not select PostgreSQL despite DATABASE_URL.")
tables = module.conn.execute(
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE'"
).fetchone()[0]
if tables < 25:
    raise SystemExit(f"Expected at least 25 bot tables, found {tables}.")
if module.conn.in_transaction:
    module.conn.rollback()
    raise SystemExit("Startup left an unexpected open PostgreSQL transaction.")

print(f"PostgreSQL startup passed: {tables} tables created, compatibility checks passed.")
module.conn.close()
