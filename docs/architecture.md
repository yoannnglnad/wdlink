# wdlink — architecture and ranking strategy

`wdlink` links the terms of a plain-text document to Wikidata items (QIDs). Candidate retrieval aims for recall and makes no decision. The decision comes from a small RDF graph built per document with SKOS: each candidate is compared with the text and with the other concepts the text mentions. Every choice below is benchmarked or justified in an architecture decision record ([`docs/adr/`](adr/README.md)).

```
text ─▶ 1 extraction ─▶ 2 retrieval ─────────▶ 3 enrichment ──────▶ 4 GraphRAG ranking ─▶ 5 JSON + RDF
        spaCy trf NER +  wbsearchentities       2 SPARQL queries      local score L
        noun chunks,     ∪ REST search          → rdflib SKOS graph   + coherence bonus βG
        char offsets     ∪ human search         → NetworkX view       NIL if S < θ
```

All Wikidata calls go through one client ([ADR-002](adr/002-wikidata-access-etiquette.md)):

- a descriptive User-Agent;
- at most 150 requests per minute;
- retries on 429, 5xx and dropped connections;
- a cache per entity, so evaluations re-run offline with identical results.

## 1. Text processing and term extraction

spaCy `en_core_web_trf` ([ADR-004](adr/004-spacy-model.md)) gives the named entities, minus dates and quantities, and the noun chunks that do not overlap them. `trf` beats `sm` by 3.4 end-to-end F1 points, with an interval excluding 0; `sm` stays as the lightweight option.

Each mention keeps its character offsets and its sentence ±1 as context ([ADR-006](adr/006-context-window.md)). A one-word common noun is kept only if its Zipf frequency is below 3.5 ([ADR-005](adr/005-generic-noun-filter.md)): "radioactivity" passes, "research" does not. Lowering the cut-off from 4.5 to 3.5 raised end-to-end F1 by 4.6 points, an interval excluding 0.

## 2. Candidate retrieval

Each mention is searched with `wbsearchentities` and the Wikibase REST search, top 20 each ([ADR-007](adr/007-search-apis.md), [ADR-008](adr/008-search-depth.md)). Bare capitalised words ("Lincoln", "Curie") are also searched among humans (`haswbstatement:P31=Q5`): both APIs miss Abraham Lincoln for "Lincoln". `wbsearchentities` alone loses 3.7 points (p = 0.016).

- **Terms.** Labels, descriptions and aliases come from `wbgetentities` with `languages=en|mul`: Q7186 has no `en` label.
- **Exclusions.** Disambiguation pages, categories, name items and scholarly articles are dropped ([ADR-010](adr/010-housekeeping-exclusions.md)).
- **Pre-ranking.** A cheap mixed score (similarity to the description, name match, search rank) keeps 10 candidates per mention ([ADR-011](adr/011-prerank-and-candidate-budget.md)). Trusting the search order instead loses 4.2 points at K = 5.

## 3. Knowledge-graph enrichment

Two batched SPARQL queries fetch, for every candidate, its item-valued statements, its types and its sitelinks ([ADR-012](adr/012-relations-via-sparql.md), [ADR-013](adr/013-bounded-type-closure.md)):

- relations: 2× faster and 6× smaller than `wbgetentities`;
- types: P31 followed by at most 3 P279 hops. The full `P279*` closure types every capital city as an "organization".

rdflib builds the SKOS graph ([ADR-014](adr/014-skos-mapping.md)):

| Wikidata | local graph |
|---|---|
| item | `c:Qx a skos:Concept ; skos:inScheme <doc/scheme> ; skos:exactMatch wd:Qx` |
| label, aliases, description | `skos:prefLabel`, `skos:altLabel`, `schema:description` |
| P279, P31, P361 / P527 | `ex:broaderGeneric`, `ex:broaderInstantive`, `ex:broaderPartitive` / `ex:narrowerPartitive` ⊑ `skos:broader` / `skos:narrower` (SKOS Primer §4.7) |
| other statements (whitelist of ~40, plus every candidate-to-candidate link) | `wdt:Pxx`, and `skos:related` unless the pair is hierarchical (S27) |
| P1889, P460 | not stored (negative evidence) |
| mention, link, run | `nif:Phrase`, `itsrdf:taIdentRef`, `itsrdf:taConfidence`, `prov:Activity` |

The ranker reads a NetworkX view derived from the RDF graph by a triple scan. This takes 1.5 ms per document, against 222 ms through rdflib's SPARQL engine ([ADR-015](adr/015-graph-runtime-representation.md)).

## 4. GraphRAG-based candidate selection

