# Benchmark: search_apis

**Question.** Which Wikidata search APIs should produce candidates?

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|
| wbs | 0.838 | 0.758 | 0.667 | 1.000 | 0.919 | 0.919 | 8.168 | -3.7 [-6.3, -1.5] | 0.016 |
| wbs + humans | 0.864 | 0.803 | 0.667 | 1.000 | 0.942 | 0.936 | 8.209 | -1.0 [-3.2, +0.6] | 0.625 |
| rest | 0.869 | 0.773 | 0.667 | 1.000 | 0.948 | 0.942 | 8.225 | -0.5 [-2.3, +1.1] | 1.000 |
| rest + humans | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.288 | +0.0 [+0.0, +0.0] | 1.000 |
| cirrus | 0.885 | 0.818 | 0.611 | 1.000 | 0.977 | 0.971 | 9 | +1.0 [-1.6, +3.6] | 0.688 |
| cirrus + humans | 0.885 | 0.833 | 0.611 | 1.000 | 0.983 | 0.971 | 9 | +1.0 [-1.0, +3.1] | 0.625 |
| wbs+rest | 0.864 | 0.773 | 0.667 | 1.000 | 0.954 | 0.936 | 8.749 | -1.0 [-2.7, +0.0] | 0.500 |
| ★ wbs+rest + humans | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | – | – |
| wbs+rest+cirrus | 0.874 | 0.803 | 0.611 | 1.000 | 0.988 | 0.954 | 8.979 | +0.0 [-2.1, +2.2] | 1.000 |
| wbs+rest+cirrus + humans | 0.880 | 0.818 | 0.611 | 1.000 | 0.988 | 0.965 | 8.984 | +0.5 [-1.1, +2.4] | 1.000 |
