"""SQLite/PostgreSQL compatibility layer for the Matar Telegram bot.

The PostgreSQL path is intentionally opt-in through DATABASE_URL. It preserves
the legacy SQLite path for local tests while translating the small subset of
SQLite SQL syntax used by the existing application.
"""
from __future__ import annotations

import re
import sqlite3
import threading
import secrets
from typing import Any, Iterable

AUTOINCREMENT_COLUMNS = {
    "transactions": "id", "retry_queue": "id", "admin_logs": "id",
    "tickets": "ticket_id", "ticket_conversations": "id",
    "ai_conversations": "id", "referrals_log": "id",
    "referral_earnings": "id", "referral_cycles": "id",
    "dynamic_buttons": "id", "api_connections": "id",
    "operations_room": "id", "pending_charges": "id",
    "pending_withdraws": "id", "api_configs": "id", "backups": "id",
    "wheel_prizes": "id", "wheel_spins": "id", "wheel_bonuses": "id",
}

try:
    import psycopg
    from psycopg import IntegrityError as PostgresIntegrityError
except ImportError:  # SQLite-only development and unit tests need no psycopg.
    psycopg = None
    PostgresIntegrityError = None

DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError,) + (
    (PostgresIntegrityError,) if PostgresIntegrityError is not None else ()
)


def _append_sql_clause(sql: str, clause: str) -> str:
    sql = sql.rstrip().rstrip(";")
    return sql + " " + clause


