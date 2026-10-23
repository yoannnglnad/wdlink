# Benchmark: prerank

**Question.** How many candidates per mention should enter the graph, ranked how?

Timings measured on: AC power.

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | ms/doc (warm) | triples/doc | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| top 5, mixed | 0.869 | 0.788 | 0.667 | 1.000 | 0.971 | 0.942 | 4.461 | 326 | 855 | -0.5 [-1.6, +0.0] | 1.000 |
| ★ top 10, mixed | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 382 | 1294 | – | – |
| top 20, mixed | 0.880 | 0.803 | 0.667 | 1.000 | 0.971 | 0.965 | 16.429 | 501 | 2253 | +0.5 [+0.0, +1.6] | 1.000 |
| top 30, mixed | 0.880 | 0.803 | 0.667 | 1.000 | 0.971 | 0.971 | 21.743 | 689 | 3189 | +0.5 [+0.0, +1.6] | 1.000 |
| top 5, search_rank | 0.832 | 0.712 | 0.667 | 1.000 | 0.971 | 0.896 | 4.508 | 234 | 1129 | -4.2 [-7.2, -1.1] | 0.039 |
| top 10, search_rank | 0.874 | 0.788 | 0.667 | 1.000 | 0.971 | 0.954 | 8.806 | 597 | 1757 | +0.0 [-2.2, +2.0] | 1.000 |
| top 20, search_rank | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.971 | 16.429 | 889 | 2662 | +0.0 [+0.0, +0.0] | 1.000 |
| top 30, search_rank | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.971 | 21.749 | 914 | 3309 | +0.0 [+0.0, +0.0] | 1.000 |
