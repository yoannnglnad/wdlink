# ADR-003 — Evaluation and benchmarking protocol

**Status:** accepted · **Evidence:** methodology (no benchmark: this ADR defines how everything else is measured).

## Context

The assignment asks for two measurements:

- the quality of candidate retrieval and the accuracy of the final linking;
- a comparison of a baseline without graph information against the GraphRAG approach.

Every other design choice in these ADRs also needs evidence. With hand-annotated data, the main risks are tuning on the numbers we report and over-reading differences of one or two mentions.

## Decision

**Data.**

| Split | Role | Size |
|---|---|---|
| `dev` | tuning and all design benchmarks | see `eval/README.md` |
| `test` | held out: never read during development, evaluated once per design | 28 hand-written documents, 97 mentions, 6 NIL |
| `kore50_dywc` | external, hard ambiguity | 141 named-entity mentions |

Every gold QID is verified against the live API. The annotation guideline is in `eval/README.md`.

**What is measured.**

- **Retrieval:** whether the gold item is among the candidates, both before and after the cut to K candidates per mention.
- **Linking with gold spans (D2KB):** accuracy, NIL precision and recall, and accuracy on ambiguous and on isolated mentions.
- **End to end (A2KB):** micro precision, recall and F1 with strong span match (exact span and QID) and weak span match (overlapping span and QID), as in GERBIL.
- **Confidence:** expected calibration error (ECE).

**How design choices are benchmarked (`wdlink bench`).**

- Each variant is scored by **5-fold cross-validation over dev documents**: its NIL threshold θ (and β, and the margin where relevant) is tuned on four folds and applied to the fifth. A variant is never scored on the documents its thresholds were tuned on.
- The difference with the reference variant is reported with a **paired, document-level bootstrap 95% interval** (2,000 resamples) and an **exact McNemar test**. Resampling documents rather than mentions respects the correlation between mentions of the same document.
- **Speed** is the warm-cache preparation time per document, i.e. our own compute, not the network.

**Final evaluation (`wdlink eval`).**

- Each system is tuned once on the whole dev split, with the median of the best plateau when several values tie.
- It is then run on test and KORE50.
- Baseline and GraphRAG are compared with McNemar.

## Why no benchmark

A protocol cannot be benchmarked against itself. It is justified by standard practice: held-out test data, cross-validation for model selection, paired tests for paired predictions, and the GERBIL D2KB/A2KB conventions.

## Consequences

- With a dev split of this size, small differences are noise. A variant is called better only when its bootstrap interval excludes 0.
- When the interval contains 0, the cheaper or simpler option wins, and the ADR says so.
- One exception: when evidence from outside dev, never from test or KORE50, shows the cheaper option is weaker on harder text, the ADR may keep the costlier one and must cite that evidence. ADR-007 and ADR-008 use the design-phase retrieval probe this way.
- Each benchmark ran under the defaults of its day. The suites run before ADR-009 (query expansion on) and before ADR-004 (`sm` extraction) are not re-run: their ★ row is the default at that time, and their accuracy comparisons are unaffected (the `query_expansion` rows are identical). Re-running `wdlink bench` today uses the current defaults, so committed tables are reproducible from their git revision, not from HEAD.
- Timings compare variants within one suite run only. The same default configuration measured 321 to 504 ms/doc across suites run at different times: about ±20% of run-to-run noise.
- In suites other than `calibration`, the confidence fields (`mean_confidence`, `ece`) use the softmax temperature that was the default when the suite ran (0.01, before ADR-023 settled on 0.03). They do not affect any accuracy figure.