```
L(m,c) = 0.50·s_txt + 0.20·s_name + 0.15·s_type + 0.15·s_pop
G(m,c) = mean over other mentions m' of  max_{c'∈C(m')}  r(c,c')·p_L(c')
S(m,c) = L + β·G      link if S ≥ θ, else NIL      β = 0.10, θ = 0.38, τ = 0.03 (tuned on dev)
```

The local score L ([ADR-021](adr/021-local-features.md)):

- **s_txt, the retrieval-augmented part** ([ADR-018](adr/018-graph-facts-in-cards.md)). Each candidate's neighbourhood is verbalised into facts. The 3 facts closest to the context are added to its label and description, and that card is compared with the context by `bge-small-en-v1.5` ([ADR-017](adr/017-embedding-model.md)). Appending every fact diluted well-described items; adding no fact cost 1 point.
- **s_name.** 1 for an exact label match, 0.9 for an exact alias, otherwise a damped fuzzy match on the label.
- **s_pop.** The log of the sitelink count. It is the strongest single feature: −12 points without it.
- **s_type, a casing rule** ([ADR-019](adr/019-entity-types.md)). A lower-case term cannot be a person, song, film or game. Matching spaCy NER labels against Wikidata classes cost 7.3 points with `sm`.

The coherence G ([ADR-020](adr/020-graph-coherence.md), [ADR-016](adr/016-neighbourhood-properties.md)):

- **Relatedness.** r(c,c′) is 1 for a direct statement between the two candidates; otherwise it is the idf-weighted overlap of their neighbourhoods.
- **Weighting.** p_L weights each candidate of another mention by its local plausibility.
- **Guards.** Candidates of the same mention never support each other, which blocks circular evidence between two wrong readings.
- **Bonus only.** G is added, never multiplied, so an isolated mention keeps S = L.
- **Alternatives.** Personalised PageRank ties in accuracy but cannot name the statement behind a bonus. Naive coherence loses 0.5 points.

**NIL and confidence.** NIL depends on the score threshold θ alone; adding a margin rule lowered NIL precision from 1.00 to 0.77 ([ADR-022](adr/022-nil-rule.md)). The confidence is a softmax over the candidates plus a NIL option, temperature-scaled on dev. This cut the expected calibration error from 0.43 to 0.05 ([ADR-023](adr/023-confidence-calibration.md)).

## 5. Output and evaluation

**Output.** `wdlink link` prints the table of the assignment. It also writes ([ADR-025](adr/025-output-formats.md)):

- a JSON file with, per mention: offsets, decision, QID, score, confidence, features, the card with its retrieved facts, the graph links behind the bonus, and alternatives;
- the Turtle graph.

**Protocol** ([ADR-003](adr/003-evaluation-protocol.md)). The data are hand-annotated and QID-verified:

- dev: 52 documents, 191 mentions, including 12 hard NILs, used for tuning and for every benchmark;
- test: 28 documents, 97 mentions, held out;
- KORE50-DYWC: 141 hard entity mentions.

All three are measured with gold spans (D2KB) and end to end (A2KB, strong match).

| | API top-1 | text-only baseline | **GraphRAG** | McNemar (fixed / broken) |
|---|---|---|---|---|
| test, accuracy | 0.691 | 0.918 | **0.938** | 2 / 0, p = 0.50 |
| test, ambiguous mentions | 0.395 | 0.816 | **0.868** | |
| test, end-to-end F1 | – | 0.785 | **0.806** | |
| KORE50, accuracy | 0.227 | 0.518 | **0.567** | 11 / 4, p = 0.12 |
| KORE50, end-to-end F1 | – | 0.461 | **0.513** | |

Test NILs are all detected (precision and recall 1.0), and the test ECE is 0.069. Preparation takes about 0.5 s per document on a laptop, mostly embeddings; ranking takes 3 ms.

**What the evaluation shows.**

- **The graph helps where text is ambiguous.** On test, the gain is +5.2 points on ambiguous mentions. On KORE50, GraphRAG fixes 11 baseline errors and causes 4. Each graph component helps on its own: on KORE50, verbalised facts give 0.532 and coherence 0.539, against 0.518 for the baseline. No single comparison is significant at these sample sizes.
- **Retrieval is the bottleneck on hard text.** On KORE50, the gold item is among the candidates for 84% of mentions, and only 71% after the cut to 10. On test, those figures are 98% and 97%.
- **Typing is the open question.** With `trf` labels, NER typing scores higher on test (0.948) and KORE50 (0.631) but lower on dev. ADR-003 forbids choosing on test, so it is the first variant to re-test with more dev data.

**Next steps.**

- Deeper retrieval: CirrusSearch and K = 20 cost about 30% more compute.
- A larger dev split, to re-test NER typing and learn the weights.
- An LLM re-ranker for low-margin mentions, fed the retrieved facts. It was kept out of the core so that the graph ablation stays clean ([ADR-024](adr/024-no-llm-in-core.md)).
