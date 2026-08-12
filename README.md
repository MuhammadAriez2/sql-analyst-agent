# SQL Analyst Agent

An agent that turns plain-English questions into SQLite queries, runs them against a real database, and retries on its own errors. A Streamlit UI shows the full generate, validate, execute, retry loop, not just the final answer.

## Quickstart

```bash
git clone <repo-url>
cd sql-analyst-agent
pip install -r requirements.txt
```

Create a `.env` file with your Anthropic API key:

```
ANTHROPIC_API_KEY=your_key_here
```

Then run the app:

```bash
streamlit run app.py
```

The Chinook database (`data/chinook.db`) is committed to the repo, so there is no database setup step. The app runs immediately after cloning.

To rebuild and run the evaluation:

```bash
python build_eval.py
python run_eval.py
```

## How it works

1. The question, the live database schema, and a short system prompt with SQL rules are sent to Claude.
2. Claude returns a SQL query.
3. The query is validated, then executed on a read-only connection.
4. If validation blocks it (not a single SELECT/WITH statement, or it contains a forbidden keyword like `DROP` or `INSERT`), the loop stops right there. That's treated as a refusal, not something to retry.
5. If it passes validation but fails at execution with a real SQLite error, the failed query and the exact error message are added to the conversation, and Claude is asked to fix it. This can happen up to 2 more times, for 3 attempts total.
6. Once a query executes cleanly, the loop returns the columns, rows, and the full attempt history, including any earlier failures.

## Project structure

```
.
├── app.py               Streamlit UI: runs the agent, shows the attempt trail, result table, and chart
├── build_eval.py        Writes eval/questions.jsonl (20 gold question/SQL pairs) and verifies every gold query runs
├── run_eval.py          Evaluation harness: runs each question through the agent, compares to gold, writes eval/results.jsonl
├── check_schema.py      Small script that prints the raw schema for a quick look
├── requirements.txt
├── .env.example         Template for ANTHROPIC_API_KEY
├── data/
│   └── chinook.db       The Chinook sample database, committed to the repo
├── eval/
│   ├── questions.jsonl  The 20 eval questions with gold SQL
│   └── results.jsonl    Latest eval run's per-question results (gitignored)
└── src/
    ├── agent.py         The agent loop: generate SQL, validate, execute, retry on error
    ├── validator.py     Query validation and safe, read-only execution
    └── schema.py        Reads the live schema from sqlite_master for the prompt
```

## Evaluation methodology

The metric is execution accuracy. The gold query and the generated query are both run against the database and their result sets are compared. This isn't string matching, since there are many correct ways to write the same query and a string comparison would mark correct SQL as wrong.

Comparison rules, from `run_eval.py`:

- Ordered comparison when the gold query has an `ORDER BY`, unordered otherwise.
- Floats are rounded to 2 decimal places.
- Column names are ignored, only values are compared.

The set has 20 questions across three tiers: tier 1 is single-table queries (10 questions), tier 2 is joins (5), tier 3 is subqueries, window functions, self-joins, and date handling (5).

The eval set was written before the agent was built, so the questions were not shaped around what the agent could already do.

## Results

Final run: 20/20 execution accuracy, 19/20 correct on the first attempt, for a retry lift of +5.0%. By tier: 10/10, 5/5, 5/5.

This is a single run of a 20-question set. LLM output varies between runs, so this number carries real variance and should be read as a snapshot, not a guarantee.

## Case study: per-group top-N

Question 18 asks: "For each genre, which single track earned the most revenue?" The correct answer has 24 rows, one per genre with any sales.

The agent's first attempt grouped correctly by genre and track, then added `LIMIT 1`. That returns one row for the whole result set, not one row per genre, so it collapsed 24 genres down to a single track. `LIMIT` applies to the whole result set, not to each group.

Rather than treat one failure as conclusive, the same question was run five times total. It was correct 3 out of 5, always taking 2 to 3 attempts. So the failure mode was unreliability, not a hard capability gap.

One rule was added to the system prompt: for "top N per group" questions, use `ROW_NUMBER() OVER (PARTITION BY ...)` in a subquery and filter on the row number, because `LIMIT` applies to the whole result set, not each group. Re-running the same question four more times gave 4 out of 4 correct, two of them on the first attempt. Both accuracy and attempt count improved.

Two caveats on that:

- The rule was written after watching this exact question fail, and the 20/20 headline number above was then measured on a set that includes that question. That's optimizing against the test set, so 20/20 is optimistic rather than an unbiased estimate. A cleaner setup would hold out a second per-group question, written before the fix and never inspected, to check the rule actually generalizes.
- n=4 on each side of the fix. Enough to see a signal, not enough to size it precisely.

A separate finding from an earlier run matters more than any headline number. That run scored 17/20. On manual review, three of the five failures were actually correct answers in the wrong output shape: extra columns, a first and last name concatenated into one field, or months formatted as "01" instead of "2023-01". Only one of the five was a genuine SQL error. Reporting the raw score without reading the failures would have understated the agent and misdiagnosed the problem as a SQL capability gap, when it was really a question-wording gap. The fix was to make the eval questions specify the expected output shape explicitly.

## Design decisions

- **Max 2 retries, 3 attempts total.** Attempt 2 fixes most syntax and column-name errors. By attempt 3 the model has usually misunderstood the question rather than the syntax, so another error message doesn't help.
- **Full conversation history is replayed on retry**, including the model's own failed query, not just the error text. Sending only the error loses the context of what was tried, and the model often regenerates the same broken query.
- **Validation failures are not retried.** A blocked query means the model tried to write data or produced a malformed statement, which is a refusal, not a correctable mistake.
- **Three-layer safety.** Static checks reject anything that isn't a single SELECT (or WITH) statement. A read-only SQLite connection (`mode=ro`) makes writes impossible at the driver level, and this is the layer that actually guarantees nothing is written, since string checks alone can be fooled. Row and time caps stop a valid but runaway query from hanging the app.
- **The UI shows the loop, not just the answer.** It displays the generated SQL, the attempt count, and any failed attempts with the errors that triggered a rewrite. A UI that only shows the final table looks like a database browser and hides what the agent actually did.

## Limitations

- **Scoped to the Chinook database.** The schema is read at startup, so questions about tables that don't exist will produce wrong or failing SQL.
- **Read only.** No inserts, updates, or deletes.
- **No ambiguity detection.** Asked which playlist has the most tracks, the agent returns one row, but Chinook has two distinct playlists both named "Music" with 3,290 tracks each. The answer is correct and incomplete, and the agent doesn't flag the tie.
- **No statistical caveats.** Asked which country has the highest average invoice, it returns Chile at 6.66 without noting that this is an average over 7 invoices.
- **Single turn.** No follow-up questions or conversation memory.
- **20 questions is a small eval set.** It found one genuine capability gap; a larger set would likely find more.
