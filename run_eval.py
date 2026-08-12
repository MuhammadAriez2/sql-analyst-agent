"""Evaluation harness.

Metric: EXECUTION ACCURACY. The gold query and the agent's query are both run,
and their result sets compared. Not string matching - there are many correct
ways to write the same query, and string comparison would mark correct SQL as
wrong.

Comparison rules:
  - Ordered comparison when the gold query has an ORDER BY (the question asked
    for an ordering, so order is part of correctness).
  - Unordered otherwise (sorted before comparing).
  - Floats rounded to 2dp, since SUM/AVG differ in the last bits depending on
    row order.
  - Column NAMES are ignored, values are not. An alias shouldn't fail a query.

Also reports RETRY LIFT: accuracy on attempt 1 vs. final accuracy. This is what
justifies the agent loop existing - if lift is ~0, the retry is dead weight.

Run:  python run_eval.py
"""

import json
import sqlite3
from collections import Counter
from pathlib import Path

from src.agent import ask
from src.schema import get_schema

DB_PATH = Path("data/chinook.db")
EVAL_PATH = Path("eval/questions.jsonl")
RESULTS_PATH = Path("eval/results.jsonl")


def run_gold(sql):
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        cur = conn.execute(sql)
        return cur.fetchall()
    finally:
        conn.close()


def _norm(rows):
    out = []
    for row in rows:
        out.append(tuple(
            round(v, 2) if isinstance(v, float) else v
            for v in row
        ))
    return out


def matches(gold_rows, pred_rows, ordered):
    g, p = _norm(gold_rows), _norm(pred_rows)
    if ordered:
        return g == p
    return Counter(g) == Counter(p)


def main():
    questions = [json.loads(l) for l in EVAL_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    schema = get_schema()

    results = []
    for q in questions:
        gold_rows = run_gold(q["gold_sql"])
        ordered = "ORDER BY" in q["gold_sql"].upper()

        r = ask(q["question"], schema=schema)

        correct = r.ok and matches(gold_rows, r.rows, ordered)

        # Was the FIRST attempt already correct? Needed for retry lift.
        first_sql = r.attempts[0][0] if r.attempts else None
        first_correct = False
        if first_sql and r.attempts[0][1] is None:
            first_correct = correct

        rec = {
            "id": q["id"],
            "tier": q["tier"],
            "question": q["question"],
            "gold_sql": q["gold_sql"],
            "pred_sql": r.sql,
            "attempts": r.n_attempts,
            "correct": correct,
            "first_correct": first_correct,
            "error": r.error,
            "failure_category": None,   # filled in by hand - see README
        }
        results.append(rec)

        mark = "PASS" if correct else "FAIL"
        print(f"[{q['id']:>2}] {mark}  attempts={r.n_attempts}  {q['question'][:55]}")
        if not correct:
            print(f"      pred: {r.sql}")
            if r.error:
                print(f"      err:  {r.error}")

    RESULTS_PATH.write_text(
        "\n".join(json.dumps(r) for r in results) + "\n", encoding="utf-8"
    )

    n = len(results)
    n_correct = sum(r["correct"] for r in results)
    n_first = sum(r["first_correct"] for r in results)

    print("\n" + "=" * 50)
    print(f"Execution accuracy : {n_correct}/{n} = {n_correct/n:.1%}")
    print(f"First-attempt      : {n_first}/{n} = {n_first/n:.1%}")
    print(f"Retry lift         : {(n_correct - n_first)/n:+.1%}")

    print("\nBy tier:")
    for tier in sorted({r["tier"] for r in results}):
        sub = [r for r in results if r["tier"] == tier]
        c = sum(r["correct"] for r in sub)
        print(f"  tier {tier}: {c}/{len(sub)} = {c/len(sub):.1%}")

    failures = [r["id"] for r in results if not r["correct"]]
    if failures:
        print(f"\nFailed IDs: {failures}")
        print(f"Categorise them by hand in {RESULTS_PATH}")


if __name__ == "__main__":
    main()
