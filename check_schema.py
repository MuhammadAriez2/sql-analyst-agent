import sqlite3

conn = sqlite3.connect("data/chinook.db")
rows = conn.execute(
    "SELECT sql FROM sqlite_master WHERE type='table'"
).fetchall()

for r in rows:
    print(r[0], "\n")