def translate_sql(sql: str) -> tuple[str | None, str | None]:
    """Translate legacy SQLite SQL into PostgreSQL SQL.

    Returns (translated_sql, generated_id_column). A None SQL result represents
    a PRAGMA statement that is only meaningful for SQLite and can be ignored.
    """
    if not isinstance(sql, str):
        raise TypeError("SQL statement must be a string")
    original = sql.strip()
    if re.match(r"^PRAGMA\s+(journal_mode|synchronous|foreign_keys|wal_autocheckpoint)\b", original, re.I):
        return None, None

    table_info = re.match(r"^PRAGMA\s+table_info\s*\(\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*\)\s*;?$", original, re.I)
    if table_info:
        # Handled by PostgresCursor.execute, which queries information_schema.
        return "__MATAR_TABLE_INFO__:" + table_info.group(1).lower(), None

    query = original
    query = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "BIGSERIAL PRIMARY KEY", query, flags=re.I)
    query = re.sub(r"\bdatetime\s*\(\s*'now'\s*\)", "TO_CHAR(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS')", query, flags=re.I)
    query = re.sub(r"\bDATE\s*\(\s*'now'\s*\)", "CURRENT_DATE", query, flags=re.I)
    def _date_modifier(match):
        amount = int(match.group(1) + match.group(2))
        unit = match.group(3).lower().rstrip('s')
        if unit not in ('day', 'week', 'month', 'year') or abs(amount) > 3650:
            raise ValueError("Unsupported SQLite DATE modifier")
        sign = '+' if amount >= 0 else '-'
        return f"(CURRENT_DATE {sign} INTERVAL '{abs(amount)} {unit}')::date"
    query = re.sub(
        r"\bDATE\s*\(\s*'now'\s*,\s*'([+-]?)(\d+)\s+(days?|weeks?|months?|years?)'\s*\)",
        _date_modifier,
        query,
        flags=re.I,
    )
    query = re.sub(r"\bDATE\s*\(\s*(created_at|transaction_date)\s*\)", r"CAST(\1 AS DATE)", query, flags=re.I)
    query = re.sub(r"\bBEGIN\s+IMMEDIATE\b", "BEGIN", query, flags=re.I)

    replace_match = re.match(r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", query, re.I)
    ignore_match = re.match(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", query, re.I)
    insert_match = re.match(r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", query, re.I)
    generated_id = None

    if replace_match:
        table = replace_match.group(1).lower()
        query = re.sub(r"^\s*INSERT\s+OR\s+REPLACE\s+INTO\s+", "INSERT INTO ", query, count=1, flags=re.I)
        if table == "operations_room":
            query = _append_sql_clause(query, "ON CONFLICT (chat_id) DO UPDATE SET created_at=EXCLUDED.created_at")
        elif table == "deleted_accounts":
            columns = ("acc_name", "acc_password", "site_balance", "balance", "deleted_at", "restored_by", "restored_at")
            assignments = ", ".join(f"{column}=EXCLUDED.{column}" for column in columns)
            query = _append_sql_clause(query, f"ON CONFLICT (user_id) DO UPDATE SET {assignments}")
        else:
            raise ValueError(f"Unsupported legacy INSERT OR REPLACE table: {table}")
        insert_match = re.match(r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", query, re.I)
    elif ignore_match:
        table = ignore_match.group(1).lower()
        query = re.sub(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\s+", "INSERT INTO ", query, count=1, flags=re.I)
        query = _append_sql_clause(query, "ON CONFLICT DO NOTHING")
        insert_match = re.match(r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", query, re.I)

    if insert_match:
        table = insert_match.group(1).lower()
        if table in AUTOINCREMENT_COLUMNS and not re.search(r"\bRETURNING\b", query, re.I):
            generated_id = AUTOINCREMENT_COLUMNS[table]
            query = _append_sql_clause(query, f"RETURNING {generated_id}")

    # PostgreSQL uses %s placeholders. The bot's parameterized SQL does not
    # use literal question marks inside SQL string constants.
    query = query.replace("?", "%s")
    return query, generated_id


class PostgresCursor:
    """SQLite-like cursor proxy with independent state for each calling thread."""
    def __init__(self, connection: "PostgresConnection"):
        self._connection = connection
        self._local = threading.local()

    def _state(self):
        if not hasattr(self._local, "raw"):
            self._local.raw = self._connection._get_raw().cursor()
            self._local.synthetic_rows = None
            self._local.synthetic_pos = 0
            self._local.lastrowid = None
        return self._local

    @property
    def lastrowid(self):
        return self._state().lastrowid

    @lastrowid.setter
    def lastrowid(self, value):
        self._state().lastrowid = value

    def execute(self, sql: str, params: Iterable[Any] | None = None):
        state = self._state()
        state.lastrowid = None
        state.synthetic_rows = None
        state.synthetic_pos = 0
        translated, generated_id = translate_sql(sql)
        if translated is None:
            state.synthetic_rows = []
            return self
        if translated.startswith("__MATAR_TABLE_INFO__:"):
            table = translated.split(":", 1)[1]
            rows = state.raw.execute(
                """SELECT c.column_name, c.data_type, c.is_nullable, c.column_default,
                          (c.column_name IN (
                              SELECT kcu.column_name
                              FROM information_schema.table_constraints tc
                              JOIN information_schema.key_column_usage kcu
                                ON tc.constraint_catalog=kcu.constraint_catalog
                               AND tc.constraint_schema=kcu.constraint_schema
                               AND tc.constraint_name=kcu.constraint_name
                              WHERE tc.table_schema=current_schema()
                                AND tc.table_name=%s AND tc.constraint_type='PRIMARY KEY'
                          )) AS is_pk
                   FROM information_schema.columns c
                   WHERE c.table_schema=current_schema() AND c.table_name=%s
                   ORDER BY c.ordinal_position""",
                (table, table),
            ).fetchall()
            state.synthetic_rows = [
                (index, row[0], row[1], 1 if row[2] == "NO" else 0, row[3], 1 if row[4] else 0)
                for index, row in enumerate(rows)
            ]
            return self

        self._connection._begin_for_statement(translated)
        state.raw.execute(translated, tuple(params or ()))
        if generated_id:
            returned = state.raw.fetchone()
            state.lastrowid = returned[0] if returned else None
        return self

    def executemany(self, sql: str, seq_of_params: Iterable[Iterable[Any]]):
        state = self._state()
        translated, _ = translate_sql(sql)
        if translated is None or translated.startswith("__MATAR_TABLE_INFO__:"):
            raise ValueError("executemany is not supported for SQLite PRAGMA compatibility statements")
        self._connection._begin_for_statement(translated)
        state.raw.executemany(translated, seq_of_params)
        state.lastrowid = None
        state.synthetic_rows = None
        return self

    def fetchone(self):
        state = self._state()
        if state.synthetic_rows is not None:
            if state.synthetic_pos >= len(state.synthetic_rows):
                return None
            row = state.synthetic_rows[state.synthetic_pos]
            state.synthetic_pos += 1
            return row
        return state.raw.fetchone()

    def fetchall(self):
        state = self._state()
        if state.synthetic_rows is not None:
            rows = state.synthetic_rows[state.synthetic_pos:]
            state.synthetic_pos = len(state.synthetic_rows)
            return rows
        return state.raw.fetchall()

    def fetchmany(self, size: int | None = None):
        state = self._state()
        if state.synthetic_rows is not None:
            count = size or 1
            rows = state.synthetic_rows[state.synthetic_pos:state.synthetic_pos + count]
            state.synthetic_pos += len(rows)
            return rows
        return state.raw.fetchmany(size) if size is not None else state.raw.fetchmany()

    @property
    def rowcount(self):
        state = self._state()
        return len(state.synthetic_rows) if state.synthetic_rows is not None else state.raw.rowcount

    @property
    def description(self):
        return self._state().raw.description

    def close(self):
        state = self._state()
        state.raw.close()
        self._local = threading.local()


class _ThreadConnection:
    def __init__(self, url: str):
        self.url = url
        self.local = threading.local()
        self.lock = threading.RLock()

    def get(self):
        raw = getattr(self.local, "raw", None)
        if raw is None or raw.closed:
            if psycopg is None:
                raise RuntimeError("DATABASE_URL is set but psycopg is not installed; install requirements.txt")
            raw = psycopg.connect(self.url, autocommit=True, connect_timeout=15, application_name="matar-bot")
            self.local.raw = raw
        return raw


class PostgresConnection:
    """Thread-local PostgreSQL connections with a sqlite3-like call surface."""
    def __init__(self, url: str):
        self._thread_connections = _ThreadConnection(url)

    def _get_raw(self):
        return self._thread_connections.get()

    def _begin_for_statement(self, sql: str):
        # With autocommit enabled, SELECT behaves like SQLite's non-transactional
        # reads, while each write starts a transaction that remains open until
        # the application's existing commit()/rollback() call.
        if re.match(r"^\s*(INSERT|UPDATE|DELETE|MERGE)\b", sql, re.I):
            raw = self._get_raw()
            if raw.info.transaction_status == psycopg.pq.TransactionStatus.IDLE:
                raw.execute("BEGIN")

    def cursor(self):
        return PostgresCursor(self)

    def execute(self, sql: str, params: Iterable[Any] | None = None):
        return self.cursor().execute(sql, params)

    def commit(self):
        raw = self._get_raw()
        if raw.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
            raw.commit()

    def rollback(self):
        raw = self._get_raw()
        if raw.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
            raw.rollback()

    def close(self):
        raw = getattr(self._thread_connections.local, "raw", None)
        if raw is not None and not raw.closed:
            raw.close()
            self._thread_connections.local.raw = None

    def backup(self, target):
        raise RuntimeError("SQLite backup API is unavailable for PostgreSQL; use the JSON database snapshot.")

    @property
    def in_transaction(self):
        return self._get_raw().info.transaction_status != psycopg.pq.TransactionStatus.IDLE


def connect_database(database_url: str, sqlite_path: str):
    """Return PostgreSQL when DATABASE_URL is present, otherwise SQLite."""
    if database_url:
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is configured but psycopg is missing. Check requirements.txt.")
        return PostgresConnection(database_url)
    return sqlite3.connect(sqlite_path, check_same_thread=False, timeout=30)


def verify_postgres_compatibility(connection: PostgresConnection) -> None:
    """Exercise key legacy-SQL translations against the real database at startup.

    All test rows are rolled back. A failed check aborts startup instead of
    allowing the bot to run with a partially compatible database backend.
    """
    marker = "__matar_db_compatibility_check_" + secrets.token_hex(8)
    test_chat_id = -int(secrets.randbelow(9_000_000_000_000_000) + 1)
    connection.execute("BEGIN")
    try:
        ticket = connection.execute(
            "INSERT INTO tickets(user_id,message,status,created_at) VALUES (?,?,?,?)",
            (-1, "__matar_database_compatibility_check__", "closed", "2000-01-01 00:00:00"),
        )
        ticket_id = ticket.lastrowid
        if not ticket_id:
            raise RuntimeError("Neon compatibility check failed: ticket_id was not returned")
        row = connection.execute(
            "SELECT ticket_id, DATE(created_at) FROM tickets WHERE ticket_id=?",
            (ticket_id,),
        ).fetchone()
        if not row or row[0] != ticket_id or row[1] is None:
            raise RuntimeError("Neon compatibility check failed: generated IDs or date conversion")

        connection.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)",
            (marker, "first"),
        )
        connection.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)",
            (marker, "second"),
        )
        setting = connection.execute(
            "SELECT value FROM settings WHERE key=?",
            (marker,),
        ).fetchone()
        if not setting or setting[0] != "first":
            raise RuntimeError("Neon compatibility check failed: INSERT OR IGNORE")

        connection.execute(
            "INSERT OR REPLACE INTO operations_room(chat_id,created_at) VALUES (?,?)",
            (test_chat_id, "2000-01-01 00:00:00"),
        )
        connection.execute(
            "INSERT OR REPLACE INTO operations_room(chat_id,created_at) VALUES (?,?)",
            (test_chat_id, "2000-01-02 00:00:00"),
        )
        room = connection.execute(
            "SELECT created_at FROM operations_room WHERE chat_id=?",
            (test_chat_id,),
        ).fetchone()
        if not room or room[0] != "2000-01-02 00:00:00":
            raise RuntimeError("Neon compatibility check failed: INSERT OR REPLACE")

        moderator_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(moderators)").fetchall()
        }
        if "can_use_ai" not in moderator_columns:
            raise RuntimeError("Neon compatibility check failed: moderator schema migration")
        connection.execute("SELECT DATE('now'), datetime('now')").fetchone()
        connection.rollback()
    except Exception:
        connection.rollback()
        raise


def is_postgres_connection(connection: Any) -> bool:
    return isinstance(connection, PostgresConnection)
