# wdlink — text-to-Wikidata entity linking with a GraphRAG re-ranker

`wdlink` finds the meaningful terms in a plain-text document and links each one to a Wikidata item (QID). For every mention it returns a confidence, the alternatives it considered, and the evidence behind its choice. It does not need a local copy of Wikidata:

1. A few search APIs find the candidates.
2. A small RDF/SKOS graph is built around them.
3. That graph decides which candidate fits the context.

```
$ uv run wdlink link "Marie Curie conducted research on radioactivity in Paris and won the Nobel Prize in Physics."
Mention                 Candidate concept       Wikidata ID  Score  Confidence  Decision
Marie Curie             Marie Curie             Q7186        0.93   1.000       linked
radioactivity           radioactivity           Q11448       0.81   1.000       linked
Paris                   Paris                   Q90          0.75   1.000       linked
Nobel Prize in Physics  Nobel Prize in Physics  Q38104       0.78   1.000       linked
```

The context overrides popularity. In "Paris, son of Priam, abducted Helen and started the Trojan War.", the system links Paris to Q167646 (the Trojan prince) and Helen to Q164061 (Helen of Troy); see `examples/paris_troy.json`.

| Held-out test split | Accuracy | Accuracy on ambiguous mentions |
|---|---|---|
| First search hit | 0.691 | 0.395 |
| Text-only baseline | 0.918 | 0.816 |
| **GraphRAG** | **0.948** | **0.895** |

On KORE50-DYWC (hard ambiguity), accuracy goes from 0.518 for the baseline to 0.582 with GraphRAG (McNemar p = 0.049). See [`eval/results/results.md`](eval/results/results.md).

The assignment's illustrative table gives Q11452 for radioactivity. Q11452 is *general relativity*; the system returns the correct item, Q11448.

## Quick start

```bash
uv sync                                    # Python 3.12, spaCy en_core_web_sm included
uv run wdlink link "text …" --json out.json --ttl graph.ttl
uv run wdlink link --file doc.txt --no-graph          # text-only baseline, for comparison
uv run wdlink eval                         # dev + test + KORE50-DYWC → eval/results/
uv run wdlink eval --offline               # re-run from the local Wikidata cache only
uv run pytest                              # unit tests (offline) + 2 end-to-end tests
```

The first run downloads the embedding model (`BAAI/bge-small-en-v1.5`, 33M parameters) and fills `.cache/wikidata/`. Later runs are fast and reproducible.

## What is in the output

`--json` writes one entry per mention (see `examples/marie_curie.json`):

- the surface form, character offsets, source (NER or noun chunk) and decision (`linked` or a NIL reason);
- the selected item: QID, URI, label, description, score and confidence;
- the evidence:
  - the feature values (text, name, type, popularity, coherence);
  - the card that was embedded, i.e. the label, description and the retrieved graph facts;
  - the graph links to the other mentions (property, direction, shared neighbours);
- up to five alternatives with their features.

`--ttl` writes the document's RDF graph in Turtle (`examples/marie_curie.ttl`):

- candidates and neighbours as `skos:Concept` mapped to Wikidata with `skos:exactMatch`;
- SKOS hierarchy sub-properties for instance-of, subclass-of and part-of;
- mentions as NIF phrases linked with ITS 2.0 (`itsrdf:taIdentRef`, `itsrdf:taConfidence`);
- the run as a `prov:Activity`.

## Layout

| Path | Content |
|---|---|
| `src/wdlink/extract.py` | 1. term extraction (spaCy NER + noun chunks, generic-word filter, offsets) |
| `src/wdlink/retrieve.py`, `wikidata.py` | 2. candidate retrieval (two search APIs + human search, cached Wikidata client) |
| `src/wdlink/graph.py` | 3. enrichment into the RDF/SKOS graph, NetworkX view, fact verbalisation |
| `src/wdlink/rank.py`, `features.py` | 4. GraphRAG ranking (local score + graph coherence, NIL decision) |
| `src/wdlink/pipeline.py` | end-to-end orchestration and JSON output |
| `src/wdlink/evaluate.py` | 5. evaluation: retrieval recall@k, D2KB / A2KB linking, ablations, McNemar test |
| `src/wdlink/config.py` | every constant, weight and threshold |
| `docs/architecture.md` | architecture and ranking strategy (the written deliverable) |
| `eval/` | gold datasets, annotation guideline, results |

## Design in one paragraph

Retrieval aims for recall and makes no decision. It merges `wbsearchentities` and the Wikibase REST search; on a probe of 19 ambiguous mentions, their union found the right item in its top 20 for all 19, where neither API did alone. Bare names are also searched among humans. Two SPARQL queries per document then bring in types, sitelinks and item-valued statements. These become a local SKOS graph.

The ranker combines a local score with a coherence bonus:

- **Local score.** The context is compared with each candidate's card: its description plus the 3 graph facts closest to the context. Name match, a type rule and popularity are added.
- **Coherence bonus.** A candidate gains when it has direct Wikidata statements, or rare shared neighbours, with the likely readings of the other mentions. Candidates of the same mention never support each other, and weak readings lend little support.

A mention is linked only if its score passes a threshold tuned on dev; otherwise it is NIL. Details and measurements: [`docs/architecture.md`](docs/architecture.md). Results: [`eval/results/results.md`](eval/results/results.md).
