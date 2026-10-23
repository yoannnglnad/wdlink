# ADR-016 — Neighbourhoods from a whitelist of ~40 descriptive properties

**Status:** accepted · **Evidence:** benchmark [`coherence`](../../eval/benchmarks/coherence.md), variant "weighted, all properties as neighbours" (timings on AC power).

## Context

Coherence (ADR-020) compares candidates through their neighbours: two candidates that share rare neighbours are related. A popular item has hundreds of item-valued statements; Marie Curie (Q7186) has 297 properties. The neighbourhood can be built in two ways:

- from **all** item-valued statements;
- from a **whitelist** of about 40 descriptive properties: location, country, field of work, award received, educated at, employer, part of, author, performer, discoverer, named after, and so on.

Some properties are excluded in both cases:

- type properties (P31/P279), which link everything to hubs such as *human*;
- negative statements (P1889, P460);
- P1346 "winner", which gives hundreds of values to every prize.

Direct statements *between two candidates* are always used, whatever their property.

## Options measured

| Neighbourhood | CV accuracy | triples/doc | prepare ms/doc | rank ms/doc | Δ [95% CI] |
|---|---|---|---|---|---|
| **whitelist** | 0.874 | 1,294 | 504 | 2.9 | – |
| all properties | 0.874 | 2,837 | 489 | 3.6 | +0.0 [+0.0, +0.0] |

## Decision

Keep the whitelist (`config.RELATION_PROPERTIES`).

## Why

- **Same accuracy, mention by mention, with half the graph.** The extra properties add 1,543 triples per document but do not change a single decision on dev.
- **Readability.** The whitelist also defines which facts can be verbalised in the candidate cards (ADR-018). "award received: Nobel Prize in Physics" is a useful fact; "described by source: Brockhaus and Efron Encyclopedic Dictionary" or "on focus list of Wikimedia project" is not. Keeping one list for both keeps the evidence interpretable.
- **Cost is not the argument.** Both variants cost the same time, and ranking takes under 4 ms per document either way.

## Consequences

The whitelist is general-domain. A specialised corpus, such as chemistry or biodiversity, would benefit from adding its own relation properties, such as "found in taxon" (P703) or "parent taxon" (P171), and the `coherence` suite measures the effect of such a change directly.
