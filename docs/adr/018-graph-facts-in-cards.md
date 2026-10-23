# ADR-018 — Retrieval augmentation: the 3 graph facts closest to the context

**Status:** accepted · **Evidence:** benchmark [`graph_facts`](../../eval/benchmarks/graph_facts.md) (timings on AC power), plus the Enigma measurement in [`evidence.md`](../../eval/benchmarks/evidence.md).

## Context

The "retrieval-augmented" half of GraphRAG enriches each candidate's text with facts from the local graph: *Marie Curie — award received: Nobel Prize in Physics*. The question is how many facts to add, and which ones. The first design appended every fact, ordered by QID and capped at 24. On the 12-document dev split this lowered accuracy. A rich, well-described candidate lost similarity because its card became a long list of unrelated facts: the Enigma cipher machine dropped from 0.62 to 0.53 cosine with "Alan Turing helped break the Enigma cipher". With the 3 closest facts it is 0.56 ([`evidence.md`](../../eval/benchmarks/evidence.md)). Mean-pooled sentence embeddings average over everything in the input.

The fix is query-focused: each fact is embedded on its own, and only the facts closest to the mention's context go into the card.

## Options measured

β and θ were re-tuned per fold. Timings are warm and on AC power.

| Card | CV accuracy | Δ vs 3 facts [95% CI] | ms/doc |
|---|---|---|---|
| no facts (label + description) | 0.864 | −1.0 [−2.6, +0.0] | shared* |
| 1 closest fact | 0.874 | +0.0 [+0.0, +0.0] | 321 |
| **3 closest facts** | **0.874** | – | 327 |
| 5 closest facts | 0.874 | +0.0 [−1.5, +1.4] | 329 |
| all facts, up to 24 (initial design) | 0.869 | −0.5 [−1.6, +0.0] | 450 |

\* "No facts" changes only the ranking configuration, so it reuses the default preparation, which embeds every fact. Its time is not a facts-free measurement.

## Decision

Add the **3 facts closest to the context** (`facts_per_card=3`).

## Why

- **Facts help, if they are selected.** A card without facts is 1.0 point worse, and appending all facts is 0.5 point worse and 38% slower. Neither interval excludes 0, but both point the same way as the earlier error analysis.
- **1, 3 and 5 facts form a plateau.** 3 is its middle, the same rule ADR-003 uses for thresholds. In addition, the JSON evidence shows the facts that were used, and 3 facts explain a decision better than 1 does.
- **Speed is unchanged between 1, 3 and 5 facts** (321–329 ms/doc): every fact is embedded once to be scored, whatever the number kept. Only the longer cards of "all facts" cost more (450 ms/doc).
- **Selection by context makes it retrieval, not decoration.** In "Paris, son of Priam, abducted Helen and started the Trojan War" (`examples/paris_troy.json`), the facts retrieved for the Trojan prince are *instance of: mythological Greek character; spouse: Helen of Troy; father: Priam*. These are exactly the relations the sentence talks about.

## Consequences

The card, with its retrieved facts, is part of each mention's evidence in the JSON output (ADR-025). The A1 ablation in the final evaluation ("graph verbalisation only") isolates this component on test and on KORE50.
