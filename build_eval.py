"""
Writes eval/questions.jsonl (tier 1) and verifies every gold query runs.

Run from the project root:  python build_eval.py
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path("data/chinook.db")
EVAL_PATH = Path("eval/questions.jsonl")

QUESTIONS = [
    {
        "id": 1,
        "tier": 1,
        "question": "How many tracks are in the database?",
        "gold_sql": "SELECT COUNT(*) FROM Track;",
    },
    {
        "id": 2,
        "tier": 1,
        "question": "List all genre names.",
        "gold_sql": "SELECT Name FROM Genre;",
    },
    {
        "id": 3,
        "tier": 1,
        "question": "What is the average track price?",
        "gold_sql": "SELECT AVG(UnitPrice) FROM Track;",
    },
    {
        "id": 4,
        "tier": 1,
        "question": "How many customers are from Brazil?",
        "gold_sql": "SELECT COUNT(*) FROM Customer WHERE Country = 'Brazil';",
    },
    {
        "id": 5,
        "tier": 1,
        "question": "What is the total revenue across all invoices?",
        "gold_sql": "SELECT SUM(Total) FROM Invoice;",
    },
    {
        "id": 6,
        "tier": 1,
        "question": "What are the five longest tracks, with their durations in milliseconds?",
        "gold_sql": (
            "SELECT Name, Milliseconds FROM Track "
            "ORDER BY Milliseconds DESC, TrackId LIMIT 5;"
        ),
    },
    {
        "id": 7,
        "tier": 1,
        "question": "Which customers have no company listed? Give their first and last name.",
        "gold_sql": (
            "SELECT FirstName, LastName FROM Customer "
            "WHERE Company IS NULL ORDER BY CustomerId;"
        ),
    },
    {
        "id": 8,
        "tier": 1,
        "question": "How many customers are there in each country, highest first?",
        "gold_sql": (
            "SELECT Country, COUNT(*) AS CustomerCount FROM Customer "
            "GROUP BY Country ORDER BY CustomerCount DESC, Country;"
        ),
    },
    {
        "id": 9,
        "tier": 1,
        "question": "What are the distinct track prices?",
"gold_sql": "SELECT DISTINCT UnitPrice FROM Track ORDER BY UnitPrice;",
    },
    {
        "id": 10,
        "tier": 1,
        "question": "How many employees report to someone else?",
        "gold_sql": "SELECT COUNT(*) FROM Employee WHERE ReportsTo IS NOT NULL;",
    },
    {
        "id": 11,
        "tier": 2,
        "question": "Which five artists have the most albums?",
        "gold_sql": (
            "SELECT ar.Name, COUNT(*) AS AlbumCount "
            "FROM Album al JOIN Artist ar ON al.ArtistId = ar.ArtistId "
            "GROUP BY ar.ArtistId, ar.Name "
            "ORDER BY AlbumCount DESC, ar.Name LIMIT 5;"
        ),
    },
    {
        "id": 12,
        "tier": 2,
        "question": "List the track names on the album 'Let There Be Rock'.",
        "gold_sql": (
            "SELECT t.Name FROM Track t "
            "JOIN Album al ON t.AlbumId = al.AlbumId "
            "WHERE al.Title = 'Let There Be Rock' ORDER BY t.TrackId;"
        ),
    },
    {
        "id": 13,
        "tier": 2,
        "question": "How many tracks are in each genre, highest first?",
        "gold_sql": (
            "SELECT g.Name, COUNT(*) AS TrackCount "
            "FROM Track t JOIN Genre g ON t.GenreId = g.GenreId "
            "GROUP BY g.GenreId, g.Name "
            "ORDER BY TrackCount DESC, g.Name;"
        ),
    },
    {
        "id": 14,
        "tier": 2,
        "question": (
            "Which customers are supported by employee Jane Peacock? "
            "Give their first and last name."
        ),
        "gold_sql": (
            "SELECT c.FirstName, c.LastName FROM Customer c "
            "JOIN Employee e ON c.SupportRepId = e.EmployeeId "
            "WHERE e.FirstName = 'Jane' AND e.LastName = 'Peacock' "
            "ORDER BY c.CustomerId;"
        ),
    },
    {
        "id": 15,
        "tier": 2,
        "question": "Which five artists brought in the most revenue?",
        "gold_sql": (
            "SELECT ar.Name, ROUND(SUM(il.UnitPrice * il.Quantity), 2) AS Revenue "
            "FROM InvoiceLine il "
            "JOIN Track t ON il.TrackId = t.TrackId "
            "JOIN Album al ON t.AlbumId = al.AlbumId "
            "JOIN Artist ar ON al.ArtistId = ar.ArtistId "
            "GROUP BY ar.ArtistId, ar.Name "
            "ORDER BY Revenue DESC, ar.Name LIMIT 5;"
        ),
    },
]


def write_eval_set() -> None:
    EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVAL_PATH.open("w", encoding="utf-8") as f:
        for q in QUESTIONS:
            f.write(json.dumps(q) + "\n")
    print(f"Wrote {len(QUESTIONS)} questions to {EVAL_PATH}\n")


def verify() -> None:
    conn = sqlite3.connect(DB_PATH)
    for q in QUESTIONS:
        rows = conn.execute(q["gold_sql"]).fetchall()
        print(f"[{q['id']}] {q['question']}")
        print(f"     {q['gold_sql']}")
        preview = rows[:5]
        print(f"     -> {len(rows)} row(s): {preview}")
        if len(rows) > 5:
            print("        (truncated)")
        print()
    conn.close()


if __name__ == "__main__":
    write_eval_set()
    verify()
