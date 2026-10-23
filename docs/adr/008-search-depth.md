# ADR-008 — Search depth: the top 20 of each search API

**Status:** accepted · **Evidence:** benchmark [`search_limit`](../../eval/benchmarks/search_limit.md), plus the 19-mention retrieval probe from the design research (`docs/research/`).

## Context

Each mention is searched with `wbsearchentities` and the REST full-text search (ADR-007). Each API returns up to 50 hits per call, and the client always fetches the full page and truncates it locally (ADR-002), so the depth costs no extra search request. Deeper searches do have a cost:

- more candidates whose terms must be fetched with `wbgetentities`;
- more candidates to embed in the pre-ranking;
- a higher chance that a popular wrong item displaces the right one.

## Options measured

| Results per API | CV accuracy | gold retrieved | gold kept after pre-ranking | Δ vs top 20 [95% CI] |
|---|---|---|---|---|
| 5 | 0.859 | 0.948 | 0.948 | −1.6 [−4.4, +1.0] |
| 10 | 0.874 | 0.971 | 0.960 | +0.0 [+0.0, +0.0] |
| **20** | **0.874** | **0.971** | 0.954 | – |
| 50 | 0.874 | 0.971 | 0.954 | +0.0 [+0.0, +0.0] |

Results from the retrieval probe run during the design phase: 19 ambiguous mentions such as "Jaguar", "Mercury", "Java" and "Washington", measured live on 2026-10-22.

| Hits | `wbsearchentities` recall | REST recall |
|---|---|---|
| top 10 | 17/19 | 17/19 |
| top 50 | 19/19 | 18/19 |

The union of the two APIs' top 20 found 19/19.

## Decision

Keep the **top 20 per API**.

## Why

- **5 is too shallow.** It loses the gold item for 2.3% of dev mentions, and accuracy follows.
- **On dev, 10, 20 and 50 tie.** Recall saturates at 10, because dev mentions are mostly retrievable early.
- **Harder mentions need a deeper search.** On the independent probe of hard ambiguous mentions, recall keeps growing between 10 and 50. Under ADR-003 a tie on dev would normally favour the cheaper option (10). Here there is evidence from outside dev that 10 is not enough on hard text, while 20 already reaches 19/19 with the union.
- **The extra cost is small.** No extra search request is made, only more terms to fetch and more candidates to embed in the pre-ranking. The pre-ranking cut (ADR-011) then keeps 10 candidates per mention, so the graph stage does not grow.

## Consequences

On KORE50, recall is still the main bottleneck (see the final evaluation). Going deeper (50) is the first lever to try on hard corpora, together with a better first-stage ranker.
