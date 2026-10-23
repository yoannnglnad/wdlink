# ADR-012 — Fetch candidate relations with one SPARQL query, not `wbgetentities`

**Status:** accepted · **Evidence:** [`micro`](../../eval/benchmarks/micro.md) benchmark (cache bypassed, median of 3 runs).

## Context

The graph needs every candidate's outgoing item-valued statements. They can come from two sources:

- the Action API `wbgetentities&props=claims`, in batches of 50 IDs;
- the query service, with one SPARQL query per 50 candidates that keeps truthy (`wdt:`) statements whose value is an item.

## Options measured

The sample is 50 real candidate QIDs from the dev documents.

| Method | Median time | Response size |
|---|---|---|
| **SPARQL, item-valued truthy statements** | **0.75 s** | **0.35 MB** |
| `wbgetentities&props=claims` | 1.50 s | 2.24 MB |

## Decision

Use SPARQL for relations and for types (ADR-013). Use `wbgetentities` only for labels, descriptions and aliases.

## Why

- **SPARQL is 2× faster and sends 6.4× less data.** `wbgetentities` returns every statement with its qualifiers, references and ranks, including string, date and quantity values. The graph does not use any of them.
- **Truthy statements are what a link needs.** `wdt:` keeps the best-ranked values, so deprecated statements are dropped without extra code.
- **Caching per entity still works.** The SPARQL rows are split per candidate before caching (ADR-002).

## Consequences

- The pipeline depends on the query service, which dropped connections several times during this project's runs.
- The client retries dropped connections and 5xx errors with backoff. This was added after a real `RemoteDisconnected` interrupted a benchmark run.
