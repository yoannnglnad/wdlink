# Benchmark: embedding_model

**Question.** Which sentence-embedding model should compare contexts and candidates?

Timings measured on: AC power.

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | ms/doc (warm) | triples/doc | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| sentence-transformers/all-MiniLM-L6-v2 (22M) | 0.859 | 0.833 | 0.667 | 1.000 | 0.971 | 0.960 | 8.759 | 271 | 1266 | -1.6 [-4.8, +1.6] | 0.549 |
| ★ BAAI/bge-small-en-v1.5 (33M) | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 461 | 1294 | – | – |
| intfloat/e5-small-v2 (33M) | 0.843 | 0.727 | 0.667 | 1.000 | 0.971 | 0.942 | 8.785 | 566 | 1329 | -3.1 [-6.2, -0.5] | 0.070 |
| ibm-granite/granite-embedding-small-english-r2 (47M) | 0.853 | 0.742 | 0.667 | 1.000 | 0.971 | 0.948 | 8.785 | 806 | 1326 | -2.1 [-4.9, +0.6] | 0.289 |
| BAAI/bge-base-en-v1.5 (109M) | 0.890 | 0.833 | 0.667 | 1.000 | 0.971 | 0.960 | 8.785 | 1277 | 1274 | +1.6 [+0.0, +3.6] | 0.250 |
| sentence-transformers/all-mpnet-base-v2 (109M) | 0.880 | 0.879 | 0.667 | 0.857 | 0.971 | 0.960 | 8.801 | 1375 | 1279 | +0.5 [-1.6, +2.9] | 1.000 |
