"""Dashboard data layer — pure SQL functions over data/dq.db (Part 7).

Kept separate from the Streamlit view so it can be tested headless.
"""
from __future__ import annotations
import sqlite3
import pandas as pd


def _conn(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def summary(db_path: str) -> dict:
    c = _conn(db_path)
    g = lambda q: c.execute(q).fetchone()[0]
    return {
        "clean_events": g("SELECT COUNT(*) FROM clean_events"),
        "verdicts": g("SELECT COUNT(*) FROM quality_verdicts"),
        "review_backlog": g("SELECT COUNT(*) FROM review_queue WHERE status='pending'"),
        "llm_cost_usd": round(g("SELECT COALESCE(SUM(cost_usd),0) FROM quality_verdicts") or 0, 4),
        "llm_calls": g("SELECT COUNT(*) FROM quality_verdicts WHERE check_kind='llm'"),
    }


def dq_trend_by_kind(db_path: str) -> pd.DataFrame:
    """Fail-rate by check kind (rule vs LLM), bucketed by the event's found_at month.

    Reads found_at straight off quality_verdicts so FAILED records (never promoted to
    clean_events) are still counted — otherwise the trend would only ever show passes.
    """
    q = """
      SELECT substr(found_at,1,7) AS month,
             check_kind,
             COUNT(*) AS n,
             SUM(CASE WHEN verdict='fail' THEN 1 ELSE 0 END) AS n_fail
      FROM quality_verdicts
      WHERE found_at IS NOT NULL
      GROUP BY month, check_kind
      ORDER BY month
    """
    df = pd.read_sql_query(q, _conn(db_path))
    if not df.empty:
        df["fail_rate"] = df["n_fail"] / df["n"]
    return df


def top_llm_fail_reasons(db_path: str, limit: int = 10) -> pd.DataFrame:
    q = """
      SELECT check_name, reason, COUNT(*) AS n
      FROM quality_verdicts
      WHERE check_kind='llm' AND verdict='fail'
      GROUP BY check_name, reason
      ORDER BY n DESC
      LIMIT ?
    """
    return pd.read_sql_query(q, _conn(db_path), params=(limit,))


def cost_latency_by_check(db_path: str) -> pd.DataFrame:
    q = """
      SELECT check_name, model,
             COUNT(*) AS calls,
             ROUND(SUM(cost_usd),4) AS total_cost_usd,
             ROUND(AVG(cost_usd),6) AS avg_cost_usd,
             ROUND(AVG(latency_ms)) AS avg_latency_ms
      FROM quality_verdicts
      WHERE check_kind='llm'
      GROUP BY check_name, model
      ORDER BY total_cost_usd DESC
    """
    return pd.read_sql_query(q, _conn(db_path))


def review_backlog(db_path: str) -> pd.DataFrame:
    q = """
      SELECT event_id, proposed_action, reason, status, enqueued_at
      FROM review_queue
      WHERE status='pending'
      ORDER BY enqueued_at DESC
    """
    return pd.read_sql_query(q, _conn(db_path))
