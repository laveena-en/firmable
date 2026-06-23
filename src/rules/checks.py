"""Deterministic rule-based checks — run on EVERY record, cheap, no LLM (Part 1)."""
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import datetime, timezone

REQUIRED = ("summary", "category", "found_at", "confidence")


@dataclass
class RuleResult:
    check: str
    passed: bool
    reason: str = ""


def required_fields(attrs: dict) -> RuleResult:
    missing = [k for k in REQUIRED if attrs.get(k) in (None, "")]
    return RuleResult("required_fields", not missing,
                      "" if not missing else f"missing: {missing}")


def confidence_range(attrs: dict) -> RuleResult:
    c = attrs.get("confidence")
    ok = isinstance(c, (int, float)) and 0.0 <= c <= 1.0
    return RuleResult("confidence_range", ok, "" if ok else f"confidence out of range: {c}")


def _parse_dt(s):
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def date_sane(attrs: dict) -> RuleResult:
    dt = _parse_dt(attrs.get("found_at"))
    if dt is None:
        return RuleResult("date_sane", False, f"unparseable found_at: {attrs.get('found_at')}")
    if dt > datetime.now(timezone.utc):
        return RuleResult("date_sane", False, f"future found_at: {attrs.get('found_at')}")
    return RuleResult("date_sane", True)


def references_resolve(event: dict, included_ids: set[str]) -> RuleResult:
    rels = event.get("relationships", {})
    bad = []
    for key in ("company1", "most_relevant_source"):
        ref = rels.get(key, {}).get("data") or {}
        rid = ref.get("id")
        if rid and rid not in included_ids:
            bad.append(f"{key}:{rid}")
    return RuleResult("references_resolve", not bad,
                      "" if not bad else f"unresolved refs: {bad}")


def staleness(attrs: dict, max_age_months: int = 18) -> RuleResult:
    dt = _parse_dt(attrs.get("found_at"))
    if dt is None:
        return RuleResult("staleness", True)  # date_sane owns the failure
    age_days = (datetime.now(timezone.utc) - dt).days
    stale = age_days > max_age_months * 30
    return RuleResult("staleness", not stale,
                      "" if not stale else f"stale: {age_days}d old")


_WS = re.compile(r"\s+")


def dedup_key(event: dict) -> str:
    a = event.get("attributes", {})
    c1 = (event.get("relationships", {}).get("company1", {}).get("data") or {}).get("id", "")
    summary = _WS.sub(" ", (a.get("summary") or "").lower().strip())
    return f"{c1}|{a.get('category')}|{summary}"


def triage(event: dict, included_ids: set[str], seen_keys: set[str] | None = None) -> dict:
    """Run all rules. Returns hard_fail / needs_llm / results.

    - hard_fail: a structural rule failed (schema, refs, bad date, duplicate) -> quarantine, skip LLM.
    - needs_llm: rule-clean but uncertain (low confidence OR not human_approved) -> escalate to judges.
    """
    a = event.get("attributes", {})
    results = [
        required_fields(a),
        confidence_range(a),
        date_sane(a),
        references_resolve(event, included_ids),
        staleness(a),
    ]

    is_dup = False
    if seen_keys is not None:
        k = dedup_key(event)
        is_dup = k in seen_keys
        seen_keys.add(k)
        results.append(RuleResult("duplicate", not is_dup, "duplicate event" if is_dup else ""))

    structural = {"required_fields", "confidence_range", "date_sane", "references_resolve", "duplicate"}
    hard_fail = any(not r.passed and r.check in structural for r in results)

    conf = a.get("confidence") or 0.0
    approved = bool(a.get("human_approved"))
    needs_llm = (not hard_fail) and ((not approved) or conf < 0.7)

    return {"hard_fail": hard_fail, "needs_llm": needs_llm, "results": results}
