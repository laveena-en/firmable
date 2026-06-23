---
name: news-events-remediation
version: 1.0.0
description: Propose a fix for a flagged news-event record — corrected value, suggested merge, or rejection — with reasoning.
---

# news-events-remediation

## When to trigger
After `news-events-quality-check` returns `decision=fail`. This skill **proposes** a fix;
it does not auto-apply. A human or downstream policy approves.

## Required inputs
- `record`: the flagged event (+ included company/article context).
- `verdicts`: the failing rule/LLM results that triggered remediation.

## What it does (tier: judge → hard for ambiguous)
Diagnoses the failure and proposes exactly one action:
- **correct** — e.g. wrong `category`; propose the correct label + evidence span.
- **merge** — duplicate of an existing event; propose the canonical `record_id`.
- **reject** — marketing/noise/unsupported; propose quarantine with reason.

## Output
```json
{
  "record_id": "...",
  "action": "correct | merge | reject",
  "proposal": {"field": "category", "from": "hires", "to": "is_developing"},
  "reasoning": "<why, citing the article_sentence>",
  "confidence": 0.0-1.0,
  "auto_applicable": false
}
```

## Interpreting the result
- High-confidence `correct` on a single field → safe to fast-track in review UI.
- `merge`/`reject` → always human-confirmed (destructive).
