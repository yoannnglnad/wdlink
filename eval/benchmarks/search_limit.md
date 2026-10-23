# Benchmark: search_limit

**Question.** How many results should each search API return?

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|
| top 5 per API | 0.859 | 0.788 | 0.667 | 1.000 | 0.948 | 0.948 | 7.010 | -1.6 [-4.4, +1.0] | 0.453 |
| top 10 per API | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.960 | 8.555 | +0.0 [+0.0, +0.0] | 1.000 |
| ★ top 20 per API | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | – | – |
| top 50 per API | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.937 | +0.0 [+0.0, +0.0] | 1.000 |
