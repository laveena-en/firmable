"""Part 7: stakeholder dashboard (Streamlit).

Run:  streamlit run src/dashboard/app.py -- --db data/dq.db

Panels:
  1. DQ fail-rate trend by check type (rule vs LLM)
  2. Top failing reasons surfaced by LLM judges
  3. Cost & latency of LLM checks
  4. Backlog of records awaiting human review
"""
from __future__ import annotations
import sys

import altair as alt
import streamlit as st

from src.dashboard import queries

# crude arg parse so `-- --db path` works under `streamlit run`
DB = "data/dq.db"
if "--db" in sys.argv:
    DB = sys.argv[sys.argv.index("--db") + 1]

st.set_page_config(page_title="News-Events Data Quality", layout="wide")
st.title("News-Events Data Quality")
st.caption(f"Rule-based and LLM-based verdicts, side by side · source: {DB}")

s = queries.summary(DB)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Clean events", s["clean_events"])
c2.metric("Total verdicts", s["verdicts"])
c3.metric("Review backlog", s["review_backlog"])
c4.metric("LLM spend (run)", f"${s['llm_cost_usd']:.4f}", f"{s['llm_calls']} calls")

st.subheader("1 · DQ fail-rate over time — rule vs LLM")
trend = queries.dq_trend_by_kind(DB)
if trend.empty:
    st.info("No dated verdicts yet.")
else:
    chart = (alt.Chart(trend).mark_line(point=True)
             .encode(x="month:O", y=alt.Y("fail_rate:Q", title="fail rate"),
                     color="check_kind:N", tooltip=["month", "check_kind", "n", "n_fail", "fail_rate"]))
    st.altair_chart(chart, use_container_width=True)

left, right = st.columns(2)
with left:
    st.subheader("2 · Top LLM failure reasons")
    reasons = queries.top_llm_fail_reasons(DB)
    st.dataframe(reasons, use_container_width=True, hide_index=True)
with right:
    st.subheader("3 · LLM cost & latency by check")
    st.dataframe(queries.cost_latency_by_check(DB), use_container_width=True, hide_index=True)

st.subheader("4 · Human-review backlog")
st.dataframe(queries.review_backlog(DB), use_container_width=True, hide_index=True)
