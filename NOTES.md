# Development notes

## What broke

### 1. Ground truth and tools disagreed on "evidence present"
The synthetic-data generator marked a dispute winnable based on per-token
`_has_evidence` flags. The mock tools returned `available: true` if ANY of
their evidence types existed. So `gather` marked all required evidence as
present whenever a tool succeeded at all.

Symptom: agent reported winnability 1.0 on disputes whose ground truth was
`winnable=False`. Sanity check agreement: 0/10.

Fix: each tool now returns an explicit `evidence_provided` list naming the
exact tokens it can vouch for on that order. `gather` checks membership in
that list per token instead of trusting a tool-level success flag.

### 2. Winnability denominator and threshold were miscalibrated
Winnability was computed over ALL required evidence, but ground truth only
considered the subset our tools can actually gather. Codes with unmappable
evidence types could never reach the fight threshold.

Fix: compute winnability over gatherable evidence only, and raise the fight
threshold to 0.99 (full coverage) to match how ground truth defines winnable.
Partial coverage routes to human review rather than auto-filing — a deliberate
choice, since a representment with missing required evidence usually loses and
the merchant only gets one shot.

Result: 0/10 -> 10/10 agreement.

### 3. Corpus evidence tokens outran tool coverage
42 extracted reason codes used ~60 distinct evidence tokens; the six mock tools
realistically cover ~35 of them. Scoped the demo to 3 codes (mastercard 4855,
visa 10.4, visa 13.1) where coverage is 3/5 or better, rather than faking tools
for every code. Extending to more codes is a matter of adding tools, not
changing the agent.

## On the 100% triage accuracy number

The triage decision is deterministic — winnability is computed directly from
tool outputs, and the fight threshold is calibrated to match how ground truth
defines "winnable." So 100% on triage is expected, not impressive. It shows the
plumbing is correct, not that the AI is clever.

The interesting numbers are elsewhere:

- **Letter quality** — where the LLM does work a template cannot. The judge
  scores specificity, rule alignment, honesty, and persuasiveness.
- **Fallback rate (~20%)** — the real reliability story. Validation caught
  malformed citations and missing identifiers in one out of five letters, and
  the system degraded to a template every time rather than shipping a bad
  representment.

Stating this openly is better than presenting 100% as a headline result.
