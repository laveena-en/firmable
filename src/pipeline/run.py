"""Agentic remediation pipeline (Part 4).

ingest → rule triage → escalate ambiguous to LLM judges → diagnose & propose remediation
→ trace every LLM step (handled in src/llm/client) → persist verdicts → emit human-review queue.

Run:  python -m src.pipeline.run --file Datasets/news_events_2025_07_07.00000.jsonl --limit 50
      MOCK_LLM=1 python -m src.pipeline.run --file ... --limit 50   # offline

Where humans / rules / LLMs belong:
  - rules     -> structural gate on every record (free). hard_fail = quarantine, never reaches LLM.
  - LLMs      -> only ambiguous records (low confidence or not human_approved) get the 3 judges.
  - humans    -> any LLM fail, judge error, or low-confidence verdict lands in review_queue.
"""
from __future__ import annotations
import argparse
import json

from src.rules import checks
from src.llm import judges
from src.storage import db

# Prompt versions in production use (Part 5 prompt versioning).
VERSIONS = {"semantic_accuracy": "v2", "entity_resolution": "v2", "source_credibility": "v1"}
LOW_CONF = 0.6  # judge confidence below this → send to humans even if it "passed"


def _lookup(included: list[dict]) -> dict:
    return {inc["id"]: inc for inc in included}


def _ref(ev, key, lut):
    rid = (ev.get("relationships", {}).get(key, {}).get("data") or {}).get("id")
    return lut.get(rid)


def diagnose(event, rule_results, llm_verdicts) -> tuple[str, str, str]:
    """Decide overall decision + propose a remediation action. Returns (decision, action, reason)."""
    failed_rules = [r.check for r in rule_results if not r.passed]

    if "duplicate" in failed_rules:
        return "fail", "merge", "duplicate of an existing event (rule)"
    structural = {"required_fields", "confidence_range", "date_sane", "references_resolve"}
    if any(c in structural for c in failed_rules):
        return "fail", "reject", f"failed structural rules: {failed_rules}"

    # source credibility failure → the event isn't real/relevant → reject
    sc = llm_verdicts.get("source_credibility", {})
    if sc.get("verdict") == "fail":
        return "fail", "reject", f"source_credibility: {sc.get('reason')}"

    sem = llm_verdicts.get("semantic_accuracy", {})
    ent = llm_verdicts.get("entity_resolution", {})
    if sem.get("verdict") == "fail":
        return "fail", "correct", f"semantic_accuracy: {sem.get('reason')}"
    if ent.get("verdict") == "fail":
        return "fail", "correct", f"entity_resolution: {ent.get('reason')}"

    if any(v.get("verdict") == "error" for v in llm_verdicts.values()):
        return "needs_human_review", "review", "an LLM check errored"
    if any((v.get("confidence") or 1) < LOW_CONF for v in llm_verdicts.values()):
        return "needs_human_review", "review", "low judge confidence"
    return "pass", "promote", "all checks passed"


def run(path: str, limit: int | None = None, db_path: str = "data/dq.db") -> None:
    conn = db.connect(db_path)
    seen_keys: set[str] = set()
    n = passed = failed = review = escalated = 0
    cost = 0.0

    with open(path) as f:
        for line in f:
            if limit is not None and n >= limit:
                break
            envelope = json.loads(line)
            lut = _lookup(envelope.get("included", []))
            included_ids = set(lut)

            for ev in envelope.get("data", []):
                if limit is not None and n >= limit:
                    break
                n += 1
                found_at = ev.get("attributes", {}).get("found_at")
                t = checks.triage(ev, included_ids, seen_keys)
                for r in t["results"]:
                    db.insert_rule_verdict(conn, ev["id"], found_at, r.check,
                                           "pass" if r.passed else "fail", r.reason)

                llm_verdicts: dict = {}
                if not t["hard_fail"] and t["needs_llm"]:
                    escalated += 1
                    company1 = _ref(ev, "company1", lut)
                    company2 = _ref(ev, "company2", lut)
                    article = _ref(ev, "most_relevant_source", lut)

                    sem = judges.semantic_accuracy(ev, VERSIONS["semantic_accuracy"])
                    llm_verdicts["semantic_accuracy"] = sem
                    if company1:
                        ent = judges.entity_resolution(ev, company1, company2,
                                                       VERSIONS["entity_resolution"])
                        llm_verdicts["entity_resolution"] = ent
                    if article:
                        sc = judges.source_credibility(article, VERSIONS["source_credibility"])
                        llm_verdicts["source_credibility"] = sc

                    for name, v in llm_verdicts.items():
                        db.insert_llm_verdict(conn, ev["id"], found_at, name, v)
                        cost += v.get("_cost_usd", 0)

                decision, action, reason = diagnose(ev, t["results"], llm_verdicts)
                if decision == "pass":
                    passed += 1
                    db.upsert_clean_event(conn, ev)
                elif decision == "fail":
                    failed += 1
                    db.enqueue_review(conn, ev["id"], reason, action)
                else:
                    review += 1
                    db.enqueue_review(conn, ev["id"], reason, action)

            conn.commit()

    conn.commit()
    conn.close()
    print(f"processed={n}  passed={passed}  failed={failed}  needs_review={review}  "
          f"escalated_to_llm={escalated}  llm_cost=${cost:.4f}")
    print(f"db: {db_path}  (clean_events, quality_verdicts, review_queue)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--db", default="data/dq.db")
    args = ap.parse_args()
    run(args.file, args.limit, args.db)
