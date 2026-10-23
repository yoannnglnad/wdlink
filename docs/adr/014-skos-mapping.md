# ADR-014 — RDF model: SKOS concepts, specialised hierarchy, NIF/ITS mentions

**Status:** accepted · **Evidence:** W3C specifications (no benchmark: a modelling choice, not a quality knob).

## Context

The assignment asks for a "GraphRAG-inspired approach based on RDF (SKOS)". Each document's candidates, their relations and the mentions must therefore live in an RDF graph, using a vocabulary that a SKOS/FAIR reviewer will find correct.

## Decision

| Wikidata | Local graph | Reason |
|---|---|---|
| item | `c:Qx a skos:Concept ; skos:inScheme <doc/scheme> ; skos:exactMatch wd:Qx` | Local concepts, mapped to Wikidata the usual SKOS way. Wikidata's P2888 is declared equivalent to `skos:exactMatch`. `foaf:focus` would be the stricter alternative. |
| label, aliases | `skos:prefLabel`, `skos:altLabel` | The same properties as Wikidata's own RDF export ([RDF dump format](https://www.mediawiki.org/wiki/Wikibase/Indexing/RDF_Dump_Format)) |
| description | `schema:description`, **not** `skos:definition` | Wikidata states that an item is defined by its statements, not its description ([Help:Description](https://www.wikidata.org/wiki/Help:Description)) |
| P279 subclass of | `ex:broaderGeneric` ⊑ `skos:broader` | [SKOS Primer §4.7](https://www.w3.org/TR/skos-primer/#secrelationships); ISO 25964 BTG |
| P31 instance of | `ex:broaderInstantive` ⊑ `skos:broader`, plus the raw `wdt:P31` | ISO 25964 BTI. A bare `skos:broader` would merge instance-of and subclass-of chains under `skos:broaderTransitive`. |
| P361 / P527 | `ex:broaderPartitive` / `ex:narrowerPartitive` | ISO 25964 BTP / NTP |
| other item-valued statements | `wdt:Pxx`, plus `skos:related` only when the pair has no hierarchical link | `skos:related` is disjoint from `skos:broaderTransitive` (integrity condition [S27](https://www.w3.org/TR/skos-reference/#L2422)) |
| P1889 "different from", P460 | not stored | They state that two items are *not* the same thing; storing them as edges would count negative statements as relatedness |
| mention | `nif:Phrase` with `nif:anchorOf`, `nif:beginIndex`, `nif:endIndex`, `nif:referenceContext` | NIF 2.0, the format of GERBIL and of most entity-linking corpora |
| link | `itsrdf:taIdentRef wd:Qx`, `itsrdf:taConfidence`, `itsrdf:taClassRef` | [ITS 2.0 RDF](https://www.w3.org/2005/11/its/rdf), the standard text-analysis annotation |
| run | `prov:Activity` with the configuration | Provenance: which settings produced the links |

## Why no benchmark

The mapping decides what the graph *means*, not which candidate wins: the ranker reads the same edges whichever SKOS sub-property labels them. It is therefore judged against the specifications cited above, not by accuracy.

The only measurable aspect is cost, measured in ADR-015: building the graph takes 6.5 ms per document, or 8 ms with its NetworkX view.

## Consequences

- `--ttl` exports a graph any SKOS or Linked Data tool can load.
- The unit tests check the mapping: instance-of is never a bare `skos:broader`, `skos:related` is never added to a hierarchical pair, and negative statements are never stored.
