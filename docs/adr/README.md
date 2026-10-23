# Architecture decision records

Every design choice in `wdlink` is recorded here. Each record either links the benchmark that settled it or says why the choice is not something a benchmark can settle. The protocol is in [ADR-003](003-evaluation-protocol.md):

- benchmarks use the dev split only (52 documents, 191 mentions), scored by 5-fold cross-validation;
- each variant is compared with the default by a paired, document-level bootstrap 95% interval and an exact McNemar test;
- end-to-end variants also get a bootstrap interval on F1;
- a variant replaces the default only when its interval excludes 0; otherwise the simpler or cheaper option is kept, unless evidence from outside dev says otherwise, and the ADR then says so.

Benchmark outputs are in [`eval/benchmarks/`](../../eval/benchmarks/). The two commands:

```bash
uv run wdlink bench <suite>      # one suite, e.g. coherence; "all" runs every suite
uv run wdlink bench micro        # data-access and graph-representation micro-benchmarks
```

| ADR | Decision | Evidence | Changed by its benchmark? |
|---|---|---|---|
| [001](001-runtime-python-uv.md) | Python 3.12, uv, spaCy models as locked URL dependencies | version constraints (no benchmark) | – |
| [002](002-wikidata-access-etiquette.md) | User-Agent, 150 req/min, Retry-After, per-entity cache, offline mode | Wikimedia policy (no benchmark: probing the limit would abuse a public service) | – |
| [003](003-evaluation-protocol.md) | Gold data, D2KB/A2KB, cross-validated benchmarks, held-out test | methodology (no benchmark) | – |
| [004](004-spacy-model.md) | spaCy pipeline for extraction | `spacy_model` | see ADR |
| [005](005-generic-noun-filter.md) | Drop one-word common nouns with Zipf ≥ 3.5 | `generic_filter` | **yes**: 4.5 → 3.5, A2KB F1 +4.6 |
| [006](006-context-window.md) | Sentence ±1 as mention context | `context_window` (inconclusive on short docs) + model limit | no |
| [007](007-search-apis.md) | `wbsearchentities` + REST + human search | `search_apis` + retrieval probe | confirmed (wbs alone −3.7, p = 0.016) |
| [008](008-search-depth.md) | Top 20 per search API | `search_limit` + retrieval probe | no |
| [009](009-query-expansion.md) | Short-mention query expansion off | `query_expansion` + trigger count | **yes**: on → off |
| [010](010-housekeeping-exclusions.md) | Remove housekeeping items and scholarly articles | `exclusions` | no |
| [011](011-prerank-and-candidate-budget.md) | Mixed pre-ranking, 10 candidates per mention | `prerank` | confirmed (search order at K = 5: −4.2, p = 0.039) |
| [012](012-relations-via-sparql.md) | Relations through SPARQL, not `wbgetentities` | `micro` | no |
| [013](013-bounded-type-closure.md) | Bounded type closure P31/P279{0..3} | `micro` | design note corrected (41 s claim not reproduced) |
| [014](014-skos-mapping.md) | SKOS concepts, specialised hierarchy, NIF/ITS mentions | W3C specifications (no benchmark: modelling choice) | – |
| [015](015-graph-runtime-representation.md) | rdflib graph with a triple-scan NetworkX view | `micro` | **yes**: SPARQL view → triple scan (222 → 1.5 ms) |
| [016](016-neighbourhood-properties.md) | Whitelisted properties for neighbourhoods | `coherence` | no |
| [017](017-embedding-model.md) | `bge-small-en-v1.5` | `embedding_model` | no |
| [018](018-graph-facts-in-cards.md) | The 3 graph facts closest to the context | `graph_facts` + dev error analysis | **yes**: all facts → 3 selected |
| [019](019-entity-types.md) | Casing rule instead of spaCy NER labels | `entity_types` | **yes**: NER typing → casing rule (−7.3, p = 0.001) |
| [020](020-graph-coherence.md) | Weighted pairwise coherence, additive bonus | `coherence` + dev error analysis | no |
| [021](021-local-features.md) | Local features and hand-set weights | `local_features` | confirmed (popularity −12.0 without) |
| [022](022-nil-rule.md) | NIL by score threshold only | `nil_rule` | no |
| [023](023-confidence-calibration.md) | Temperature-scaled confidence | `calibration` | confirmed (ECE 0.43 → 0.05) |
| [024](024-no-llm-in-core.md) | No LLM in the core pipeline | scope, reproducibility, clean graph ablation (no benchmark) | – |
| [025](025-output-formats.md) | JSON + Turtle (NIF/ITS) outputs | assignment and standards (no benchmark) | – |
