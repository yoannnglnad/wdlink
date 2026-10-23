# Benchmark: exclusions

**Question.** Should Wikimedia housekeeping items and scholarly articles be removed?

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|
| ★ excluded | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | – | – |
| kept | 0.864 | 0.788 | 0.667 | 1.000 | 0.971 | 0.954 | 9.225 | -1.0 [-2.6, +0.0] | 0.500 |
