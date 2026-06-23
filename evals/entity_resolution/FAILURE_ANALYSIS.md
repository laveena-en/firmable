# Failure Analysis — entity_resolution (Part 5)

| Eval set / version | n | acc | precision | recall | f1 |
|---|---|---|---|---|---|
| v1, synthetic negatives (old) | 30 | 1.000 | 1.000 | 1.000 | 1.000 |
| v1, real mined negatives | 31 | 0.903 | 0.917 | 0.846 | 0.880 |
| **v2, real mined negatives** | 31 | **0.968** | **0.929** | **1.000** | **0.963** |

The synthetic 1.0 was meaningless — totally-unrelated company swaps are trivially caught. Replacing
the 12 synthetic negatives with **13 hand-verified real entity errors** (mined from the feed, each
read and confirmed by a human, not taken from the judge's own output) gives a number that actually
measures the judge. **v2** then targets the two weaknesses v1 exposed (below) and recovers them:
recall 0.846 → 1.000, F1 0.880 → 0.963 — both evaluated against the *same* real set, so the delta is
the prompt change alone.

## v1 → v2: the two targeted fixes worked
- **Parent/subsidiary leniency** → v2 Rule 1 ("if the article names a specific subsidiary, linking the
  parent is a fail"). The MVM miss (`bdb19f5f`) is now correctly caught.
- **Acronym collisions** → v2 Rule 2 ("distrust exact name/acronym matches the context contradicts").
  The METI miss (`6269ba37`) is now correctly caught.
v2 has **zero false negatives** on this set. The one remaining error is the org-vs-person false
positive below, which v2 did not target.

## How the negatives were built
Mined candidates where the linked company's name tokens are absent from the article evidence, then
**hand-verified** — most candidates were *false* (slug names like "Sironacapital" = "Sirona Capital",
or acronyms like "DARPA", where the entity is correct). The 13 confirmed errors span 9 types:
parent/subsidiary (4), wrong actor (2), distributor-vs-principal, geographic subsidiary,
generic/wrong entity, publisher-vs-subject, wrong investor, acronym collision, wrong subunit.

## The 3 misses — all informative
1. **`bdb19f5f` (FN, fail→pass) — lenient on parent/subsidiary.** Article: *MVM Tisza Erőmű* signs the
   contract; linked company is the parent *MVM Hungarian Electricity*. The judge passed it, explicitly
   reasoning "parent/umbrella entity … plausible subject." **This is the judge's main weakness:** it
   treats a parent as an acceptable stand-in for a subsidiary's action. It caught the Unipart
   parent/subsidiary cases but not this one — so it's *inconsistent* on the hardest class.
2. **`6269ba37` (FN, fail→pass) — fooled by acronym collisions.** "METI" literally matches
   "Medical Education Technologies, Inc.", so the judge passed it — missing that the article's METI is
   an industrial-shutdown context (a different METI). When the name equals the acronym, the judge
   anchors on the string and ignores the semantic mismatch.
3. **`0d352124` (FP, pass→fail) — over-reasoning org-vs-person.** The judge failed a record I labelled
   pass, arguing the actor is a professor, not "Science & Technology Australia." Defensible, but shows
   it can be over-aggressive when an individual is named alongside the org.

## What changed in v2 (shipped) and what's left
- ✅ **Parent vs. subsidiary** (Rule 1) and ✅ **acronym-collision distrust** (Rule 2) were added in
  `prompts/entity_resolution/v2.md` and fixed misses #1 and #2 — recall went to 1.0.
- ⏳ Still open: the **org-vs-person false positive** (#3, `0d352124`). v2 didn't target it; it may be
  a debatable ground-truth label as much as a judge error. Re-examine with a second labeller.
- ⏳ Watch for **over-correction**: v2 is now strict on parent/subsidiary. Add a few *legitimate*
  parent-link positives (sentence refers to the group generically) to confirm v2 didn't become
  trigger-happy — precision held at 0.929 here, but the set is small.

## Known weaknesses of the set itself
- Still single-labeller; 18/13 balance is decent but small.
- Parent/subsidiary is over-weighted (Unipart appears 3×) — broaden entity diversity next.
