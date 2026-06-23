"""Eval harness (Part 5). Re-run a judge against its labelled set, report
precision/recall/accuracy, and drift vs. the previous prompt version.

Run:  python -m src.evals.harness --check semantic_accuracy --version v1
      python -m src.evals.harness --check semantic_accuracy --version v2 --compare v1

Labelled set format (evals/<check>/labelled.jsonl): {"record": {...}, "label": "pass"|"fail"}
Set MOCK_LLM=1 to run offline with the heuristic stand-in.

The positive class for precision/recall is FAIL — i.e. "did the judge correctly catch a bad record".
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from src.llm import judges

EVALS = Path(__file__).resolve().parents[2] / "evals"

# Each entry maps a labelled item -> a judge call. Items carry whatever inputs the check needs
# (record, company, article) alongside the ground-truth label.
JUDGE_FNS = {
    "semantic_accuracy": lambda it, ver: judges.semantic_accuracy(it["record"], version=ver),
    "entity_resolution": lambda it, ver: judges.entity_resolution(
        it["record"], it["company"], it.get("company2"), version=ver),
    "source_credibility": lambda it, ver: judges.source_credibility(it["article"], version=ver),
}


def _record_id(item: dict) -> str:
    for k in ("record", "article"):
        if k in item:
            return item[k].get("id", "?")
    return "?"


def _metrics(rows: list[dict]) -> dict:
    # positive class = "fail" (a caught bad record)
    tp = sum(1 for r in rows if r["label"] == "fail" and r["pred"] == "fail")
    fp = sum(1 for r in rows if r["label"] == "pass" and r["pred"] == "fail")
    fn = sum(1 for r in rows if r["label"] == "fail" and r["pred"] == "pass")
    tn = sum(1 for r in rows if r["label"] == "pass" and r["pred"] == "pass")
    err = sum(1 for r in rows if r["pred"] not in ("pass", "fail"))
    n = len(rows)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    accuracy = (tp + tn) / n if n else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "errors": err,
            "precision": round(precision, 3), "recall": round(recall, 3),
            "accuracy": round(accuracy, 3), "f1": round(f1, 3)}


def evaluate(check: str, version: str, compare: str | None = None) -> dict:
    labelled_path = EVALS / check / "labelled.jsonl"
    rows = []
    with labelled_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            pred = JUDGE_FNS[check](item, version)
            rows.append({"id": _record_id(item), "label": item["label"],
                         "pred": pred.get("verdict"), "reason": pred.get("reason"),
                         "confidence": pred.get("confidence")})

    m = _metrics(rows)
    result = {"check": check, "version": version, "metrics": m, "rows": rows}
    out_path = EVALS / check / f"results_{version}.json"
    out_path.write_text(json.dumps(result, indent=2))

    print(f"\n=== {check} {version}  (positive class = fail) ===")
    print(f"  n={m['n']}  acc={m['accuracy']}  precision={m['precision']}  "
          f"recall={m['recall']}  f1={m['f1']}  errors={m['errors']}")
    print(f"  confusion: tp={m['tp']} fp={m['fp']} fn={m['fn']} tn={m['tn']}")

    if compare:
        prev_path = EVALS / check / f"results_{compare}.json"
        if prev_path.exists():
            prev = json.loads(prev_path.read_text())["metrics"]
            print(f"\n  drift vs {compare}: "
                  f"acc {prev['accuracy']}->{m['accuracy']} ({m['accuracy']-prev['accuracy']:+.3f}), "
                  f"f1 {prev['f1']}->{m['f1']} ({m['f1']-prev['f1']:+.3f})")
        else:
            print(f"\n  (no prior results_{compare}.json to compare)")

    # surface misses for failure analysis
    misses = [r for r in rows if r["label"] != r["pred"]]
    if misses:
        print(f"\n  misses ({len(misses)}):")
        for r in misses:
            print(f"    [{r['label']}->{r['pred']}] {r['id']}: {r['reason']}")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", required=True)
    ap.add_argument("--version", default="v1")
    ap.add_argument("--compare", default=None)
    args = ap.parse_args()
    evaluate(args.check, args.version, args.compare)
