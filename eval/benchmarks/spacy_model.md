# Benchmark: spacy_model

**Question.** Which spaCy pipeline should extract the mentions?

Timings measured on: AC power.

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | A2KB P | A2KB R | A2KB F1 | prepare ms/doc | rank ms/doc | triples/doc | Δ vs ★ [95% CI] | p | ΔF1 A2KB vs ★ [95% CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ★ en_core_web_sm | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.662 | 0.757 | 0.706 | 493 | 3.0 | 1294 | – | – | – |
| en_core_web_md | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.672 | 0.780 | 0.722 | 470 | 16.6 | 1294 | +0.0 [+0.0, +0.0] | 1.000 | +1.6 [-2.3, +5.5] |
| en_core_web_lg | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.652 | 0.757 | 0.701 | 448 | 3.0 | 1294 | +0.0 [+0.0, +0.0] | 1.000 | -0.6 [-4.7, +3.2] |
| en_core_web_trf | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.695 | 0.792 | 0.741 | 435 | 2.8 | 1294 | +0.0 [+0.0, +0.0] | 1.000 | +3.4 [+0.5, +6.7] |
