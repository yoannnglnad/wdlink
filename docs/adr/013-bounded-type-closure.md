# ADR-013 — Entity types: a bounded P31/P279{0..3} closure, not P279*

**Status:** accepted · **Evidence:** [`micro`](../../eval/benchmarks/micro.md) benchmark.

## Context

The type signal (ADR-019) and the housekeeping filter (ADR-010) need each candidate's classes. These are its `instance of` (P31) values and their superclasses (P279). The complete closure `wdt:P31/wdt:P279*` is the textbook query. Wikidata's upper ontology is deep and tangled, though, so the full closure reaches very general classes.

## Options measured

The sample is 50 dev candidates. The table also checks which of five capital cities end up typed "organization" (Q43229): Paris, Warsaw, London, Berlin, Tokyo.

| Query | Median time | Rows | Cities typed "organization" |
|---|---|---|---|
| **explicit UNION, P31 followed by 0–3 P279** | 0.57 s | 909 | Berlin |
| transitive `wdt:P31/wdt:P279*` | 0.57 s | 3,600 | all five |

## Decision

Use the bounded closure: P31 followed by up to 3 P279 hops, written as an explicit UNION.

## Why

- **The full closure is semantically wrong for this use.** Through long P279 chains, every capital city becomes an "organization". A type check built on it would accept a city for an ORG mention and reject nothing. Depth 3 keeps the classes a human would name, such as city, capital, or commune of France.
- **It returns 4× fewer rows** for the same query time, so the per-entity cache stays smaller.
- **Correction to the design notes.** The design research recorded the transitive query as 41 s against 1.25 s. This was not reproduced: both take 0.57 s here. The choice rests on the quality difference, not on speed.

## Consequences

- An item whose relevant class is more than 3 hops above its P31 is not recognised as belonging to it: the casing rule and the housekeeping filter simply do not fire for it. They never fire wrongly.
- The depth is a constant (`TYPE_DEPTH = 3`, `config.py`). It was not benchmarked against 2 or 4 on accuracy: since NER typing was rejected (ADR-019), types only feed the casing rule and the housekeeping filter, which use classes close to P31.
