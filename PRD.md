## **Technical Assessment**

### **Who should NOT continue:**

❌ **If you're short on time for an assessment.**

❌ **If you can't read the full page right now.**

❌ **If you're seeking a traditional 9-to-5 role.**

❌ **If you don't believe in leveraging AI tools for productivity.**

❌ **If you've never shipped real work using Claude Code, Cursor, or an equivalent agentic IDE.**

❌ **If you treat LLMs as a wrapper around prompts rather than a system that needs evals, traces, and version control.**

## Overview:

**Building an AI-Native Data Quality System for the "News Events" Dataset**

**Objective:**

Design, implement, and document an **AI-native data quality system** for the provided "news events" dataset. Where the traditional version of this assessment focuses on rule-based profiling and remediation, this version focuses on **LLM-driven checks, reusable skills, agentic remediation pipelines, and the eval/observability scaffolding that makes AI quality work in production.**

**Context:**

At Firmable, AI is not a productivity tool bolted onto traditional analyst work — it *is* the workflow. Every analyst is expected to operate with agentic development, evals, traces, and AI-powered review pipelines as their default mode of working.

This assessment simulates exactly that. You are the data quality champion for a critical incoming feed, and your remit is to make AI do the heavy lifting in a way that's **measurable, reproducible, and trustworthy** in production.

You'll be assessed not only on whether your system finds issues, but on **how you build** — the quality of your prompts, the rigor of your evals, the reusability of your skills, and the clarity of your reasoning about when to use an LLM vs. when not to.

---

### Part 1 — Baseline Profiling (light)

Before reaching for an LLM, demonstrate you understand the data:

- Brief description of the dataset's structure, columns, and business relevance.
- Lightweight EDA: distributions, missingness, format anomalies, candidate keys.
- Identify which quality issues are **better solved by deterministic rules** (e.g. format validation, null checks, duplicates on a clean key) vs. **better solved by LLMs** (e.g. semantic accuracy, contextual validity, entity resolution edge cases). Justify the split.

This part should be deliberately compact. It exists to set up the rest — we want to see that you reach for rules first when rules are the right tool.

---

### Part 2 — LLM-Based Quality Checks

Build at least **three LLM-powered quality checks** that target dimensions where rule-based logic underperforms. Pick any three or propose your own:

- **Semantic accuracy** — does the news event description actually match the labelled event type?
- **Entity resolution validation** — is the linked company/person plausibly correct given the event content?
- **Source credibility & relevance** — is this a real news event, marketing content, syndicated noise, or duplicate coverage?
- **Contextual freshness** — is the event still relevant, or is it a stale historical event being re-surfaced as new?
- **Geographic/market validity** — does the event apply to the claimed market (ANZ/SEA/etc.)?

For each check, deliver:

- The **prompt(s)** with an explicit grading rubric.
- The **expected output schema** (structured JSON: pass/fail, reason, confidence).
- A short note on **model choice and why** (e.g. Haiku for cheap classification, Sonnet for nuanced judgement, frontier model for hard edge cases).
- An **eval set of at least 30 hand-labelled examples per check**, with clear ground truth, and measured precision/recall/accuracy on your prompt.

We care less about hitting a specific accuracy number and more about whether you've *measured* your judge and can defend its weaknesses.

---

### Part 3 — Reusable Skills

At Firmable, recurring AI workflows are packaged as **skills** — markdown specifications that any team member or agent can invoke to perform a defined task with defined inputs and outputs. Think of a skill as a self-contained, versioned capability that lives in a repo and can be loaded by Claude Code, Cursor, or the API.

Build at least **one skill** as part of this submission:

- A `SKILL.md` for `news-events-quality-check` that any agent can load and run.
- The skill must describe: when to trigger it, required inputs, expected outputs, the prompts/evals it depends on, and how to interpret the result.
- Include a worked example invocation and the resulting output.

Bonus points if you also build a `news-events-remediation` skill that **proposes** a fix for a flagged record (and explains its reasoning).

---

### Part 4 — Agentic Remediation Pipeline

Build a small **agentic pipeline** that ties the pieces together. The flow should roughly be:

