# wdlink — text-to-Wikidata entity linking with a GraphRAG re-ranker

`wdlink` finds the meaningful terms in a plain-text document and links each one to a Wikidata item (QID). For every mention, it returns a calibrated confidence, the alternatives it considered, and the evidence behind its choice. It needs no local copy of Wikidata:

1. two search APIs, plus a people search for bare names, propose candidates;
2. a small RDF/SKOS graph is built around them;
3. that graph helps decide which candidate fits the context.

```
$ uv run wdlink link "Marie Curie conducted research on radioactivity in Paris and won the Nobel Prize in Physics."
Mention                 Candidate concept       Wikidata ID  Score  Confidence  Decision
Marie Curie             Marie Curie             Q7186        0.89   0.999       linked
radioactivity           radioactivity           Q11448       0.79   0.970       linked
Paris                   Paris                   Q90          0.73   0.907       linked
Nobel Prize in Physics  Nobel Prize in Physics  Q38104       0.76   0.996       linked
```

The assignment's illustrative table gives Q11452 for radioactivity. Q11452 is *general relativity*; the system returns the correct item, Q11448.

The context also overrides popularity. In "Paris, son of Priam, abducted Helen and started the Trojan War.", Paris is linked to Q167646, the Trojan prince, and Helen to Q164061, Helen of Troy (`examples/paris_troy.json`).

## Results

Thresholds are tuned on dev only; test and KORE50 are held out. Full tables are in [`eval/results/results.md`](eval/results/results.md).

| | first search hit | text-only baseline | **GraphRAG** |
|---|---|---|---|
| test accuracy (97 mentions) | 0.691 | 0.918 | **0.938** |
| test, ambiguous mentions | 0.395 | 0.816 | **0.868** |
| test, end-to-end F1 | – | 0.785 | **0.806** |
| KORE50-DYWC accuracy (141 hard mentions) | 0.227 | 0.518 | **0.567** |
| KORE50-DYWC, end-to-end F1 | – | 0.497 | **0.552** |

## Quick start

```bash
uv sync                                    # Python 3.12; spaCy en_core_web_trf (+ sm) included
uv run wdlink link "text …" --json out.json --ttl graph.ttl
uv run wdlink link --file doc.txt --no-graph          # text-only baseline, for comparison
uv run wdlink link "…" --spacy-model en_core_web_sm  # 15 MB pipeline instead of 501 MB
uv run wdlink eval                         # dev + test (+ KORE50-DYWC if present) → eval/results/
uv run wdlink eval --offline               # re-run from the Wikidata cache only
uv run wdlink bench <suite>|all|micro      # design benchmarks on dev → eval/benchmarks/
uv run pytest                              # 27 tests (2 need the network or a warm cache)
```

The first run downloads the models and fills `.cache/wikidata/`. Later runs are reproducible from that cache.

## Design and its evidence

- [`docs/architecture.md`](docs/architecture.md): the architecture and ranking strategy, the 1–2 page written deliverable.
- [`docs/adr/`](docs/adr/README.md): one decision record per choice, 25 in all, with the benchmark that settled it or the reason it cannot be benchmarked. Six choices changed because of their benchmark: the generic-word cut-off, the query expansion, the graph view, the selection of facts, entity typing, and the spaCy pipeline.
- [`eval/benchmarks/`](eval/benchmarks/): the raw benchmark tables; each suite is a 5-fold cross-validation on dev with paired bootstrap intervals and McNemar tests, and `micro.md` holds the data-access micro-benchmarks.
- [`eval/README.md`](eval/README.md): the annotation guideline and dataset statistics.

## Layout

| Path | Content |
|---|---|
| `src/wdlink/extract.py` | 1. term extraction (spaCy NER and noun chunks, generic-word filter, offsets) |
| `src/wdlink/retrieve.py`, `wikidata.py` | 2. candidate retrieval: search APIs, human search, pre-ranking, cached Wikidata client |
| `src/wdlink/graph.py` | 3. enrichment into the RDF/SKOS graph, NetworkX view, fact verbalisation |
| `src/wdlink/rank.py`, `features.py` | 4. GraphRAG ranking: local score, graph coherence, NIL decision, confidence |
| `src/wdlink/pipeline.py` | end-to-end orchestration and JSON output |
| `src/wdlink/evaluate.py` | 5. evaluation: retrieval recall, D2KB/A2KB, ablations, McNemar |
| `src/wdlink/bench.py`, `microbench.py` | design benchmarks and data-access micro-benchmarks |
| `src/wdlink/config.py` | every constant, weight and threshold (`PipelineConfig`, `RankingConfig`) |

Quality gates run in CI (`.github/workflows/ci.yml`): ruff lint and format, the ty type checker, and the offline unit tests.

## Data note

The KORE50-DYWC annotations have no explicit licence, so the converted file is not committed. `eval/scripts/convert_kore50.py` rebuilds it from the archive documented in `eval/README.md`.
