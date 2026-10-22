# wdlink — architecture and ranking strategy

`wdlink` turns plain text into links to Wikidata items (QIDs). It is a five-stage Python pipeline. Retrieval is tuned for recall and makes no decision. The decision comes from a small RDF graph built per document with SKOS: each candidate is compared with the text, and with the other concepts the text mentions.

```
text ─▶ 1 extraction ─▶ 2 retrieval ─▶ pre-rank ─▶ 3 enrichment ─▶ 4 GraphRAG ranking ─▶ 5 JSON + RDF
        spaCy NER +      wbsearchentities         SPARQL (WDQS)    local L + coherence G
        noun chunks      ∪ REST search            → rdflib SKOS     NIL if evidence is weak
        (char offsets)   + wbgetentities          → NetworkX view
```

Every Wikidata call goes through one client. It sends a descriptive User-Agent and stays under 150 requests per minute (the limit is 200). On a 429 it waits for `Retry-After`. It caches each entity to disk, so evaluations re-run offline (`--offline`) and give the same results every time.

## 1. Text processing and term extraction (`extract.py`)

spaCy `en_core_web_sm` provides the named entities, minus dates and quantities, and the noun chunks that do not overlap an entity.

- **Trimming.** Leading determiners, possessives and superlatives are removed: "the Nobel Prize in Physics" becomes "Nobel Prize in Physics".
- **Generic words.** A one-word common noun is kept only if it is rare in English (Zipf frequency < 4.5, `wordfreq`). "radioactivity" (2.9) passes; "research" (5.4) and "data" (5.3) are dropped. Compounds and proper nouns are always kept.
- **Offsets.** Each mention keeps its character offsets (`text[start:end] == mention`), its NER label, and a context window (the sentence and its neighbours).
- **Short mentions.** A short mention inherits the longer mention that contains it elsewhere in the document: "Curie" is also searched as "Marie Curie". Wikidata search does not return Q7186 in its top 20 for "Curie".

## 2. Candidate retrieval (`retrieve.py`, `wikidata.py`)

Each query goes to two search APIs, and the results are merged.

- **Why two APIs.** On 19 ambiguous mentions, `wbsearchentities` (prefix match on labels and aliases) found the right item in its top 1 for 7 mentions, and the REST full-text search for 12. Together, their top 20 contained the right item for all 19.
- **Terms.** `wbgetentities` returns labels, descriptions and aliases in batches of 50. It must ask for `languages=en|mul`, because many English labels now live only under `mul` (Q7186 and Q42 have no `en` label).
- **Exclusions.** Wikimedia housekeeping items (disambiguation pages, categories, lists, family and given names) are removed. So are scholarly articles, which have been absent from the main SPARQL graph since 2025.
- **Pre-ranking.** A cheap score keeps 10 candidates per mention: context/description similarity, name match and search rank. Recall is measured both before and after this cut.

## 3. Knowledge-graph enrichment (`graph.py`)

Two batched SPARQL queries per document fetch the rest:

- the types (`P31/P279{0..3}`, written as an explicit UNION: 1.3 s, against 41 s and wrong results for `P279*`) and the sitelink counts;
- every outgoing truthy statement whose value is an item.

From these, rdflib builds a local SKOS graph with three kinds of nodes:

- the candidates;
- every candidate-to-candidate relation (any property);
- the neighbours reached through about 40 descriptive properties (field of work, award, location, part of, author…).

| Wikidata | local RDF graph |
|---|---|
| candidate / neighbour item | `c:Qx a skos:Concept ; skos:inScheme <doc/scheme> ; skos:exactMatch wd:Qx` |
| label / aliases / description | `skos:prefLabel` / `skos:altLabel` / `schema:description` (a Wikidata description is not a definition) |
| P279 subclass of | `ex:broaderGeneric` ⊑ `skos:broader` |
| P31 instance of | `ex:broaderInstantive` ⊑ `skos:broader` |
| P361 / P527 | `ex:broaderPartitive` ⊑ `skos:broader` / `ex:narrowerPartitive` ⊑ `skos:narrower` |
| any other item-valued statement | `wdt:Pxx`, plus `skos:related` when the pair is not hierarchical (SKOS S27) |
| P1889 different from, P460 | never stored: they are negative evidence |
| mention, link | `nif:Phrase` (anchorOf, begin/endIndex) with `itsrdf:taIdentRef`, `itsrdf:taConfidence`; run as `prov:Activity` |

