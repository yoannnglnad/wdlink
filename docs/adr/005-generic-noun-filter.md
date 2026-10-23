# ADR-005 — Generic-word filter: drop one-word common nouns with Zipf frequency ≥ 3.5

**Status:** accepted (supersedes the initial 4.5) · **Evidence:** benchmark [`generic_filter`](../../eval/benchmarks/generic_filter.md), end-to-end (A2KB).

## Context

The assignment asks for "relevant terms, named entities, and noun phrases", and lists "fully automated linking of every possible noun phrase" as out of scope. spaCy's noun chunks include generic words ("research", "study", "team", "planet"). Every such word gets linked to *some* Wikidata item, so each one is a false positive end to end.

The filter applies to noun chunks that are not named entities (`extract._is_specific`):

- **always kept:** chunks containing a proper noun, and multi-word chunks containing a noun compound;
- **kept:** other chunks with at least one non-stop-word noun or adjective whose English Zipf frequency (`wordfreq`) is below the cut-off;
- **dropped:** the rest, for example "research" or "closest planet".

The cut-off does not affect linking with gold spans (D2KB is identical for every variant); only the extraction changes.

## Options measured

End to end on dev: our extraction, then linking. Thresholds are tuned by cross-validation. There are 173 linkable gold mentions.

| Cut-off | Predicted links | A2KB precision | A2KB recall | A2KB F1 | ΔF1 vs 3.5 [95% CI] |
|---|---|---|---|---|---|
| no filter | 297 | 0.485 | 0.832 | 0.613 | −12.8 [−16.6, −9.1] |
| Zipf < 5.0 | 254 | 0.555 | 0.815 | 0.660 | −8.0 [−11.3, −4.8] |
| Zipf < 4.5 (initial default) | 232 | 0.608 | 0.815 | 0.696 | −4.4 [−7.1, −1.7] |
| Zipf < 4.0 | 216 | 0.648 | 0.809 | 0.720 | −2.1 [−4.0, +0.2] |
| **Zipf < 3.5** | 197 | 0.695 | 0.792 | 0.741 | – |
| Zipf < 3.0 | 184 | 0.728 | 0.775 | 0.751 | +1.0 [−0.6, +2.8] |
| Zipf < 2.5 | 177 | 0.734 | 0.751 | 0.743 | +0.2 [−2.2, +2.8] |

Extraction uses the current default, `en_core_web_trf`. The suite was first run with `en_core_web_sm`, which gave the same pattern: 4.5 → 3.5 raised F1 from 0.660 to 0.706 (+4.6 [+1.9, +7.1]), with a plateau from 2.5 to 3.5.

ΔF1 is a paired, document-level bootstrap of the end-to-end F1 difference (2,000 resamples).

The grid first stopped at 3.5, where the best F1 sat at its edge. It was extended to 3.0 and 2.5 to locate the optimum.

## Decision

Cut-off **3.5**.

## Why

- **The filter matters.** Without it, F1 drops to 0.613: 153 of the 297 predicted links are wrong.
- **4.5 was too lenient, significantly.** Going from 4.5 to 3.5 removes 35 predicted links, of which 4 were right and 31 wrong. It raises F1 by 4.4 points, and the interval [+1.7, +7.1] excludes 0.
- **2.5–3.5 is a plateau** (F1 0.741–0.751, intervals around 0). Within it, 3.5 keeps the most recall (0.792 against 0.775 at 3.0). This matters for research text, because science words sit just around 3:

| Word | Zipf |
|---|---|
| radioactivity | 2.91 |
| photosynthesis | 3.03 |
| helium | 3.42 |

At 3.0, photosynthesis and helium would be dropped, and radioactivity, the assignment's own example, would only just pass. These values are recorded in [`evidence.md`](../../eval/benchmarks/evidence.md).

## Consequences

- One-word common nouns between 3.5 and 4.5, such as "physics" (4.39), are no longer extracted on their own. They are still linked inside a named entity or a compound ("Nobel Prize in Physics").
- A domain-specific stop list would beat a frequency cut-off for a given corpus. The cut-off is used because it needs no hand-built resource.
