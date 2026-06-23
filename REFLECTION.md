# How You Build — Reflection (Part 8)

## Dev loop

I built this in **Claude Code**, driving it as an agentic pair rather than an autocomplete. The shape
of the work was a tight **measure → diagnose → version → re-measure** loop, not a linear "write code,
then test" pass.

A concrete trace of how the loop actually ran:

1. **Profiled the data with throwaway scripts before writing a line of the system.** I had the agent
   stream the 24 `.jsonl` files and report category distribution, fill rates, confidence, duplicate
   IDs, and the found_at histogram. That EDA is what produced the rule-vs-LLM split in `PLAN.md` —
   I reached for rules first *because the data showed me where rules were enough*.
2. **Scaffolded the whole repo as stubs first**, with the trace schema and judge interfaces fixed up
   front, then filled them in. Getting the `Trace` contract right early meant cost/latency/prompt-hash
   were captured from the first real call, not bolted on later.
3. **Closed the eval loop on one judge before building the other two.** `semantic_accuracy` v1 scored
   F1 0.33 against my first 34 labels. Reading the *disagreements* (not the score) revealed the real
   problem wasn't the model — it was **my own labels and an under-scoped prompt**: I'd labelled
   speculative-language cases inconsistently and expected the check to catch entity/amount errors that
   belong to other checks. I wrote a v2 prompt that explicitly scopes the check to category↔evidence,
   reconciled the labels *once*, and re-ran **both** versions against the same corrected set so the
   delta was attributable to the prompt. v2: **F1 0.33 → 0.88, precision → 1.0.** That's the loop the
   whole assessment is about, and Claude Code made each turn of it cost minutes.

Agentic tooling changed the *unit of work*. I was reasoning about prompts, rubrics, and eval deltas —
the agent handled the mechanical span (sampling records, writing harness plumbing, SQL, the Streamlit
view). I spent my attention on the parts that needed judgement: **what counts as ground truth**, and
**which dimension owns which failure**.

## Where the LLM saved the most time — and where it cost more than rules

**Saved the most:** the semantic checks no rule could express. `source_credibility` distinguishing a
real funding announcement from an obituary, an exam-date notice, or a vaccination site that merely sits
in a *former* store — a regex would never get there, and the judge hit F1 0.96 out of the box.
`entity_resolution` turned out to be the standout: against synthetic mislinks it scored a uselessly-easy
1.0, but **on real data it repeatedly caught parent/subsidiary mislinks** (record linked to *Unipart
Manufacturing Group* where the article names *Unipart Logistics* / *Unipart Rail*). No rule I could
write would know those are different subsidiaries.

**Cost more than rules would have:** everything deterministic. Schema validation, null checks,
`confidence ∈ [0,1]`, future-date detection, duplicate keys, broken-reference checks — these are
rules *by design*, and the pipeline runs them first so an LLM never sees a record that a free check can
already reject. The one place the LLM actively *under*-performed a rule was the truncated-company-name
cases ("Company", "International"): an LLM judging name-vs-summary mostly passes them because the
summary is generated from that same name. A two-line rule (`name too short / generic`) catches them
more cheaply and more reliably. That's in the entity_resolution failure notes as a known boundary.

The cost discipline is real and measured: the monitoring projection shows that at 500k records/day
with 40% escalation to Sonnet, this blows past a $20k/mo ceiling (~$33k). **The lever isn't the model —
it's the escalation rate**, i.e. how good the rules are at pre-filtering. That reframed rules from
"the boring part" to "the cost-control layer."

## If I had two more weeks and a real production budget

1. **Replace synthetic eval negatives with mined real ones.** The pipeline already surfaces real
   parent/subsidiary errors; I'd harvest those into the `entity_resolution` eval so its 1.0 means
   something. Same for a balanced, multi-domain `source_credibility` set (mine is LPU/Dillard's-heavy).
2. **An LLM-assisted labelling + adjudication workflow.** My biggest time sink and biggest error source
   was *labelling*. I'd build a second-model adjudicator that flags label/judge disagreements for human
   review — turning the eval set into a living, version-controlled asset.
3. **Wire the canary to CI + a real alert surface.** The regression check exists; I'd schedule it
   nightly, pin model snapshots, and route a golden-set F1 drop to Slack/a ticket — the actual defense
   against a silent `claude-*-latest` swap.
4. **Promote `daily_metrics` from a schema to a populated rollup** so the dashboard trend survives
   millions of rows, and add per-prompt-version drift lines.
5. **Make remediation a closed loop**: today the pipeline *proposes* (reject/merge/correct) and queues
   for humans. With a real budget I'd add a human-in-the-loop UI and feed approved corrections back as
   new eval examples.

## One known weakness I'd flag at handover

**The eval sets are small, mine alone labelled, and uneven.** `semantic_accuracy` is 52 examples
(38/14), the other two are 30, and `entity_resolution`'s negatives are synthetic and easy. Every
reported precision/recall number rests on a single labeller's judgement, and several of the "misses"
are genuinely my-label-vs-model-defensible (the pending-merger and "set to debut in October 2018" cases
in the failure analyses). **Do not read these scores as production-validated** — they prove the loop
works and the judges are directionally sound. Before trusting any threshold in production, the sets
need a second labeller, real (not synthetic) negatives, and broader domain coverage. I've documented
this in each `evals/<check>/FAILURE_ANALYSIS.md` so it isn't a surprise.
