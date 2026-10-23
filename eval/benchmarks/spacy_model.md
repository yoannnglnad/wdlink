# Benchmark: spacy_model

**Question.** Which spaCy pipeline should extract the mentions?

Timings measured on: AC power.

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | A2KB P | A2KB R | A2KB F1 | ms/doc (warm) | triples/doc | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ★ en_core_web_sm | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.575 | 0.775 | 0.660 | 519 | 1294 | – | – |
| en_core_web_md | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.586 | 0.803 | 0.678 | 402 | 1294 | +0.0 [+0.0, +0.0] | 1.000 |
| en_core_web_lg | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.565 | 0.775 | 0.654 | 423 | 1294 | +0.0 [+0.0, +0.0] | 1.000 |
| en_core_web_trf | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.608 | 0.815 | 0.696 | 480 | 1294 | +0.0 [+0.0, +0.0] | 1.000 |
