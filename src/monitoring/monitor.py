"""Part 6: continuous, LLM-aware monitoring.

Three capabilities:
  1. tiering_plan()        — which checks run on every record / sample / schedule.
  2. estimate_monthly_cost — token×volume×frequency projection vs a cost ceiling.
  3. run_canary()          — re-run judges on the labelled golden set, compare to the committed
                             baseline (evals/<check>/results_<version>.json), alert on regression.

Run:  python -m src.monitoring.monitor --canary semantic_accuracy:v2 --cost
      MOCK_LLM=1 python -m src.monitoring.monitor --canary semantic_accuracy:v2
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from src.llm.client import MODELS, PRICING
from src.evals.harness import evaluate, EVALS

# ---- 1. What runs where -----------------------------------------------------
TIERING = [
    # (check, kind, cadence, model)
    ("required_fields/confidence/date/refs/dedup", "rule", "every record", "—"),
    ("staleness", "rule", "every record", "—"),
    ("semantic_accuracy", "llm", "every escalated record", MODELS["cheap"]),
    ("entity_resolution", "llm", "sample (10%) + all escalated", MODELS["judge"]),
    ("source_credibility", "llm", "sample (10%) + all escalated", MODELS["judge"]),
    ("golden-set canary", "llm", "nightly schedule", "all tiers"),
]


def tiering_plan() -> None:
    print("\n=== Monitoring tiers ===")
    for check, kind, cadence, model in TIERING:
        print(f"  [{kind:4}] {check:55} {cadence:28} {model}")
    print("\nModel-regression guard: prompts are pinned by version + sha256 hash (see traces).")
    print("Pin exact model ids (never `-latest`). Nightly canary re-scores the golden set; a drop")
    print("> threshold vs the committed baseline pages on-call (a silent vendor model swap shows here).")


# ---- 2. Cost math -----------------------------------------------------------
def estimate_monthly_cost(daily_volume: int, escalation_rate: float, sample_rate: float,
                          avg_in_tok: int = 480, avg_out_tok: int = 60,
                          ceiling_usd: float | None = None) -> dict:
    """Project monthly LLM spend. Math = volume × frequency × tokens × price, summed per check.

    - semantic_accuracy runs on every ESCALATED record (Haiku).
    - entity_resolution + source_credibility run on escalated records AND a flat sample (Sonnet).
    """
    days = 30
    escalated = daily_volume * escalation_rate
    sampled = daily_volume * sample_rate

    def per_call(model):
        pin, pout = PRICING[model]
        return (avg_in_tok * pin + avg_out_tok * pout) / 1_000_000

    sem_calls = escalated
    ent_calls = escalated + sampled
    src_calls = escalated + sampled

    monthly = days * (
        sem_calls * per_call(MODELS["cheap"]) +
        ent_calls * per_call(MODELS["judge"]) +
        src_calls * per_call(MODELS["judge"])
    )
    out = {
        "daily_volume": daily_volume, "escalation_rate": escalation_rate,
        "sample_rate": sample_rate, "monthly_calls": round(days * (sem_calls + ent_calls + src_calls)),
        "monthly_cost_usd": round(monthly, 2),
        "ceiling_usd": ceiling_usd,
        "under_ceiling": None if ceiling_usd is None else monthly <= ceiling_usd,
    }
    return out


# ---- 3. Canary --------------------------------------------------------------
def run_canary(check: str, version: str, max_f1_drop: float = 0.05) -> dict:
    """Re-score the golden set and compare F1 to the committed baseline; alert on regression."""
    baseline_path = EVALS / check / f"results_{version}.json"
    baseline = json.loads(baseline_path.read_text())["metrics"] if baseline_path.exists() else None

    # evaluate() overwrites results_<version>.json, so snapshot the baseline f1 first
    base_f1 = baseline["f1"] if baseline else None
    result = evaluate(check, version)
    new_f1 = result["metrics"]["f1"]

    alert = None
    if base_f1 is not None and (base_f1 - new_f1) > max_f1_drop:
        alert = (f"REGRESSION: {check} {version} f1 {base_f1}->{new_f1} "
                 f"(drop {base_f1-new_f1:.3f} > {max_f1_drop}) — page on-call / open ticket")
    print(f"\ncanary {check} {version}: baseline_f1={base_f1} new_f1={new_f1} "
          f"-> {alert or 'OK'}")
    return {"check": check, "version": version, "baseline_f1": base_f1,
            "new_f1": new_f1, "alert": alert}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="print the monitoring tiering plan")
    ap.add_argument("--cost", action="store_true", help="print a cost projection")
    ap.add_argument("--canary", default=None, help="check:version to canary, e.g. semantic_accuracy:v2")
    args = ap.parse_args()

    if args.plan or not (args.cost or args.canary):
        tiering_plan()
    if args.cost:
        print("\n=== Cost projection (500k records/day feed, $20k/mo ceiling) ===")
        print("  escalation_rate is the primary lever — tighter rules pre-filter more before LLMs.")
        for er in (0.4, 0.2, 0.1, 0.05):
            est = estimate_monthly_cost(500_000, escalation_rate=er, sample_rate=0.0,
                                        ceiling_usd=20_000)
            print(f"  escalation={er:>5}: {est['monthly_calls']:>12,} calls/mo  "
                  f"${est['monthly_cost_usd']:>11,.2f}/mo  under_ceiling={est['under_ceiling']}")
    if args.canary:
        check, _, version = args.canary.partition(":")
        run_canary(check, version or "v1")
