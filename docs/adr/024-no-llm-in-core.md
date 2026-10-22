# ADR-024 — No large language model in the core pipeline

**Status:** accepted · **Evidence:** scope, reproducibility and measurement design (not benchmarked).

## Context

Recent entity-linking work uses LLMs for re-ranking or generation (ChatEL, LREC-COLING 2024; OneNet, EMNLP 2024; LELA, ISWC 2026). "GraphRAG" also often implies an LLM that reads a retrieved subgraph.

## Decision

The core pipeline uses no LLM:

- the GraphRAG part is retrieval of graph facts plus deterministic graph reasoning (ADR-018, ADR-020);
- an LLM re-ranker is listed as a possible extension, to be called only on low-margin mentions, fed the retrieved facts, and required to cite the triples it relies on.

## Why no benchmark

1. **It would break the comparison the assignment asks for.** The assignment asks whether *graph* context improves selection. An LLM brings its own world knowledge, so adding one would make the graph's effect impossible to isolate in the ablations.
2. **Reproducibility.** The evaluation runs offline and is fully deterministic. LLM outputs change across model versions and need a paid API, so a reviewer could not reproduce the numbers.
3. **Scope.** The assignment asks for a lightweight, modular solution. Every component here runs on a laptop CPU.
4. **Cost of a fair benchmark.** A fair comparison would need several prompts, temperature 0, repeated runs and the same tuning protocol. That is a separate study, not a toggle.

## Consequences

- The pipeline needs no API key and its results can be reproduced exactly.
- The architecture document names the LLM re-ranker as the first extension to evaluate.
