# wdlink — architecture and ranking strategy

`wdlink` links the terms of a plain-text document to Wikidata items (QIDs). Candidate retrieval aims for recall and makes no decision. The decision comes from a small RDF graph built per document with SKOS: each candidate is compared with the text and with the other concepts the text mentions.

```
text ─▶ 1 extraction ─▶ 2 retrieval ─────────▶ 3 enrichment ─────▶ 4 GraphRAG ranking ─▶ 5 JSON + RDF
        spaCy NER +      wbsearchentities       2 SPARQL queries     local score L
        noun chunks,     ∪ REST search          → rdflib SKOS graph  + coherence bonus G
        char offsets     ∪ human search         → NetworkX view      NIL if score < θ
```

All Wikidata calls go through one client. It sends a descriptive User-Agent, stays under 150 requests per minute (the limit is 200) and waits for `Retry-After` on a 429. It caches each entity to disk, so an evaluation re-runs offline with identical results.

## 1. Text processing and term extraction

spaCy `en_core_web_sm` provides the named entities (minus dates and quantities) and the noun chunks that do not overlap an entity.

- Leading determiners and possessives are trimmed.
- A one-word common noun is kept only if it is rare in English (Zipf frequency < 4.5): "radioactivity" passes; "research" and "data" do not.
- Each mention keeps its character offsets and its sentence context.
- A short mention is also searched under the longer mention that contains it ("Curie" → "Marie Curie").

## 2. Candidate retrieval

Each mention is searched with two APIs whose results are merged: `wbsearchentities` (prefix match on labels and aliases) and the Wikibase REST full-text search. On a 19-mention probe, each API missed items the other found, and their union found all 19.

- **Bare names.** A single capitalised word ("Lincoln") is also searched among humans only (`haswbstatement:P31=Q5`). Both APIs rank places first and miss Abraham Lincoln.
- **Terms.** Labels, descriptions and aliases come from `wbgetentities`, which must ask for `languages=en|mul`: Q7186 (Marie Curie) has no `en` label.
- **Exclusions.** Disambiguation pages, categories, name items and scholarly articles are dropped.
- **Pre-ranking.** A cheap score (similarity to the description, name match, search rank) keeps 10 candidates per mention.

## 3. Knowledge-graph enrichment

Two batched SPARQL queries per document fetch the types (P31/P279 up to 3 levels, written as a UNION: 1.3 s instead of 41 s for `P279*`), the sitelinks and every item-valued statement of every candidate. rdflib then builds a local graph that contains:

- the candidates;
- every candidate-to-candidate relation;
- the neighbours reached through about 40 descriptive properties.

| Wikidata | Local RDF graph |
|---|---|
| item | `c:Qx a skos:Concept ; skos:inScheme <doc/scheme> ; skos:exactMatch wd:Qx` |
| label, aliases, description | `skos:prefLabel`, `skos:altLabel`, `schema:description` (not a definition) |
| P279, P31, P361 / P527 | `ex:broaderGeneric`, `ex:broaderInstantive`, `ex:broaderPartitive` / `ex:narrowerPartitive`, all sub-properties of `skos:broader` / `skos:narrower` (SKOS Primer §4.7) |
| other statements | `wdt:Pxx`, plus `skos:related` when the pair is not hierarchical (SKOS S27) |
| P1889 different from, P460 | not stored: negative evidence |
| mention and link | `nif:Phrase` + `itsrdf:taIdentRef` / `itsrdf:taConfidence`; the run is a `prov:Activity` |

The ranker reads a NetworkX view derived from this graph by a SPARQL query.

## 4. GraphRAG-based candidate selection

```
L(m,c) = 0.50·s_txt + 0.20·s_name + 0.15·s_type + 0.15·s_pop
G(m,c) = mean over other mentions m' of  max_{c'∈C(m')}  r(c,c')·p_L(c')
S(m,c) = L + β·G        link if S ≥ θ, else NIL        (β = 0.2, θ = 0.42, tuned on dev)
```

