# Firmable — AI-Native Data Quality System for News Events

An LLM-driven data-quality system for the "news events" feed: rules first, LLM judges for the
semantic tail, packaged as reusable skills, wired into an agentic remediation pipeline with
evals, tracing, monitoring, and a stakeholder dashboard.

> **Status: system working end-to-end.** Rules + 3 LLM judges (measured against hand-labelled
> eval sets) + agentic pipeline → SQLite + monitoring (cost math, canary) + Streamlit dashboard all
> run against real data. Remaining: Part 8 reflection. See `PLAN.md` for the full build order.
>
> **Measured judge quality** (real Haiku/Sonnet calls):
> | Judge | n | Acc | Precision | Recall | F1 |
> |---|---|---|---|---|---|
> | semantic_accuracy v2 | 52 | 0.942 | 1.00 | 0.786 | 0.880 |
> | entity_resolution v1 | 30 | 1.00 | 1.00 | 1.00 | 1.00* |
> | source_credibility v1 | 30 | 0.967 | 1.00 | 0.917 | 0.957 |
>
> *synthetic negatives are easy — see `evals/entity_resolution/FAILURE_ANALYSIS.md`.

## Repo layout
```
PLAN.md                  build order + rule-vs-LLM split + verified EDA numbers
prompts/<check>/vN.md     versioned judge prompts (semantic_accuracy, entity_resolution, source_credibility)
skills/                   SKILL.md specs: news-events-quality-check, news-events-remediation
evals/<check>/            labelled.jsonl ground-truth sets (>=30 each) + results_<version>.json
src/eda/profile.py        Part 1 baseline profiling
src/rules/checks.py       Part 1 deterministic checks (every record)
src/llm/client.py         Anthropic wrapper: model tiering, trace schema, cost
src/llm/judges.py         Part 2 LLM judges
src/pipeline/run.py       Part 4 agentic remediation pipeline
src/evals/harness.py      Part 5 one-command eval (P/R + drift)
src/monitoring/monitor.py Part 6 LLM-aware monitoring + cost math
src/storage/schema.sql    Part 7 DDL (cleaned records, rule+LLM verdicts, metrics, review queue)
src/dashboard/app.py      Part 7 Streamlit dashboard
traces/                   JSONL LLM call traces
```

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY
```

## Run (once implemented)
```bash
python -m src.eda.profile --glob 'Datasets/*.jsonl'
python -m src.pipeline.run --file Datasets/news_events_2025_07_07.00000.jsonl --limit 60
python -m src.evals.harness --check semantic_accuracy --version v2 --compare v1
python -m src.monitoring.monitor --plan --cost            # tiering + cost projection
python -m src.monitoring.monitor --canary semantic_accuracy:v2   # regression check vs baseline
streamlit run src/dashboard/app.py -- --db data/dq.db     # dashboard
```

Add `MOCK_LLM=1` before any command to run offline with a heuristic stand-in (no API key needed).

## Model tiering
Haiku 4.5 (high-volume binary) · Sonnet 4.6 (nuanced judgement) · Opus 4.8 (hard escalation).
Versions are pinned — see `src/llm/client.py`.
