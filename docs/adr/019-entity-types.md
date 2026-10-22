# ADR-019 — Entity types: a casing rule, not spaCy NER labels

**Status:** accepted · **Evidence:** benchmark [`entity_types`](../../eval/benchmarks/entity_types.md); spaCy model comparison in ADR-004.

## Context

The assignment asks to compare candidates on "textual relevance, entity types, and connections". The obvious type signal checks the spaCy NER label of the mention (PERSON, GPE, ORG…) against the candidate's Wikidata classes, i.e. its P31/P279 closure up to depth 3 (ADR-013). This only helps if the NER label is right.

## Options measured

| Variant | CV accuracy | ambiguous | Δ vs casing rule [95% CI] | McNemar p |
|---|---|---|---|---|
| no type signal | 0.874 | 0.803 | +0.0 [+0.0, +0.0] | 1.000 |
| **casing rule only** | **0.874** | **0.803** | – | – |
| spaCy `sm` NER label vs P31/P279 closure | 0.801 | 0.682 | −7.3 [−11.5, −3.6] | 0.001 |
| spaCy `trf` NER label vs P31/P279 closure | 0.864 | 0.773 | −1.0 [−3.8, +1.5] | 0.688 |

The **casing rule** says that a lower-case, non-NER term cannot be a person, song, single, album, film, TV series, video game or literary work.

## Decision

Use the casing rule. Keep NER typing only as an option (`types="ner"`) for the ablation.

## Why

- **NER typing hurts significantly.** With `sm` it costs 7.3 points, and the interval is far from 0. With `trf` it is no better than no typing, and costs a 436 MB model and much slower extraction. The labels are wrong too often on short, ambiguous mentions: `sm` tags "Lincoln" ORG, "Mind" LOC and "Freddie Mercury" ORG; `trf` tags "Higgs boson" LOC. A wrong label actively penalises the right candidate.
- **The casing rule is neutral on dev but kept for two reasons.** It ties exactly with having no type signal: dev contains no lower-case term whose top reading is a work or a person. It is kept because the assignment requires an entity-type comparison, and because it fixes the motivating case at no cost: "radioactivity" is never linked to Kraftwerk's single. It cannot hurt a correct link unless a lower-case mention really names a song or a person, which the annotation guideline excludes.
- **The class list is deliberately narrow.** A first version also excluded "creative work" and "business". That rejected the software library "pandas", which Wikidata classes as a creative work. Lower-case software names are common in research text.

## Consequences

- The type signal is the weakest component of the system. A better one would come from a stronger typed extractor (GLiNER, ADR-004 next steps) or from types inferred from the other mentions' candidates.
- These options were not built. They would need a training-free typer reliable on 1–3-word mentions, and none of the tested pipelines is.
