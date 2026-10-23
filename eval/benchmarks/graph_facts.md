# Benchmark: graph_facts

**Question.** How many verbalised graph facts should the candidate card carry?

Timings measured on: AC power.

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | ms/doc (warm) | triples/doc | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| no facts (label + description) | 0.864 | 0.788 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 327 | 1294 | -1.0 [-2.6, +0.0] | 0.500 |
| 1 closest facts | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 321 | 1294 | +0.0 [+0.0, +0.0] | 1.000 |
| ★ 3 closest facts | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 327 | 1294 | – | – |
| 5 closest facts | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 329 | 1294 | +0.0 [-1.5, +1.4] | 1.000 |
| all facts (up to 24) | 0.869 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 450 | 1294 | -0.5 [-1.6, +0.0] | 1.000 |