The hierarchical sub-properties follow SKOS Primer §4.7. Mapping P31 to a bare `skos:broader` would merge instance-of and subclass-of chains under `skos:broaderTransitive`. The ranker does not read rdflib directly: a SPARQL query over the local graph produces its NetworkX view. The graph can be exported as Turtle (`--ttl`).

## 4. GraphRAG-based candidate selection (`rank.py`)

Here "GraphRAG" means two things, measured separately in the evaluation:

- **Retrieval augmentation.** Each candidate gets a "card": its label and description, followed by its verbalised neighbourhood read from the graph. Example: *Marie Curie, Polish-born French physicist… award received: Nobel Prize in Physics; field of work: radioactivity…*. The card is embedded with `BAAI/bge-small-en-v1.5`.
- **Graph reasoning.** A coherence score rewards candidates related to the likely readings of the other mentions.

For a mention *m* and a candidate *c*:

```
L(m,c) = 0.50·s_txt + 0.20·s_name + 0.15·s_type + 0.15·s_pop
G(m,c) = mean over other mentions m' of  max_{c'∈C(m')}  r(c,c') · p_L(c')
S(m,c) = L(m,c) + β·G(m,c)
```

The local terms:

- **s_txt** is the cosine similarity between the context and the card.
- **s_name** is 1 for an exact label match, 0.9 for an exact alias, and a damped fuzzy score otherwise.
- **s_type** compares the NER label with the P31/P279 closure: 1 compatible, 0.5 unknown, 0 incompatible. A lower-case common noun excludes people, creative works and companies; this alone removes the Kraftwerk song "Radioactivity".
- **s_pop** is the log of the sitelink count.

The coherence terms:

- **Relatedness.** r(c,c′) is 1 for a direct statement between the two candidates. Otherwise it is the idf-weighted overlap of their neighbourhoods, so hubs such as *human* or *France* barely count.
- **Weighting.** p_L(c′) is a softmax of the local score L over the other mention's candidates.
- **Guards.** The max per mention, the p_L weighting, and ignoring candidates of the same mention prevent circular evidence. For example, *curie* (unit) and *activity* (quantity) are two wrong readings linked to each other, and they cannot lift each other.

When no relation exists, G = 0 and S = L, so coherence is a bonus that never penalises a mention alone in its document.

**Decision.** The top candidate is selected if S ≥ θ. Otherwise the mention is NIL and the ranking is still returned. The confidence is the softmax probability of the choice against the other candidates and a NIL option scored θ. θ and β are tuned on the dev split only.

## 5. Output and evaluation

`wdlink link "<text>" --json out.json --ttl graph.ttl` prints the table from the assignment. It writes, per mention:

- the offsets and the decision;
- the selected QID with its URI, score and confidence;
- the evidence: features, the card, and the graph links that supported the choice (relation, direction, shared neighbours);
- up to 5 alternatives with their features.

See `examples/`.

`wdlink eval` measures, on hand-annotated dev and test splits plus KORE50-DYWC (`eval/README.md`):

- **retrieval:** recall@k before and after pre-ranking;
- **linking (D2KB, gold spans):** accuracy, split into ambiguous / unambiguous, isolated / with context, and NIL precision / recall;
- **end to end (A2KB):** strong and weak-match F1.

Systems compared:

- first search hit (API top-1);
- text-only baseline (no graph, β = 0);
- verbalisation only;
- coherence only;
- naive coherence (no idf, no p_L weighting);
- full GraphRAG.

An exact McNemar test checks whether the difference between baseline and GraphRAG is significant.

RESULTS_PLACEHOLDER

## Limitations and next steps

- spaCy `sm` NER labels are noisy ("Freddie Mercury" → ORG), which weakens s_type; `en_core_web_trf` or GLiNER would help, at a higher cost.
- A first name or surname alone (e.g. "Mercury" for Freddie Mercury) can fall outside both top-20 lists when the document has no fuller mention to expand from.
- Weights are hand-set and only θ and β are tuned, because the dev set is too small to learn more without overfitting. A larger gold set (KORE50, ZELDA) would allow learning to rank.
- An optional LLM re-ranker could be called only on low-margin mentions, fed the verbalised subgraph and asked to cite the triples it uses. It was left out to keep the core deterministic and the graph ablation clean.
