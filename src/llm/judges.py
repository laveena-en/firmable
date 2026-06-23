"""LLM judges (Part 2). Each loads a versioned prompt as the system rubric, renders the
record into the user message, calls a tiered model, and returns
{verdict: pass|fail, reason: str, confidence: float}.
"""
from __future__ import annotations
from pathlib import Path

from . import client

PROMPTS = Path(__file__).resolve().parents[2] / "prompts"


def _load_prompt(check: str, version: str) -> str:
    return (PROMPTS / check / f"{version}.md").read_text()


def semantic_accuracy(event: dict, version: str = "v1") -> dict:
    """Does article_sentence support the labelled category? Tier: cheap (Haiku)."""
    a = event.get("attributes", {})
    system = _load_prompt("semantic_accuracy", version)
    user = (
        f"category: {a.get('category')}\n"
        f"summary: {a.get('summary')}\n"
        f"article_sentence: {a.get('article_sentence')}"
    )
    return client.call_judge(
        check="semantic_accuracy", tier="cheap", system=system, user=user,
        version=version, record_id=event.get("id", "unknown"),
    )


def entity_resolution(event: dict, company: dict, company2: dict | None = None,
                      version: str = "v1") -> dict:
    """Is company1 plausibly the real-world subject of the event? Tier: judge (Sonnet)."""
    a = event.get("attributes", {})
    ca = company.get("attributes", {})
    c2name = (company2 or {}).get("attributes", {}).get("company_name", "")
    system = _load_prompt("entity_resolution", version)
    user = (
        f"summary: {a.get('summary')}\n"
        f"category: {a.get('category')}\n"
        f"article_sentence: {a.get('article_sentence')}\n"
        f"company1_name: {ca.get('company_name')}\n"
        f"company1_domain: {ca.get('domain')}\n"
        f"company2_name: {c2name}"
    )
    return client.call_judge(
        check="entity_resolution", tier="judge", system=system, user=user,
        version=version, record_id=event.get("id", "unknown"),
    )


def source_credibility(article: dict, version: str = "v1") -> dict:
    """Real news event vs marketing/syndicated/dup? Tier: judge (Sonnet)."""
    at = article.get("attributes", {})
    body = (at.get("body") or "")[:3000]
    system = _load_prompt("source_credibility", version)
    user = f"title: {at.get('title')}\nurl: {at.get('url')}\nbody: {body}"
    return client.call_judge(
        check="source_credibility", tier="judge", system=system, user=user,
        version=version, record_id=article.get("id", "unknown"),
    )
