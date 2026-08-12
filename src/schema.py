"""Schema introspection - gives the LLM a map of the database."""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/chinook.db")


def get_schema(db_path: Path = DB_PATH) -> str:
    """Return every CREATE TABLE statement as one string.

    This is what gets pasted into the prompt. The CREATE statements are used
    verbatim rather than a hand-written summary because they already carry
    column types and foreign keys, which is exactly what the model needs to
    pick a correct join path.
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
    ).fetchall()
    conn.close()
    return "\n\n".join(r[0] for r in rows)


if __name__ == "__main__":
    print(get_schema())
