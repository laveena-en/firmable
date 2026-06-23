"""SQLite storage helper — init schema, write verdicts/clean records/review queue (Part 7)."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA.read_text())
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_rule_verdict(conn, event_id, found_at, check_name, verdict, reason) -> None:
    conn.execute(
        "INSERT INTO quality_verdicts (event_id, found_at, check_kind, check_name, verdict, reason, "
        "created_at) VALUES (?,?,?,?,?,?,?)",
        (event_id, found_at, "rule", check_name, verdict, reason, _now()))


def insert_llm_verdict(conn, event_id, found_at, check_name, v: dict) -> None:
    conn.execute(
        "INSERT INTO quality_verdicts (event_id, found_at, check_kind, check_name, verdict, reason, "
        "confidence, model, prompt_version, cost_usd, latency_ms, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (event_id, found_at, "llm", check_name, v.get("verdict"), v.get("reason"), v.get("confidence"),
         v.get("_model"), v.get("_prompt_version"), v.get("_cost_usd", 0), v.get("_latency_ms", 0),
         _now()))


def upsert_clean_event(conn, ev: dict) -> None:
    a = ev.get("attributes", {})
    rels = ev.get("relationships", {})
    def rid(k):
        return (rels.get(k, {}).get("data") or {}).get("id")
    conn.execute(
        "INSERT OR REPLACE INTO clean_events (event_id, category, summary, found_at, confidence, "
        "human_approved, company1_id, company2_id, source_id, promoted_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (ev.get("id"), a.get("category"), a.get("summary"), a.get("found_at"), a.get("confidence"),
         1 if a.get("human_approved") else 0, rid("company1"), rid("company2"),
         rid("most_relevant_source"), _now()))


def enqueue_review(conn, event_id, reason, proposed_action) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO review_queue (event_id, reason, proposed_action, status, enqueued_at) "
        "VALUES (?,?,?,?,?)",
        (event_id, reason, proposed_action, "pending", _now()))
