---
name: news-events-quality-check
version: 1.0.0
description: Run the layered (rule + LLM) quality checks on one or more news-event records and return structured verdicts.
---

# news-events-quality-check

## When to trigger
Invoke when validating incoming or stored **news_event** records — on ingest, before
promotion to the clean table, or when auditing a batch for a quality report.

## Required inputs
- `records`: one event or a JSON:API batch (`data[]` + `included[]`), so company/article
  context is resolvable.
- Optional `checks`: subset of `[rules, semantic_accuracy, entity_resolution, source_credibility]`
  (default: all).

## What it does
1. Runs deterministic **rules** first (schema, nulls, confidence range, date sanity, broken refs,
   dedup, staleness) — see `src/rules/checks.py`.
2. Escalates rule-clean-but-uncertain records (low confidence or `human_approved=false`) to the
   **LLM judges** — see `src/llm/judges.py` and `prompts/<check>/v1.md`.
3. Traces every LLM call (model, prompt version, cost, latency, decision) to `traces/`.

## Dependencies
- Prompts: `prompts/semantic_accuracy/v1.md`, `prompts/entity_resolution/v1.md`, `prompts/source_credibility/v1.md`
- Evals: `evals/<check>/labelled.jsonl` (validates judge quality before trusting output)

## Output
```json
{
  "record_id": "0020f127-...",
  "rule_results": [{"check": "date_sane", "passed": true, "reason": ""}],
  "llm_results":  {"semantic_accuracy": {"verdict": "fail", "reason": "...", "confidence": 0.82}},
  "decision": "pass | fail | needs_human_review",
  "cost_usd": 0.0007,
  "latency_ms": 540
}
```

## Interpreting the result
- `decision=fail` with high judge confidence → route to remediation skill.
- `decision=needs_human_review` → low-confidence or conflicting verdicts → human queue.
- `decision=pass` → eligible for the clean table.

## Worked example
**Input** (abridged): event `category=hires`, `article_sentence="X is hiring for several roles"`.
**Output**: `semantic_accuracy.verdict=fail` (job posting, not a hire event), `decision=fail`.
