# ADR-017 — Sentence embeddings: `BAAI/bge-small-en-v1.5`

**Status:** accepted · **Evidence:** benchmark [`embedding_model`](../../eval/benchmarks/embedding_model.md) (timings on AC power).

## Context

Embeddings drive three steps:

- s_txt, the similarity between a mention's context and each candidate's card;
- the pre-ranking;
- the choice of the graph facts closest to the context.

The assignment asks for a lightweight solution, and embeddings are the largest compute cost per document. Candidates must be open, small enough for a laptop CPU or GPU, and usable without accepting a gated licence.

## Options measured

The NIL threshold and β were re-tuned per fold for each model. Timings are warm, on the same machine, on AC power.

| Model (parameters) | CV accuracy | ambiguous | ms/doc | Δ vs bge-small [95% CI] | p |
|---|---|---|---|---|---|
| all-MiniLM-L6-v2 (22M) | 0.859 | 0.833 | 271 | −1.6 [−4.8, +1.6] | 0.549 |
| **bge-small-en-v1.5 (33M)** | **0.874** | 0.803 | 461 | – | – |
| e5-small-v2 (33M) | 0.843 | 0.727 | 566 | −3.1 [−6.2, −0.5] | 0.070 |
| granite-embedding-small-english-r2 (47M) | 0.853 | 0.742 | 806 | −2.1 [−4.9, +0.6] | 0.289 |
| bge-base-en-v1.5 (109M) | 0.890 | 0.833 | 1,277 | +1.6 [+0.0, +3.6] | 0.250 |
| all-mpnet-base-v2 (109M) | 0.880 | 0.879 | 1,375 | +0.5 [−1.6, +2.9] | 1.000 |

## Decision

Keep `BAAI/bge-small-en-v1.5` (MIT licence, 384 dimensions).

## Why

- **It is the best small model.** It beats the other three models of 22–47M parameters by 1.6 to 3.1 points.
- **The base models do not clearly beat it.** bge-base gains 1.6 points, but its interval touches 0, and it is 2.8× slower. Under ADR-003, the cheaper model wins.
- **MiniLM is the fast fallback.** It is 1.7× faster for −1.6 points, a difference that is not significant. It is the right choice when latency matters more than the last points.
- **Caveat on e5-small-v2.** e5 expects the prefixes `query:` and `passage:`, and the benchmark encodes every model the same way, without them. Its score is therefore a lower bound and should not be read as a verdict on e5.
- **Not benchmarked:**
  - EmbeddingGemma requires accepting a gated licence on Hugging Face, so the install would not be reproducible.
  - jina-embeddings-v3 is licensed CC BY-NC.
  - Larger 7B-class models do not fit the "lightweight" requirement.

## Consequences

- The model is configurable (`PipelineConfig.embedding_model`), and any sentence-transformers model can be benchmarked with the same command.
- mpnet-base scores best on ambiguous mentions (0.879) but not overall. With more dev data, it is worth re-testing it.
