# ADR-010 — Remove Wikimedia housekeeping items and scholarly articles from the candidates

**Status:** accepted · **Evidence:** benchmark [`exclusions`](../../eval/benchmarks/exclusions.md).

## Context

The search APIs return many items that a plain-text mention never refers to:

- disambiguation pages, categories, list articles and templates;
- name items ("Curie (family name)", "Paris (given name)");
- scholarly articles that share a title with a concept ("Radioactivity", scientific article published in 1958).

Since the 2025 split of the query service, scholarly articles are absent from the main SPARQL graph, so they cannot be enriched at all.

## Options measured

Items are removed in two places: by description before enrichment, and by P31 class after the type query.

| Variant | CV accuracy | ambiguous | candidates/mention | Δ [95% CI] |
|---|---|---|---|---|
| **excluded** | **0.874** | **0.803** | 8.76 | – |
| kept | 0.864 | 0.788 | 9.23 | −1.0 [−2.6, +0.0] |

## Decision

Exclude these items (`exclude_housekeeping=True`).

## Why

- **Keeping them is never better.** It loses 2 mentions on dev. The interval touches 0, so the accuracy difference alone is not conclusive.
- **Exclusion is also the cheaper option.** It means fewer candidates per mention, and fewer terms, types and relations to fetch: every kept article must be fetched, although it has no statements in the main graph. Under ADR-003, the cheaper option wins a tie.
- **The rule is definitional, not tuned.** A disambiguation page or a category is by definition not a referent. Name items are excluded because the mention "Curie" denotes a person or a unit, not the surname as a word.

## Consequences

A mention whose referent really is a paper or a surname cannot be linked to it. The annotation guideline (`eval/README.md`) does not ask for such links, and neither does the assignment.
