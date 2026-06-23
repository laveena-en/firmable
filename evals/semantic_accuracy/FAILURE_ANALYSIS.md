# Failure Analysis — semantic_accuracy (Part 5)

## Method
Ground truth (52 hand-labelled records) was **fixed and corrected once**; both prompt versions
were then evaluated against that same set, so the v1→v2 delta reflects the **prompt change only**,
not relabelling. Positive class = `fail` (a caught bad record).

| Version | n | acc | precision | recall | f1 | cost | avg latency |
|---|---|---|---|---|---|---|---|
| v1 | 52 | 0.865 | 0.706 | 0.857 | 0.774 | $0.041 | 1390ms |
| **v2** | 52 | **0.942** | **1.000** | 0.786 | **0.880** | $0.062 | 1484ms |

v2 lifted accuracy +0.077 and F1 +0.106, and **eliminated all false positives** (precision 1.0).

## What v1 got wrong (and v2 fixed)
v1's 5 false positives were all **scope leakage** — it failed records for problems other checks own:
- `eb87a36c` / `15462abf` — flagged because the *company/direction* looked wrong (entity_resolution's job).
- `52eaa167` — flagged because the *$ amount/date* didn't match the sentence (numeric validation's job).
- `504b148a` — over-cautious about a co-mentioned third party.
- `bcc7350e` — a real announced hire, flagged on a "set to open" detail about the venue, not the hire.

v2's scope section ("judge ONLY category↔evidence; entity and amounts are out of scope") removed
every one of these false alarms.

## What v2 still gets wrong (3 false negatives — genuinely hard)
1. `81edfae3` merges_with — "antitrust review **reportedly holding up the merger**." The deal is
   *pending/blocked*, not completed; v2 read it as an ongoing merger. **Real weakness:** the prompt
   doesn't distinguish *announced/pending* from *completed* for deal categories.
2. `c7ee4f3d` launches — "**is all set to** debut … in October 2018", event dated Oct 2018. Arguably
   the launch *did* happen that month — this is a **label-quality edge case** as much as a judge miss.
3. `ffd5a9af` attends_event — judge **over-infers attendance** from "following the presentation at the
   conference." The sentence never states the subject attended.

## What I'd change next
- Add an explicit **announced/pending vs completed** rule for deal categories (`merges_with`,
  `acquires`) — likely fixes #1 and is the highest-value next prompt edit.
- Re-examine 3–4 remaining **label edge cases** (#2) with a second labeller to cut ground-truth noise.
- **Known dataset weakness:** the 18 mined negatives are all Marriott (one company / hospitality
  domain). Broaden the negative pool across industries before trusting these numbers in production.
- Class balance is 38/14 (27% fail) — better than the original 28/6, still worth pushing toward ~40%.