**Retrieval augmentation (s_txt).** Each candidate's neighbourhood is turned into short facts (*Marie Curie — award received: Nobel Prize in Physics*). The 3 facts closest to the mention's context are kept. Together with the label and description, they form the candidate's card, compared with the context using `bge-small-en-v1.5`. Appending every fact diluted well-described items: the Enigma machine dropped from 0.62 to 0.54 similarity.

**Other local features.**
- **s_name:** 1 for an exact label, 0.9 for an exact alias, otherwise a damped fuzzy match on the label.
- **s_type:** a lower-case term cannot be a person, song, film or game. This removes Kraftwerk's single "Radioactivity".
- **s_pop:** the log of the sitelink count.

**Coherence (G).** r(c,c′) is 1 for a direct statement between two candidates; otherwise it is the idf-weighted overlap of their neighbours, so hubs (*human*, *France*) count little. p_L is a softmax of L over the other mention's candidates, so a weak reading lends little support. Candidates of the same mention never support each other, which blocks circular evidence such as *curie* (unit) ↔ *activity* (quantity). G is a bonus: a mention with no related mention keeps S = L.

**Confidence.** The confidence is a softmax over the candidates and a NIL option scored θ. Its temperature (0.01) minimises the negative log-likelihood on dev.

## 5. Output and evaluation

`wdlink link` prints the table from the assignment. It can also write the JSON output and the RDF graph (`--json`, `--ttl`). Per mention, the JSON gives:

- the offsets and the decision;
- the selected QID with its URI, score and confidence;
- the evidence: feature values, the card, and the graph links that supported the choice;
- up to 5 alternatives.

**Data.** Two hand-annotated splits, with every QID checked on the live API:

- dev: 12 documents, 43 mentions, used for tuning only;
- test: 28 documents, 97 mentions, of which 38 ambiguous and 6 NIL.

KORE50-DYWC adds 141 deliberately hard entity mentions. Linking is measured with gold spans (D2KB) and end to end (A2KB, strong span match).

| Test split (held out) | Accuracy | Ambiguous | NIL P / R | A2KB F1 | ECE |
|---|---|---|---|---|---|
| First search hit (API top-1) | 0.691 | 0.395 | – | – | – |
| Baseline: text only, no graph | 0.918 | 0.816 | 1.0 / 1.0 | 0.694 | 0.064 |
| + graph verbalisation only | 0.928 | 0.842 | 1.0 / 1.0 | – | 0.061 |
| + graph coherence only | 0.938 | 0.868 | 1.0 / 1.0 | – | 0.048 |
| **GraphRAG (both)** | **0.948** | **0.895** | 1.0 / 1.0 | **0.724** | 0.051 |
| GraphRAG with spaCy NER types | 0.897 | 0.789 | 1.0 / 1.0 | – | 0.096 |

| KORE50-DYWC | Accuracy | Retrieval recall (all / after pre-rank) |
|---|---|---|
| API top-1 / baseline / **GraphRAG** | 0.227 / 0.518 / **0.582** | 0.837 / 0.709 |

**Findings.**

- **The graph helps, and most where text is ambiguous.** On test, accuracy on ambiguous mentions rises from 0.816 to 0.895. Both graph components contribute, and so does each guard in the coherence score (naive coherence: 0.928).
- **Significance.** On KORE50, GraphRAG fixes 13 baseline errors and introduces 4 (exact McNemar p = 0.049). On test, the result is 3 against 0 (p = 0.25): the split is too small for significance.
- **Rejected design choice.** Matching spaCy NER labels against Wikidata types hurt on every split. The labels are too noisy ("Lincoln" → ORG, even "Higgs boson" → LOC with `trf`), so only the casing rule is kept.
- **Bottleneck on hard text.** On KORE50, the main limit is retrieval: the gold item is among the candidates for only 84% of mentions, and only 71% after the cut to 10 per mention. Confidence, well calibrated on test (0.973 for an accuracy of 0.948), is over-confident on KORE50 (0.88 against 0.58).

**Next steps.**

- Keep more candidates, with a cheaper first-stage scorer.
- Calibrate on harder data.
- Use a stronger NER (GLiNER) for spans only, not for types.
- Add an optional LLM re-ranker, called only on low-margin mentions and fed the retrieved facts.
