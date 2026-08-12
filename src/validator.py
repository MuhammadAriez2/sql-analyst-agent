"""Validation + safe execution.

The agent runs model-written SQL against a real database, so this layer decides
what is allowed to execute. Three defences, in order:

  1. Static checks   - reject anything that isn't a single SELECT
  2. Read-only conn  - SQLite enforces it even if a check is bypassed
  3. Row + time caps - stop a valid-but-runaway query from hanging the app

Defence 1 alone is not enough: string checks can be fooled. Defence 2 is the
one that actually guarantees nothing is written.
"""

import re
import sqlite3
from pathlib import Path

DB_PATH = Path("data/chinook.db")

MAX_ROWS = 1000
TIMEOUT_MS = 5000

FORBIDDEN = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "REPLACE", "TRUNCATE", "ATTACH", "DETACH", "PRAGMA", "VACUUM",
}


class UnsafeQuery(Exception):
    """Raised when a query fails validation - never executed."""


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def validate(sql: str) -> str:
    """Return cleaned SQL, or raise UnsafeQuery."""
    cleaned = _strip_comments(sql).strip().rstrip(";").strip()

    if not cleaned:
        raise UnsafeQuery("Empty query.")

    # Reject multiple statements. Done after comment stripping so that a
    # semicolon hidden inside a comment doesn't trigger a false positive.
    if ";" in cleaned:
        raise UnsafeQuery("Multiple statements are not allowed.")

    first = cleaned.split(None, 1)[0].upper()
    if first not in ("SELECT", "WITH"):
        raise UnsafeQuery(f"Only SELECT queries are allowed, got: {first}")

    tokens = set(re.findall(r"[A-Za-z_]+", cleaned.upper()))
    hits = tokens & FORBIDDEN
    if hits:
        raise UnsafeQuery(f"Forbidden keyword(s): {', '.join(sorted(hits))}")

    return cleaned


def execute(sql: str, db_path: Path = DB_PATH):
    """Validate then run. Returns (columns, rows).

    Raises UnsafeQuery on validation failure, sqlite3.Error on a bad query.
    The caller distinguishes these: the first is a refusal, the second is
    feedback the agent can learn from and retry on.
    """
    cleaned = validate(sql)

    # mode=ro makes writes impossible at the driver level.
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)

    # Interrupt long queries: the handler fires every N VM steps.
    steps = {"n": 0}
    limit = TIMEOUT_MS * 100

    def guard():
        steps["n"] += 1000
        return 1 if steps["n"] > limit else 0

    conn.set_progress_handler(guard, 1000)

    try:
        cur = conn.execute(cleaned)
        rows = cur.fetchmany(MAX_ROWS)
        cols = [d[0] for d in cur.description] if cur.description else []
        return cols, rows
    finally:
        conn.close()


if __name__ == "__main__":
    tests = [
        "SELECT COUNT(*) FROM Track",
        "DROP TABLE Track",
        "SELECT 1; DELETE FROM Track",
        "SELECT * FROM Track -- ; DROP TABLE Track",
        "SELECT Name FROM Genre LIMIT 3",
        "UPDATE Track SET UnitPrice = 0",
    ]
    for t in tests:
        try:
            cols, rows = execute(t)
            print(f"OK      {t!r} -> {rows[:2]}")
        except UnsafeQuery as e:
            print(f"BLOCKED {t!r} -> {e}")
        except sqlite3.Error as e:
            print(f"SQLERR  {t!r} -> {e}")
