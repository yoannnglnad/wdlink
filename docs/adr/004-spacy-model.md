# ADR-004 — Extraction: spaCy `en_core_web_trf`, with `en_core_web_sm` as the lightweight option

**Status:** accepted (supersedes the initial `en_core_web_sm`) · **Evidence:** benchmark [`spacy_model`](../../eval/benchmarks/spacy_model.md), end to end with bootstrap intervals; timings on AC power.

## Context

spaCy provides the named entities and noun chunks from which mentions are built (stage 1). The NER label is no longer used for typing (ADR-019), but the extraction model still decides:

- which spans become mentions;
- where they start and end;
- whether a lower-case term counts as a common noun.

The assignment suggests spaCy and asks for a lightweight solution. The four English pipelines range from 15 MB to 478 MB.

## Options measured

The generic-word filter is set at 3.5 (ADR-005). Linking with gold spans is identical for all four models, so they differ only end to end.

| Pipeline | Size on disk | A2KB precision | A2KB recall | A2KB F1 | ΔF1 vs sm [95% CI] | prepare ms/doc |
|---|---|---|---|---|---|---|
| en_core_web_sm | 15 MB | 0.662 | 0.757 | 0.706 | – | 493 |
| en_core_web_md | 55 MB | 0.672 | 0.780 | 0.722 | +1.6 [−2.3, +5.5] | 470 |
| en_core_web_lg | 426 MB | 0.652 | 0.757 | 0.701 | −0.6 [−4.7, +3.2] | 448 |
| **en_core_web_trf** | 478 MB | **0.695** | **0.792** | **0.741** | **+3.4 [+0.5, +6.7]** | 435 |

## Decision

Make `en_core_web_trf` the default. Keep `en_core_web_sm` installed and selectable (`--spacy-model en_core_web_sm`).

## Why

- **`trf` is the only significant improvement.** Its F1 interval excludes 0, which under ADR-003 is the condition for replacing the default. It improves precision and recall at the same time, finding and delimiting entity spans better, as expected from its NER score (89.9 F1 against 84.3 for `sm` on OntoNotes).
- **It costs disk space, not time, in this pipeline.** Preparation time is the same, between 435 and 493 ms per document, because the sentence embeddings dominate. torch is already a dependency of sentence-transformers, so `trf` adds about 460 MB of weights and the small `spacy-curated-transformers` package, but no new runtime.
- **The larger CNN models are not worth it.** `md` and `lg` are not significantly better than `sm`.
- **`sm` remains the lightweight option** (15 MB) for environments where the extra download matters. It loses 3.4 F1 points end to end.

## Consequences

- `uv sync` downloads both pipelines. `md` and `lg` stay in an optional extra (`--extra models`), used only by this benchmark.
- The other benchmarks were run with `sm` before this decision, and were not re-run with `trf`. With gold spans, the extraction model only affects sentence boundaries (the context) and the common-noun flag. The final evaluation is run with `trf`.
