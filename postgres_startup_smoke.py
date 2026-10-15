"""Integration smoke test: run the real bot schema and compatibility checks on PostgreSQL."""
import importlib.util
import os
from pathlib import Path

from matar_db import restore_postgres_snapshot

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

# Exercise the financial transaction paths against a real PostgreSQL engine.
import json
import secrets

test_user_id = -int(secrets.randbelow(8_000_000_000_000_000) + 1)
backup_path = None
try:
    module.conn.execute(
        "INSERT INTO users(user_id,balance,site_balance,deleted,created_at) VALUES (?,?,?,?,?)",
        (test_user_id, 0, 0, 0, "2000-01-01 00:00:00"),
    )
    module.conn.commit()

    module.admin_adjust_balance_atomic(test_user_id, 100, "bot_charge", module.ADMIN_ID)
    bot_balance, site_balance = module.transfer_internal_balance(test_user_id, 25, "to_site")
    if abs(bot_balance - 75) > 0.001 or abs(site_balance - 25) > 0.001:
        raise SystemExit(f"PostgreSQL balance transfer mismatch: {bot_balance}, {site_balance}")

    pending, status = module.create_pending_withdraw_atomic(
        test_user_id, "integration-test", "test-account", 10, 0, 10, "USD"
    )
    if status != "ok" or not pending:
        raise SystemExit(f"PostgreSQL withdrawal reservation failed: {status}")
    _, status = module.cancel_pending_withdraw_atomic(pending[0], module.ADMIN_ID, "CI integration test")
    if status != "ok":
        raise SystemExit(f"PostgreSQL withdrawal cancellation failed: {status}")

    balance, _ = module.credit_referral_payout_atomic(test_user_id, 5, module.ADMIN_ID)
    if abs(balance - 80) > 0.001:
        raise SystemExit(f"PostgreSQL referral payout mismatch: {balance}")

    pending_charge, status = module.create_pending_charge_atomic(
        test_user_id, "integration-test", "manual", f"PG-CI-CHARGE-{test_user_id}"
    )
    if status != "ok" or not pending_charge:
        raise SystemExit(f"PostgreSQL pending charge creation failed: {status}")
    charge_id = pending_charge[0]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: module.complete_pending_charge(charge_id, module.ADMIN_ID, 10),
            range(2),
        ))
    statuses = sorted(result[1] for result in results)
    if statuses != ["already_completed", "ok"]:
        raise SystemExit(f"Concurrent PostgreSQL charge completion was not idempotent: {statuses}")
    balance = module.conn.execute("SELECT balance FROM users WHERE user_id=?", (test_user_id,)).fetchone()[0]
    if abs(float(balance) - 90) > 0.001:
        raise SystemExit(f"Concurrent PostgreSQL charge credited an incorrect amount: {balance}")

    backup_path = module.create_consistent_backup(module.ADMIN_ID)
    with open(backup_path, "r", encoding="utf-8") as backup_file:
        snapshot = json.load(backup_file)
    if snapshot.get("format") != "matar-postgres-snapshot-v1" or "users" not in snapshot.get("tables", {}):
        raise SystemExit("PostgreSQL JSON snapshot validation failed.")

    # Prove a deleted row can be recovered from the JSON snapshot.
    module.conn.execute("DELETE FROM users WHERE user_id=?", (test_user_id,))
    module.conn.commit()
    restored = restore_postgres_snapshot(module.conn, snapshot)
    recovered = module.conn.execute(
        "SELECT balance,site_balance FROM users WHERE user_id=?", (test_user_id,)
    ).fetchone()
    if restored.get("tables") != tables or not recovered or abs(float(recovered[0]) - 90) > 0.001:
        raise SystemExit("PostgreSQL JSON restore did not recover the expected financial state.")

finally:
    module.conn.rollback()
    for table in (
        "transactions", "pending_withdraws", "pending_charges", "processed_transactions",
        "wheel_spins", "wheel_bonuses", "gift_usage", "ai_conversations",
    ):
        module.conn.execute(f"DELETE FROM {table} WHERE user_id=?", (test_user_id,))
    module.conn.execute("DELETE FROM referrals_log WHERE referrer_id=? OR referred_id=?", (test_user_id, test_user_id))
    module.conn.execute("DELETE FROM referral_earnings WHERE referrer_id=? OR from_user_id=?", (test_user_id, test_user_id))
    module.conn.execute("DELETE FROM users WHERE user_id=?", (test_user_id,))
    if backup_path:
        import os
        backup_name = Path(backup_path).name
        module.conn.execute("DELETE FROM backups WHERE backup_name=?", (backup_name,))
        try:
            os.remove(backup_path)
        except OSError:
            pass
    module.conn.commit()

if module.conn.in_transaction:
    module.conn.rollback()
    raise SystemExit("PostgreSQL test left an unexpected open transaction.")

print(f"PostgreSQL startup, concurrent charge idempotency, financial operations, and JSON backup/restore passed: {tables} tables.")
module.conn.close()
