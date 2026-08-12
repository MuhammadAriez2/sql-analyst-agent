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
        "question": (
            "What are the five longest tracks? Give two columns: track name "
            "and duration in milliseconds."
        ),
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
    {
        "id": 16,
        "tier": 3,
        "question": (
            "For each employee, give two columns: the employee's full name and "
            "their manager's full name. Include employees who have no manager."
        ),
        "gold_sql": (
            "SELECT e.FirstName || ' ' || e.LastName AS Employee, "
            "m.FirstName || ' ' || m.LastName AS Manager "
            "FROM Employee e LEFT JOIN Employee m ON e.ReportsTo = m.EmployeeId "
            "ORDER BY e.EmployeeId;"
        ),
    },
    {
        "id": 17,
        "tier": 3,
        "question": (
            "Which customers have spent more than the average customer? "
            "Give first name, last name, and total spend as three separate columns."
        ),
        "gold_sql": (
            "SELECT c.FirstName, c.LastName, ROUND(SUM(i.Total), 2) AS Spend "
            "FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId "
            "GROUP BY c.CustomerId "
            "HAVING SUM(i.Total) > ("
            "SELECT AVG(t.s) FROM (SELECT SUM(Total) s FROM Invoice GROUP BY CustomerId) t"
            ") ORDER BY Spend DESC, c.LastName, c.FirstName;"
        ),
    },
    {
        "id": 18,
        "tier": 3,
        "question": "For each genre, which single track earned the most revenue?",
        "gold_sql": (
            "SELECT Genre, TrackName, Rev FROM ("
            "SELECT g.Name AS Genre, t.Name AS TrackName, "
            "ROUND(SUM(il.UnitPrice * il.Quantity), 2) AS Rev, "
            "ROW_NUMBER() OVER (PARTITION BY g.GenreId "
            "ORDER BY SUM(il.UnitPrice * il.Quantity) DESC, t.TrackId) AS rn "
            "FROM InvoiceLine il "
            "JOIN Track t ON il.TrackId = t.TrackId "
            "JOIN Genre g ON t.GenreId = g.GenreId "
            "GROUP BY g.GenreId, t.TrackId) WHERE rn = 1 "
            "ORDER BY Rev DESC, Genre;"
        ),
    },
    {
        "id": 19,
        "tier": 3,
        "question": "Which genres have never had a single track purchased?",
        "gold_sql": (
            "SELECT g.Name FROM Genre g WHERE NOT EXISTS ("
            "SELECT 1 FROM Track t JOIN InvoiceLine il ON t.TrackId = il.TrackId "
            "WHERE t.GenreId = g.GenreId) ORDER BY g.Name;"
        ),
    },
    {
        "id": 20,
        "tier": 3,
        "question": "What was the total revenue for each month of 2023? Format each month as YYYY-MM.",
        "gold_sql": (
            "SELECT strftime('%Y-%m', InvoiceDate) AS Month, "
            "ROUND(SUM(Total), 2) AS Revenue FROM Invoice "
            "WHERE strftime('%Y', InvoiceDate) = '2023' "
            "GROUP BY Month ORDER BY Month;"
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
