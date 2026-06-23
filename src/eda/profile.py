"""Part 1 baseline profiling — formalizes the exploratory pass into one reproducible command.

Run:  python -m src.eda.profile --glob 'Datasets/*.jsonl'
      python -m src.eda.profile --glob 'Datasets/*.jsonl' --max-records 25000   # quick sample
      python -m src.eda.profile --glob 'Datasets/*.jsonl' --json report.json    # machine-readable

Emits: record counts, category distribution, attribute fill rates, confidence stats,
human_approved ratio, found_at year histogram, duplicate ids/summaries, broken refs, included types.

Streams line-by-line so it runs over the full 2.3 GB / 620k-event feed without loading it into memory.
"""
from __future__ import annotations
import argparse
import glob
import json
import re
from collections import Counter

_WS = re.compile(r"\s+")


def _norm(s: str | None) -> str:
    return _WS.sub(" ", (s or "").lower().strip())


def profile(files: list[str], max_records: int | None = None) -> dict:
    n_events = 0
    n_files = 0
    categories: Counter = Counter()
    included_types: Counter = Counter()
    rel_keys: Counter = Counter()
    attr_filled: Counter = Counter()     # attr -> count of non-empty
    found_year: Counter = Counter()
    approved: Counter = Counter()
    conf_buckets: Counter = Counter()    # "0.0-0.1" -> count
    conf_sum = 0.0
    conf_n = 0
    conf_min, conf_max = 1.0, 0.0

    seen_ids: set[str] = set()
    dup_ids = 0
    summary_counts: Counter = Counter()
    broken_company1 = 0
    broken_source = 0

    EMPTY = (None, "", [], {})

    stop = False
    for path in files:
        if stop:
            break
        n_files += 1
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                included = obj.get("included", [])
                included_ids = {inc["id"] for inc in included}
                for inc in included:
                    included_types[inc["type"]] += 1

                for ev in obj.get("data", []):
                    n_events += 1
                    a = ev.get("attributes", {})
                    categories[a.get("category")] += 1

                    # attribute fill rate
                    for k, v in a.items():
                        if v not in EMPTY:
                            attr_filled[k] += 1

                    # confidence
                    c = a.get("confidence")
                    if isinstance(c, (int, float)):
                        conf_sum += c
                        conf_n += 1
                        conf_min = min(conf_min, c)
                        conf_max = max(conf_max, c)
                        b = min(int(c * 10), 9)
                        conf_buckets[f"{b/10:.1f}-{(b+1)/10:.1f}"] += 1

                    # human_approved
                    approved[bool(a.get("human_approved"))] += 1

                    # found_at year
                    fa = a.get("found_at") or ""
                    if len(fa) >= 4 and fa[:4].isdigit():
                        found_year[fa[:4]] += 1

                    # duplicates
                    eid = ev.get("id")
                    if eid in seen_ids:
                        dup_ids += 1
                    else:
                        seen_ids.add(eid)
                    summary_counts[_norm(a.get("summary"))] += 1

                    # relationships + broken refs
                    rels = ev.get("relationships", {})
                    for rk in rels:
                        rel_keys[rk] += 1
                    c1 = (rels.get("company1", {}).get("data") or {}).get("id")
                    if c1 and c1 not in included_ids:
                        broken_company1 += 1
                    src = (rels.get("most_relevant_source", {}).get("data") or {}).get("id")
                    if src and src not in included_ids:
                        broken_source += 1

                    if max_records is not None and n_events >= max_records:
                        stop = True
                        break
                if stop:
                    break

    dup_summaries = sum(1 for s, c in summary_counts.items() if c > 1 and s)
    pct = lambda x: round(100 * x / n_events, 2) if n_events else 0.0

    return {
        "files": n_files,
        "events": n_events,
        "unique_event_ids": len(seen_ids),
        "duplicate_event_ids": dup_ids,
        "included_types": dict(included_types),
        "relationship_presence_pct": {k: pct(v) for k, v in rel_keys.most_common()},
        "human_approved_pct": pct(approved[True]),
        "confidence": {
            "min": round(conf_min, 4) if conf_n else None,
            "mean": round(conf_sum / conf_n, 4) if conf_n else None,
            "max": round(conf_max, 4) if conf_n else None,
            "histogram": dict(sorted(conf_buckets.items())),
        },
        "found_at_by_year": dict(sorted(found_year.items())),
        "top_categories": dict(categories.most_common(25)),
        "attribute_fill_rate_pct": {k: pct(v) for k, v in attr_filled.most_common()},
        "duplicate_summaries": dup_summaries,
        "top_repeated_summaries": [
            {"count": c, "summary": s} for s, c in summary_counts.most_common(5) if c > 1
        ],
        "broken_refs": {"company1": broken_company1, "most_relevant_source": broken_source},
    }


def _print_summary(r: dict) -> None:
    print(f"\n=== News-events profile: {r['events']:,} events across {r['files']} file(s) ===")
    print(f"  unique ids: {r['unique_event_ids']:,}  duplicate ids: {r['duplicate_event_ids']}")
    print(f"  human_approved: {r['human_approved_pct']}%   duplicate summaries: {r['duplicate_summaries']:,}")
    print(f"  broken refs: {r['broken_refs']}")
    print(f"  confidence: min={r['confidence']['min']} mean={r['confidence']['mean']} max={r['confidence']['max']}")
    print(f"  included types: {r['included_types']}")
    print(f"  relationship presence %: {r['relationship_presence_pct']}")
    print("\n  top categories:")
    for c, v in r["top_categories"].items():
        print(f"    {v:8,}  {c}")
    print("\n  attribute fill rate %:")
    for k, v in r["attribute_fill_rate_pct"].items():
        print(f"    {v:6.1f}  {k}")
    print("\n  found_at by year:")
    for y, v in r["found_at_by_year"].items():
        print(f"    {y}: {v:,}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default="Datasets/*.jsonl")
    ap.add_argument("--max-records", type=int, default=None, help="cap events scanned (quick sample)")
    ap.add_argument("--json", default=None, help="also write the full report as JSON to this path")
    args = ap.parse_args()

    files = sorted(glob.glob(args.glob))
    if not files:
        raise SystemExit(f"no files matched: {args.glob}")
    report = profile(files, args.max_records)
    _print_summary(report)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nfull report written to {args.json}")
