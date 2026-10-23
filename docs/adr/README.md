# Architecture decision records

Every design choice in `wdlink` is recorded here. Each record either links the benchmark that settled it or says why the choice is not something a benchmark can settle. The protocol is in [ADR-003](003-evaluation-protocol.md):

- benchmarks use the dev split only, scored by 5-fold cross-validation;
- each variant is compared with the default using a paired, document-level bootstrap 95% interval and an exact McNemar test;
- a variant replaces the default only when its interval excludes 0; otherwise the simpler or cheaper option is kept.

Benchmark outputs are in [`eval/benchmarks/`](../../eval/benchmarks/). The two main commands:

```bash
uv run wdlink bench <suite>      # one suite, e.g. coherence
uv run wdlink bench micro        # data-access and graph-representation micro-benchmarks
```

| ADR | Decision | Evidence |
|---|---|---|
| [001](001-runtime-python-uv.md) | Python 3.12, uv, spaCy models as locked URL dependencies | version constraints (no benchmark) |
| [002](002-wikidata-access-etiquette.md) | User-Agent, 150 req/min, Retry-After, per-entity cache, offline mode | Wikimedia policy (no benchmark: probing the limit would abuse a public service) |
| [003](003-evaluation-protocol.md) | Gold data, D2KB/A2KB, cross-validated benchmarks, held-out test | methodology (no benchmark) |
| 004 | spaCy pipeline for extraction | `spacy_model` (pending) |
| 005 | Generic-noun filter (Zipf cut-off) | `generic_filter` (pending) |
| 006 | Context window around a mention | `context_window` (pending) |
| 007 | Search APIs and human search | `search_apis` (pending) |
| 008 | Results per search API | `search_limit` (pending) |
| 009 | Short-mention query expansion | `query_expansion` (pending) |
| 010 | Housekeeping and scholarly-article exclusions | `exclusions` (pending) |
| 011 | Pre-ranking and candidate budget per mention | `prerank` (pending) |
| 012 | Relations through SPARQL, not `wbgetentities` | `micro` (pending) |
| 013 | Bounded type closure P31/P279{0..3} | `micro` (pending) |
| [014](014-skos-mapping.md) | SKOS concepts, specialised hierarchy, NIF/ITS mentions | W3C specifications (no benchmark: modelling choice) |
| 015 | rdflib graph with a triple-scan NetworkX view | `micro` (pending) |
| 016 | Whitelisted properties for neighbourhoods | `coherence` (see [ADR-020](020-graph-coherence.md)) |
| 017 | Sentence-embedding model | `embedding_model` (pending) |
| 018 | Query-focused graph facts in the candidate card | `graph_facts` (pending) |
| [019](019-entity-types.md) | Casing rule instead of spaCy NER labels | `entity_types` |
| [020](020-graph-coherence.md) | Weighted pairwise coherence, additive bonus | `coherence` + dev error analysis |
| [021](021-local-features.md) | Local features and hand-set weights | `local_features` |
| [022](022-nil-rule.md) | NIL by score threshold only | `nil_rule` |
| [023](023-confidence-calibration.md) | Temperature-scaled confidence | `calibration` |
| [024](024-no-llm-in-core.md) | No LLM in the core pipeline | scope, reproducibility, clean graph ablation (no benchmark) |
| [025](025-output-formats.md) | JSON + Turtle (NIF/ITS) outputs | assignment and standards (no benchmark) |
