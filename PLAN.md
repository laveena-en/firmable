# Implementation Plan — AI-Native Data Quality System for News Events

> Status: **scaffold + plan**. Repo structure and stubs are in place; this document is the
> build order. Designed against the real Anthropic API (model tiering Haiku/Sonnet/Opus).

## 0. The dataset (verified from `Datasets/`)

- 24 `.jsonl` files, ~620k events total, ~25k events/file, 2.3 GB.
- Each line is a JSON:API envelope: `data[]` (news events) + `included[]` (companies, news_articles).
- Event `attributes`: `summary`, `category` (event type), `found_at`, `confidence` (0–1, mean ~0.60),
  `article_sentence` (evidence span), `human_approved` (only **1.7%** true), sparse typed slots
  (`amount`, `location_data`, `product_data`, `job_title`, …).
- `relationships`: `company1` (~98%), `company2` (~36%), `most_relevant_source` → article.
- Observed issues: duplicate event IDs, ~295 exact-dup summaries/file, stale events back to 2010,
  confidence/human_approved as ready triage levers.

## 1. Rule vs. LLM split (decision)

| Concern | Tool | Why |
|---|---|---|
| Schema/type validity, null required fields, `confidence∈[0,1]`, `found_at` parseable/not-future | **Rule** | Deterministic, cheap, every record |
| Duplicate events (ID; `(company1, category, norm-summary)`) | **Rule** | Exact/near-exact comparison |
| Broken references (company/article ID resolves in `included`) | **Rule** | Set membership |
| Staleness (`found_at` older than N months) | **Rule** | Date math |
| **Semantic accuracy** (sentence ↔ category) | **LLM** | Requires reading comprehension |
| **Entity resolution** (is `company1` the subject?) | **LLM** | Contextual judgement |
| **Source credibility** (real event vs marketing/syndicated) | **LLM** | Nuanced classification |
| Geographic/market validity vs `location_data` | **LLM** | Contextual |

Principle: rules triage the bulk; LLMs touch only the uncertain slice (low confidence,
not human_approved, rule-ambiguous). At 620k records this is a cost necessity, not just hygiene.

## 2. LLM checks (3 judges)

Each judge = versioned prompt + rubric + structured output `{verdict, reason, confidence}` + eval set ≥30.

1. `semantic_accuracy` — inputs: `article_sentence`, `category`, `summary`. Model: **Haiku 4.5** (high volume binary).
2. `entity_resolution` — inputs: `summary`, company `name`/`domain`, `company2` if present. Model: **Sonnet 4.6**.
3. `source_credibility` — inputs: article `title`/`body`/`url`. Model: **Sonnet 4.6**, escalate hard → **Opus 4.8**.

Eval method: stratified sample across categories + confidence bands so the tail is covered.
Report precision/recall/accuracy per judge; document weaknesses.

## 3. Skills
- `skills/news-events-quality-check/SKILL.md` — trigger, inputs (record/batch), outputs (verdicts),
  prompt/eval dependencies, interpretation, worked example.
- `skills/news-events-remediation/SKILL.md` (bonus) — propose corrected value / merge / rejection + reasoning.

## 4. Agentic pipeline (`src/pipeline/run.py`)
ingest → rule triage → escalate ambiguous to LLM judges → diagnose & propose remediation →
log every call (input, prompt version, model, output, latency, cost, decision) → emit human-review queue.

## 5. Evals & observability
- `src/evals/harness.py` — one command: re-run judges vs labelled set, report P/R + drift vs prev prompt version.
- Prompt versioning: file-based `prompts/<check>/vN.md`, hash recorded in every trace.
- Tracing: `traces/*.jsonl` (or SQLite) with fixed schema (see `src/llm/client.py`).
- Failure analysis: 5–10 worst misses written up.

## 6. Monitoring (`src/monitoring/monitor.py`)
Every-record rules; sampled LLM checks; scheduled full sweeps. Pin model versions (no `-latest` in prod);
golden-set canary detects regression/drift. Cost ceiling = tokens × volume × frequency; sampling is the lever.
Alerting surface: dashboard for trends, ticket for systematic regressions, Slack for threshold breaches.

## 7. Storage & dashboard
- `src/storage/schema.sql` — cleaned records, per-record verdicts (rule + LLM side-by-side), aggregated metrics.
- `src/dashboard/app.py` (Streamlit) — DQ trend by check type, top LLM failure reasons, LLM cost/latency, review backlog.

## 8. Reflection — `REFLECTION.md` (weighted heavily).

## Build order
1. `src/eda/profile.py` (formalize EDA) → 2. `src/rules/checks.py` → 3. `src/llm/client.py` (Anthropic + tracing + cost)
→ 4. prompts v1 + `src/llm/judges.py` → 5. label eval sets (≥30 each) → 6. `src/evals/harness.py`
→ 7. `src/pipeline/run.py` → 8. skills → 9. storage + dashboard → 10. monitoring → 11. README + reflection.
