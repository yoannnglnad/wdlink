# Micro-benchmarks: data access and graph representation

Sample: 50 candidate QIDs from the first 6 dev documents. Network
timings are medians of 3 cache-bypassing requests from one laptop; they vary with load.

## Fetching relations for 50 candidates

| method | median time | response size |
|---|---|---|
| SPARQL, item-valued truthy statements | 0.75 s | 0.35 MB |
| `wbgetentities&props=claims` | 1.50 s | 2.24 MB |

## Type closure

Cities checked: Paris, Warsaw, London, Berlin, Tokyo; which ones end up typed "organization"?

| query | median time | cities typed organization (Q43229) |
|---|---|---|
| explicit UNION, P31/P279{0..3} | 0.57 s, 909 rows | Q64 |
| transitive `wdt:P31/wdt:P279*` | 0.57 s, 3600 rows | Q64, Q1490, Q84, Q90, Q270 |

## Graph representation, per document (warm data)

| step | time |
|---|---|
| build the rdflib SKOS graph (1200 triples) | 6.5 ms |
| NetworkX view by SPARQL over the rdflib graph | 221.8 ms |
| NetworkX view by scanning the rdflib triples (used) | 1.5 ms |
| NetworkX built directly from the statements, no RDF | 0.7 ms |

The two views are asserted to contain exactly the same edges.
