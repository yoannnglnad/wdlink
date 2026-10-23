# ADR-022 — NIL rule: a single score threshold θ

**Status:** accepted · **Evidence:** benchmark [`nil_rule`](../../eval/benchmarks/nil_rule.md).

## Context

The assignment says the top candidate should be selected "when sufficient evidence is available". There are two common ways to define "insufficient":

- the best score is too low (absolute threshold θ);
- the best candidate barely beats the second one (margin δ).

The dev split contains 18 NIL mentions, 12 of which are hard: invented entities whose names collide with real items ("Thomas Berger", "Sophie Martin") or nearly match them ("Nordic Snow and Ice Data Centre"). This is the case the rule has to handle.

## Options measured

In both variants, θ (and δ) were tuned on four folds and scored on the fifth.

| Variant | CV accuracy | NIL recall | NIL precision | ambiguous | Δ [95% CI] |
|---|---|---|---|---|---|
| **θ only** | **0.874** | 0.667 | **1.000** | **0.803** | – |
| θ and δ | 0.874 | 0.722 | 0.765 | 0.788 | +0.0 [−1.6, +1.5] |

The tuned values were stable across folds: θ = 0.38 in all five folds, and δ = 0.01 in four of five.

## Decision

Use θ only (`min_margin = 0`).

## Why

- **Accuracy is identical.** The margin rule turns one more NIL into a correct answer, but also turns correct links into wrong NILs: NIL precision drops from 1.00 to 0.77, and accuracy on ambiguous mentions from 0.803 to 0.788.
- **Ambiguity and absence are different problems.** A small margin means two real items are close, as with the Nobel Prizes in Physics and in Chemistry for Marie Curie. Answering NIL in that case discards a probably correct answer. A low absolute score is what actually signals that nothing in Wikidata fits.
- **The simpler rule wins the tie,** as ADR-003 prescribes.

## Consequences

- A mention is NIL when its best score S is below θ, which the final evaluation tunes on all of dev.
- The ranking is still returned for NIL mentions, so a human reviewer can see the near-misses.
- Half of the hard NILs (6 of 12) are still linked to a namesake, while every plain NIL is detected; NIL recall is 0.667 over all 18 NILs. This is the main known weakness. Coherence is a bonus only, so a namesake with no connection to the rest of the text is never penalised; it just gets no bonus.
