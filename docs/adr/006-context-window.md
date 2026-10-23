# ADR-006 — Mention context: the sentence plus one sentence on each side

**Status:** accepted · **Evidence:** benchmark [`context_window`](../../eval/benchmarks/context_window.md) (inconclusive by construction), plus a model constraint.

## Context

The text similarity s_txt compares a mention's context with each candidate's card. The context can be:

- the sentence of the mention;
- that sentence with 1 or 2 neighbouring sentences on each side;
- the whole document.

## Options measured

| Context | CV accuracy | Δ [95% CI] |
|---|---|---|
| sentence | 0.874 | +0.0 [+0.0, +0.0] |
| **sentence ±1** | **0.874** | – |
| sentence ±2 | 0.874 | +0.0 [+0.0, +0.0] |
| whole document | 0.874 | +0.0 [+0.0, +0.0] |

All four variants are identical, mention by mention.

## Decision

Keep the sentence ±1.

## Why the benchmark cannot decide

Dev documents are short: 51 of the 52 are a single sentence, and the mean is 22.6 words (`eval/README.md`). The four windows therefore give almost the same text, and the benchmark cannot measure anything here. That is a limit of the data, not evidence that the window does not matter.

## Why ±1 anyway

- **A model limit.** `bge-small-en-v1.5` reads at most 512 tokens and truncates the rest. On a long document, "whole document" would silently cut the context, and the cut might fall before the mention.
- **Too little context loses signal.** A single sentence misses information that often sits in the next sentence ("He was born in Paris. He studied radioactivity…").
- **Too much context dilutes it.** A wide window mixes topics, which hurts mean-pooled sentence embeddings. The same effect was measured for candidate cards in ADR-018.

## Consequences

The choice should be re-benchmarked on long documents, such as abstracts or articles, before using the pipeline on them. The `context_window` suite runs unchanged on any JSONL split passed as `--dev`.
