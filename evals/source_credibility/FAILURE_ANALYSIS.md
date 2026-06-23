# Eval Notes — source_credibility (Part 5)

| Version | n | acc | precision | recall | f1 |
|---|---|---|---|---|---|
| v1 | 30 | 0.967 | 1.000 | 0.917 | 0.957 |

Balance: 18 pass / 12 fail. Positive class = `fail` (caught noise).

## The single miss
- `6bc9b3c3` Oncyber "AI-Powered Tool Lets Users Customize Metaverse with Ease!" — I labelled **fail**
  (advertorial/promotional crypto content); the judge passed it as a real product launch. **Defensible
  disagreement** — it does describe a concrete feature release, just in marketing tone. This marks the
  fuzzy boundary between "promotional" and "real product launch"; worth a rubric clarification, not a
  judge bug.

## Known weaknesses
- The set skews to a few entities (LPU, Dillard's, Global Geoscience) because it was sampled from one
  file — domain/source diversity is limited. Broaden before trusting in production.
- "Relevance" (company is only a backdrop) and "credibility" (marketing vs news) are bundled into one
  judge here. If they need separate thresholds later, split into two checks.
