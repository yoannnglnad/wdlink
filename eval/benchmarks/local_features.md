# Benchmark: local_features

**Question.** Which local features and weights should form L?

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|
| ★ default (0.50 / 0.20 / 0.15 / 0.15) | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | – | – |
| no popularity | 0.754 | 0.712 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | -12.0 [-17.0, -7.3] | 0.000 |
| no name match | 0.843 | 0.833 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | -3.1 [-6.3, +0.0] | 0.146 |
| text weight 0.70 | 0.890 | 0.848 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | +1.6 [+0.0, +3.5] | 0.250 |
| text weight 0.30 | 0.864 | 0.773 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | -1.0 [-3.3, +1.0] | 0.625 |
| popularity weight 0.30 | 0.848 | 0.773 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | -2.6 [-5.1, -0.5] | 0.125 |
| fuzzy name match on aliases too | 0.843 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | -3.1 [-6.0, -0.5] | 0.070 |
