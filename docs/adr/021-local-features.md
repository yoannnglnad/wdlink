# ADR-021 — Local score: text, name, type and popularity, with hand-set weights

**Status:** accepted · **Evidence:** benchmark [`local_features`](../../eval/benchmarks/local_features.md).

## Context

Before any graph evidence, each candidate gets a local score:

```
L = w_txt·s_txt + w_name·s_name + w_type·s_type + w_pop·s_pop
```

The weights could be hand-set, grid-searched or learned. The name match could be lenient (any alias, token-set ratio) or strict (exact alias, fuzzy match on the label only). The dev split, at 191 mentions, is too small to learn a ranking model without overfitting. The question is therefore whether the hand-set weights sit in a stable region and whether every feature earns its place.

## Options measured

All variants were scored by 5-fold cross-validation on dev, with the NIL threshold and β re-tuned on the training folds each time.

| Variant | CV accuracy | Δ vs default [95% CI] |
|---|---|---|
| **default 0.50 / 0.20 / 0.15 / 0.15, strict name match** | **0.874** | – |
| without popularity | 0.754 | −12.0 [−17.0, −7.3] |
| without name match | 0.843 | −3.1 [−6.3, +0.0] |
| fuzzy name match on aliases too | 0.843 | −3.1 [−6.0, −0.5] |
| popularity weight 0.30 | 0.848 | −2.6 [−5.1, −0.5] |
| text weight 0.30 | 0.864 | −1.0 [−3.3, +1.0] |
| text weight 0.70 | 0.890 | +1.6 [+0.0, +3.5] |

## Decision

Keep the four features and the default weights, with the strict name match.

## Why

- **Popularity is the strongest single feature.** Removing it costs 12 points, an interval far from 0. It must stay a minority weight, though: doubling it costs 2.6 points, because the first search hit, often the most popular item, is wrong for 47 ambiguous dev mentions.
- **The name match helps.** Its lenient variant hurts, and the interval excludes 0. A token-set match on aliases gives "Darwin" a high name score for the mention "Northern Territory", because one of Darwin's aliases is "Darwin, Northern Territory".
- **The text weight lies on a plateau.** Moving it from 0.30 to 0.70 changes accuracy by −1.0 to +1.6 points, and both intervals touch 0. Under ADR-003, a variant whose interval does not exclude 0 is not adopted, so the default stays. With more dev data, a higher text weight is the first thing to re-test.
- **Weights are not learned.** A logistic regression on 191 mentions would fit noise. A full grid over 4 weights × θ × β would make the dev score optimistic. A one-factor-at-a-time sensitivity analysis is the honest test at this data size.

## Consequences

Weights live in `RankingConfig` (`src/wdlink/config.py`). The table above shows that no single weight change moves accuracy by more than 3 points, except removing popularity.
