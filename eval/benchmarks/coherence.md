# Benchmark: coherence

**Question.** How should graph connections to the other mentions be scored?

Timings measured on: AC power.

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | prepare ms/doc | rank ms/doc | triples/doc | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no coherence | 0.869 | 0.788 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 504 | 0.6 | 1294 | -0.5 [-1.7, +0.0] | 1.000 |
| naive (Jaccard, unweighted mean) | 0.869 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 504 | 7.3 | 1294 | -0.5 [-1.6, +0.0] | 1.000 |
| ★ weighted pairwise (idf, p_L, max per mention) | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 504 | 2.9 | 1294 | – | – |
| personalised PageRank | 0.874 | 0.833 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 504 | 5.6 | 1294 | +0.0 [-2.5, +2.6] | 1.000 |
| weighted, all properties as neighbours | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 489 | 3.6 | 2837 | +0.0 [+0.0, +0.0] | 1.000 |
| weighted, convex fusion (1-β)L + βG | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 504 | 2.7 | 1294 | +0.0 [+0.0, +0.0] | 1.000 |
