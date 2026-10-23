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

The **casing rule** says that a lower-case, non-NER term cannot be a person, a musical group, a musical work (song, single, album, release group), a film, a TV series, a video game or a literary work (`config.COMMON_NOUN_INCOMPATIBLE`).

## Decision

Use the casing rule. Keep NER typing only as an option (`types="ner"`) for the ablation.

## Why

- **NER typing hurts with `sm` and does not help on dev with `trf`.** With `sm` it costs 7.3 points, and the interval is far from 0. With `trf` the difference is not significant (−1.0 [−3.8, +1.5]); `trf` became the default extraction model later, for its spans (ADR-004). The labels are wrong too often on short, ambiguous mentions: `sm` tags "Lincoln" ORG, "Mind" LOC and "Freddie Mercury" ORG; `trf` tags "Higgs boson" LOC ([`evidence.md`](../../eval/benchmarks/evidence.md)). A wrong label actively penalises the right candidate.
- **The casing rule is neutral on dev but kept for two reasons.** It ties exactly with having no type signal, changing no dev decision. It is kept because the assignment requires an entity-type comparison, and because it fixes the motivating case at no cost: "radioactivity" is never linked to Kraftwerk's single. It cannot hurt a correct link unless a lower-case mention really names a song or a person, which the annotation guideline excludes.
- **The class list is deliberately narrow.** A first version also excluded "creative work" and "business". That rejected the software library "pandas", which Wikidata classes as a creative work within depth 3 ([`evidence.md`](../../eval/benchmarks/evidence.md)). Lower-case software names are common in research text.

## Consequences

- **Typing is the open question.** With `trf` labels, NER typing does not differ significantly from the casing rule on dev. In the final evaluation it scores higher on the held-out data: 0.948 against 0.938 on test, and 0.631 against 0.567 on KORE50, whose mentions are mostly people and places. It scores lower on dev (0.864 against 0.880).
- **The default does not change.** ADR-003 forbids choosing a configuration on test data, so the casing rule stays. NER typing with `trf` labels is the first variant to re-test once a larger dev split is available. It is one flag (`types="ner"`).
- **The casing rule is not a no-op.** In the final evaluation, dropping all type signal (ablation A4) scores 0.874 against 0.880 on dev and 0.553 against 0.567 on KORE50, and its confidence is worse calibrated on test (ECE 0.168 against 0.069). These are single runs with tuned thresholds, not cross-validated comparisons.
