# ADR-005 — Generic-word filter: drop one-word common nouns with Zipf frequency ≥ 3.5

**Status:** accepted (supersedes the initial 4.5) · **Evidence:** benchmark [`generic_filter`](../../eval/benchmarks/generic_filter.md), end-to-end (A2KB).

## Context

The assignment asks for "relevant terms, named entities, and noun phrases", and lists "fully automated linking of every possible noun phrase" as out of scope. spaCy's noun chunks include generic words ("research", "study", "team", "planet"). Every such word gets linked to *some* Wikidata item, so each one is a false positive end to end.

The filter applies to one-word common nouns only:

- **always kept:** proper nouns and noun compounds;
- **kept:** a one-word common noun whose English Zipf frequency (`wordfreq`) is below the cut-off;
- **dropped:** a one-word common noun at or above the cut-off.

The cut-off does not affect linking with gold spans (D2KB is identical for every variant); only the extraction changes.

## Options measured

End to end on dev: our extraction, then linking. Thresholds are tuned by cross-validation. There are 173 linkable gold mentions.

| Cut-off | Predicted links | A2KB precision | A2KB recall | A2KB F1 | ΔF1 vs 3.5 [95% CI] |
|---|---|---|---|---|---|
| no filter | 295 | 0.458 | 0.780 | 0.577 | −12.9 [−16.4, −9.5] |
| Zipf < 5.0 | 254 | 0.528 | 0.775 | 0.628 | −7.9 [−11.1, −4.6] |
| Zipf < 4.5 (initial default) | 233 | 0.575 | 0.775 | 0.660 | −4.6 [−7.1, −1.9] |
| Zipf < 4.0 | 218 | 0.615 | 0.775 | 0.685 | −2.1 [−4.0, +0.2] |
| **Zipf < 3.5** | 198 | 0.662 | 0.757 | 0.706 | – |
| Zipf < 3.0 | 188 | 0.681 | 0.740 | 0.709 | +0.3 [−1.2, +1.6] |
| Zipf < 2.5 | 183 | 0.689 | 0.728 | 0.708 | +0.2 [−2.0, +2.2] |

ΔF1 is a paired, document-level bootstrap of the end-to-end F1 difference (2,000 resamples).

The grid first stopped at 3.5, where the best F1 sat at its edge. It was extended to 3.0 and 2.5 to locate the optimum.

## Decision

Cut-off **3.5**.

## Why

- **The filter matters.** Without it, F1 drops to 0.577: 160 of the 295 predicted links are wrong.
- **4.5 was too lenient, significantly.** Going from 4.5 to 3.5 removes 35 predicted links, of which 32 were wrong and only 3 right. It raises F1 by 4.6 points, and the interval [+1.9, +7.1] excludes 0.
- **2.5–3.5 is a plateau** (F1 0.706–0.709, intervals around 0). Within it, 3.5 keeps the most recall (0.757 against 0.740 at 3.0). This matters for research text, because science words sit just around 3:

| Word | Zipf |
|---|---|
| radioactivity | 2.91 |
| photosynthesis | 3.03 |
| metadata | 3.36 |
| helium | 3.42 |

At 3.0, photosynthesis, metadata and helium would be dropped, and radioactivity, the assignment's own example, would only just pass.

## Consequences

- One-word common nouns at or above 3.5, such as "physics" (4.39) or "protein" (4.53), are no longer extracted on their own. They are still linked inside a named entity or a compound ("Nobel Prize in Physics", "protein folding").
- A domain-specific stop list would beat a frequency cut-off for a given corpus. The cut-off is used because it needs no hand-built resource.
