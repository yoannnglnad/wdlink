# ADR-015 — Graph at runtime: rdflib as the source, NetworkX view by triple scan

**Status:** accepted · **Evidence:** [`micro`](../../eval/benchmarks/micro.md) benchmark (warm data, 6 dev documents).

## Context

The assignment asks for an approach "based on RDF (SKOS)" and suggests NetworkX for the local graph. The ranker needs fast neighbourhood and edge lookups, which NetworkX provides. The question is how the RDF graph and the NetworkX graph relate. There are three options:

- skip RDF;
- build the RDF graph and derive a NetworkX view with a SPARQL query;
- build the RDF graph and derive the same view by scanning its triples.

## Options measured

| Step, per document (about 1,200 triples) | Time |
|---|---|
| build the rdflib SKOS graph | 6.5 ms |
| NetworkX view by SPARQL over the rdflib graph (first design) | 221.8 ms |
| **NetworkX view by scanning the rdflib triples** | **1.5 ms** |
| NetworkX built directly from the statements, no RDF | 0.7 ms |

The micro-benchmark asserts that the two views contain exactly the same edges.

## Decision

Build the rdflib SKOS graph first. The ranker reads a NetworkX view derived from it by a triple scan, never from the raw API data.

## Why

- **RDF stays the single source of truth.** Every edge the ranker uses exists as a triple in the exported Turtle file, so the evidence in the JSON can be checked against the graph.
- **The SPARQL view was the bottleneck.** rdflib's SPARQL engine took 222 ms per document, about 50% on top of the whole preparation (about 450 ms per document, 71% of it embeddings, [`evidence.md`](../../eval/benchmarks/evidence.md)). The equivalent triple scan takes 1.5 ms and gives the same edges. The SPARQL query is kept in the code (`graph.CONCEPT_EDGES`) for documentation and for this benchmark.
- **The RDF cost is negligible.** Building the graph plus the view costs 8 ms per document, against 0.7 ms without RDF. The whole preparation, dominated by embeddings, takes about 450 ms per document.

## Consequences

No graph database is needed. A larger deployment could load the same Turtle files into a triple store and keep the ranker on NetworkX views.
