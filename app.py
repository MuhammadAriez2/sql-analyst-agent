"""Streamlit UI for the SQL agent.

Surfaces the agent LOOP, not just the final answer: every failed attempt is
shown with the query that failed and the database error that caused the
model to rewrite it, so a viewer can see retry lift happening rather than
just trusting the final number.

Run:  streamlit run app.py
"""

import os

import anthropic
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.agent import ask
from src.schema import get_schema

load_dotenv()

st.set_page_config(page_title="SQL Analyst Agent", page_icon="🗃️", layout="wide")


@st.cache_data
def _schema() -> str:
    return get_schema()


@st.cache_resource
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


st.title("SQL Analyst Agent")
st.caption("Ask a question about the Chinook database.")

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error("ANTHROPIC_API_KEY is not set. Add it to .env and restart the app.")
    st.stop()

with st.form("ask_form"):
    question = st.text_input(
        "Question",
        placeholder="Which five artists brought in the most revenue?",
    )
    submitted = st.form_submit_button("Run")

if submitted and not question.strip():
    st.warning("Type a question first.")

elif submitted:
    with st.spinner("Generating and running SQL..."):
        result = ask(question, schema=_schema(), client=_client())

    attempts = result.attempts
    st.caption(f"Attempts: {len(attempts)}")

    # Every attempt that failed - shown with the query and the error that
    # caused it, in order, so the rewrite trail is visible.
    for i, (sql, err) in enumerate(attempts):
        if err is None:
            continue
        is_last = i == len(attempts) - 1
        if err.startswith("BLOCKED:"):
            title = "Blocked by validator — refused, no retry"
        elif is_last and not result.ok:
            title = f"Attempt {i + 1} failed — out of retries"
        else:
            title = f"Attempt {i + 1} failed — rewritten after this error"
        with st.expander(title, expanded=True):
            st.code(sql, language="sql")
            st.error(err)

    if result.ok:
        st.subheader("Generated SQL")
        st.code(result.sql, language="sql")

        df = pd.DataFrame(result.rows, columns=result.columns)

        st.subheader(f"Result ({len(df)} row{'s' if len(df) != 1 else ''})")
        st.dataframe(df, width="stretch")

        if len(df) > 0 and len(df.columns) == 2:
            c1, c2 = df.columns
            numeric1 = pd.api.types.is_numeric_dtype(df[c1])
            numeric2 = pd.api.types.is_numeric_dtype(df[c2])
            if numeric1 != numeric2:  # exactly one label column, one numeric
                label_col, value_col = (c2, c1) if numeric1 else (c1, c2)
                st.subheader("Chart")
                st.bar_chart(df.set_index(label_col)[value_col])
    else:
        st.error(result.error)
