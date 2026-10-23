# ADR-011 — Pre-ranking: keep the 10 best candidates per mention, by a mixed cheap score

**Status:** accepted · **Evidence:** benchmark [`prerank`](../../eval/benchmarks/prerank.md) (timings on AC power).

## Context

Retrieval returns up to 45 candidates per mention: the union of two top-20 lists plus 5 from the human search (ADR-007, ADR-008). Every candidate that enters the graph stage costs:

- SPARQL rows for its types and relations;
- labels for its neighbours;
- embeddings for its facts;
- pairwise coherence work, quadratic in the number of candidates.

A cheap pre-ranking keeps K candidates per mention. Two orders are possible:

- **mixed:** 0.5 × similarity of the context with label + description, plus 0.3 × name match, plus 0.2 / (1 + search rank);
- **search_rank:** the APIs' own order.

## Options measured

| K, order | CV accuracy | gold kept | candidates/mention | triples/doc | ms/doc | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|
| 5, mixed | 0.869 | 0.942 | 4.5 | 855 | 326 | −0.5 [−1.6, +0.0] | 1.000 |
| **★ 10, mixed** | **0.874** | 0.954 | 8.8 | 1294 | 382 | – | – |
| 20, mixed | 0.880 | 0.965 | 16.4 | 2253 | 501 | +0.5 [+0.0, +1.6] | 1.000 |
| 30, mixed | 0.880 | 0.971 | 21.7 | 3189 | 689 | +0.5 [+0.0, +1.6] | 1.000 |
| 5, search_rank | 0.832 | 0.896 | 4.5 | 1129 | 234 | −4.2 [−7.2, −1.1] | 0.039 |
| 10, search_rank | 0.874 | 0.954 | 8.8 | 1757 | 597 | +0.0 [−2.2, +2.0] | 1.000 |
| 20, search_rank | 0.874 | 0.971 | 16.4 | 2662 | 889 | +0.0 [+0.0, +0.0] | 1.000 |

## Decision

Use **K = 10** with the **mixed** pre-ranking.

## Why

- **The mixed order is what makes a small K safe.** At K = 5, trusting the search engines' order loses the gold item for 10% of mentions and costs 4.2 points, which is significant. The mixed order keeps 94% of gold items at the same K.
- **K = 20 gains one mention for 31% more time.** That is +0.5 points, with an interval touching 0, for 501 ms/doc instead of 382 and 1.7× the triples. Under ADR-003, the cheaper option wins.
- **The mixed order also builds a smaller graph, and faster.** At K = 10, it gives 1,294 triples/doc against 1,757 with the search order, in 382 ms/doc against 597.

## Consequences

K is the knob with the clearest cost/recall trade-off. On a corpus much more ambiguous than dev, the cut can drop gold items that retrieval had found. The final evaluation therefore reports recall both before and after the cut. K = 20 is the first setting to try there, at about 30% more compute.