1. **Ingest** a batch of new records.
2. **Triage** with cheap rule-based checks first.
3. **Escalate** ambiguous records to your LLM checks.
4. **Diagnose & propose remediation** for failures (corrected value, suggested merge, suggested rejection).
5. **Log everything** — input, prompt version, model, output, latency, cost, decision.
6. **Surface a queue** of records that need human review.

This does not need to be a polished production service. A Python script or notebook that demonstrates the loop end-to-end is enough — what we're looking for is whether you've thought through the agentic flow and **where humans, rules, and LLMs each belong**.

---

### Part 5 — Evals & Observability

Production AI quality work lives or dies by what you measure. Show us:

- **Eval harness**: a script that re-runs your LLM checks against your labelled set and reports precision/recall/drift vs. the previous version. Must be runnable with one command.
- **Prompt versioning**: how prompts are tracked over time (file-based, registry, or otherwise) and how you'd compare v1 vs. v2 of a check.
- **Tracing**: log structure for each LLM call (request, response, model, prompt version, cost, latency, decision). A JSONL file or SQLite table is fine — what matters is the schema.
- **Failure analysis**: pull 5–10 of your worst failures from the eval set and write a short note on *why* the LLM got them wrong and what you'd change.

---

### Part 6 — Automated Monitoring (LLM-Aware)

Propose and implement a **continuous monitoring** plan that goes beyond traditional DQ alerts:

- Which checks run on **every record**, which run on **samples**, which run on **schedule**?
- How do you detect **prompt drift** or **model regression** when a vendor updates a model behind a name like `claude-sonnet-latest`?
- What's the **cost ceiling** and how do you stay under it? Show your math on tokens × volume × frequency.
- What's the **alerting surface** — Slack, dashboard, ticket — for which kind of failure?

A short architecture diagram (drawn however you like) plus a working monitoring script is enough.

---

### Part 7 — Storage, Reporting & Stakeholder View

You still need somewhere to store the cleaned data and the quality results, and stakeholders still need a view they can read.

- Minimal SQL schema (DDL) to store cleaned records, per-record quality verdicts, and aggregated metrics — **rule-based and LLM-based, side by side**.
- A lightweight dashboard (BI tool of your choice, or a simple HTML/Streamlit report) showing:
    - DQ trend over time, broken down by check type (rule vs. LLM).
    - Top failing reasons surfaced by LLM judges.
    - Cost and latency of LLM checks over time.
    - Backlog of records awaiting human review.

---

### Part 8 — How You Build (short written reflection)

A 1–2 page write-up answering:

- What was your **dev loop**? Which agentic tools (Claude Code, Cursor, API scripts, etc.) did you use, and how did they change the shape of the work compared to writing this by hand?
- Where did the LLM **save you the most time**, and where did it **cost you more time than rules would have**?
- If you were given two more weeks and a real production budget, **what would you build next** to make this a system the data team relies on daily?
- One thing about this submission you'd flag as a **known weakness** if you were handing it over to a teammate.

We weight this section heavily. It is the clearest signal that someone operates **AI-native rather than AI-assisted**.

---

### Deliverables:

**GitHub Repository:**

- Code: EDA, rule-based checks, LLM checks, agentic pipeline, eval harness, monitoring script.
- `skills/` directory containing your `SKILL.md` file(s).
- `prompts/` directory with versioned prompts.
- `evals/` directory with labelled sets and eval results.
- DDL scripts for the storage schema.
- A `README.md` with setup, run, and reproduction instructions.

**Notion Document:**

- Solution summary and architecture overview.
- Rule-vs-LLM split decision and rationale (Part 1).
- Per-check writeup with prompt, rubric, eval results, and model choice (Part 2).
- Skill design and example invocation (Part 3).
- Agentic pipeline walkthrough (Part 4).
- Eval, tracing, and failure analysis findings (Part 5).
- Monitoring plan with cost math (Part 6).
- Dashboard screenshots and example insights (Part 7).
- "How you build" reflection (Part 8).
- IDE(s) / agentic tools used.

**Optional but valued:**

- A short Loom (≤5 minutes) walking through your agentic dev loop and the system running end-to-end. This is the easiest way for us to assess *how* you work, not just what you produced.

---

## **Dataset:**

Datasets-2025-08-08.zip

---

We're eager to review your implementation. If you have any questions or require clarification, please feel free to reach out to Suresh Badavath on LinkedIn.

Good luck!