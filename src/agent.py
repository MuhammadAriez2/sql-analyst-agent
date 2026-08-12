"""The agent loop.

    question -> SQL -> validate -> execute
                 ^                    |
                 |____ error feedback _|   (max 2 retries)

Design decisions worth being able to defend:

  MAX_RETRIES = 2
    Attempt 2 fixes most errors (typo'd column, wrong table name). Attempt 3
    almost never converges - by then the model has usually misunderstood the
    question rather than the syntax, and a fresh error message doesn't help.
    Retry lift is measured in the eval, so this number is an empirical claim,
    not a guess.

  Full history is replayed on retry
    The model sees its own failed attempt and the exact database error. Sending
    only the error loses the context of what it tried, and it often regenerates
    the same broken query.

  Validation failures are NOT retried
    A blocked query means the model tried to write or ran a malformed statement.
    That is a refusal, not a correctable mistake.
"""

import os
import sqlite3

import anthropic
from dotenv import load_dotenv

from .schema import get_schema
from .validator import UnsafeQuery, execute

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_RETRIES = 2

SYSTEM = """You write SQLite queries against the schema below.

Rules:
- Return ONLY the SQL query. No explanation, no markdown fences.
- SELECT statements only.
- Use exact table and column names from the schema.
- Add a deterministic tiebreaker to ORDER BY when using LIMIT.

Schema:
{schema}"""


class Result:
    def __init__(self, question):
        self.question = question
        self.attempts = []      # list of (sql, error_or_None)
        self.sql = None
        self.columns = []
        self.rows = []
        self.error = None

    @property
    def ok(self):
        return self.error is None

    @property
    def n_attempts(self):
        return len(self.attempts)


def _generate(client, messages, schema):
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM.format(schema=schema),
        messages=messages,
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text.strip().removeprefix("```sql").removeprefix("```").removesuffix("```").strip()


def ask(question: str, schema: str = None, client=None) -> Result:
    """Run the full loop for one question."""
    schema = schema or get_schema()
    client = client or anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    result = Result(question)
    messages = [{"role": "user", "content": question}]

    for attempt in range(MAX_RETRIES + 1):
        sql = _generate(client, messages, schema)

        try:
            cols, rows = execute(sql)
            result.attempts.append((sql, None))
            result.sql, result.columns, result.rows = sql, cols, rows
            return result

        except UnsafeQuery as e:
            # Not retried - see module docstring.
            result.attempts.append((sql, f"BLOCKED: {e}"))
            result.error = f"Query blocked by validator: {e}"
            return result

        except sqlite3.Error as e:
            result.attempts.append((sql, str(e)))
            if attempt == MAX_RETRIES:
                result.error = f"Failed after {MAX_RETRIES + 1} attempts: {e}"
                return result
            messages += [
                {"role": "assistant", "content": sql},
                {"role": "user", "content": f"That query failed with: {e}\nFix it."},
            ]

    return result


if __name__ == "__main__":
    r = ask("Which five artists brought in the most revenue?")
    print(f"attempts: {r.n_attempts}")
    print(f"sql: {r.sql}")
    print(f"rows: {r.rows[:5]}")
    if r.error:
        print(f"error: {r.error}")
