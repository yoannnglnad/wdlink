# ADR-013 — Entity types: a bounded P31/P279{0..3} closure, not P279*

**Status:** accepted · **Evidence:** [`micro`](../../eval/benchmarks/micro.md) benchmark.

## Context

The type signal (ADR-019) needs each candidate's classes. The housekeeping filter (ADR-010) only looks at direct P31 values, so it does not depend on the closure. These are its `instance of` (P31) values and their superclasses (P279). The complete closure `wdt:P31/wdt:P279*` is the textbook query. Wikidata's upper ontology is deep and tangled, though, so the full closure reaches very general classes.

## Options measured

The sample is 50 dev candidates. The table also checks which of five capital cities end up typed "organization" (Q43229): Paris, Warsaw, London, Berlin, Tokyo.

| Query | Median time | Rows | Cities typed "organization" |
|---|---|---|---|
| **explicit UNION, P31 followed by 0–3 P279** | 0.57 s | 909 | Berlin |
| transitive `wdt:P31/wdt:P279*` | 0.57 s | 3,600 | all five |

## Decision

Use the bounded closure: P31 followed by up to 3 P279 hops, written as an explicit UNION.

## Why

- **The full closure reaches classes that make type checks meaningless.** Through long P279 chains, all five capitals tested become an "organization", so a type check built on it would accept a city for an ORG mention. Depth 3 does not remove generic classes: Paris still gets 75 classes, from "city" and "commune of France" to "government organization" and "datapoint" ([`evidence.md`](../../eval/benchmarks/evidence.md)). But it reaches "organization" for one capital out of five instead of all five.
- **It returns 4× fewer rows** for the same query time, so the per-entity cache stays smaller.
- **Correction to the design notes.** The design research recorded the transitive query as 41 s against 1.25 s. This was not reproduced: both take 0.57 s here. The choice rests on the quality difference, not on speed.

## Consequences

- An item whose relevant class is more than 3 hops above its P31 is not recognised as belonging to it: the casing rule simply does not fire for it, and never fires wrongly.
- The depth is a constant (`TYPE_DEPTH = 3`, `config.py`). It was not benchmarked against 2 or 4 on accuracy: since NER typing was rejected (ADR-019), the closure only feeds the casing rule. Its classes (human, song, single, film…) are what a candidate's P31 names directly or through a short chain: Kraftwerk's "Radioactivity" is a single, and a single is a musical work.
