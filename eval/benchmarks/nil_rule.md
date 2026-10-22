# Benchmark: nil_rule

**Question.** Should NIL depend on the score only, or also on the top1-top2 margin?

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|
| ★ score threshold θ | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | – | – |
| θ + margin δ | 0.874 | 0.788 | 0.722 | 0.765 | 0.971 | 0.954 | 8.764 | +0.0 [-1.6, +1.5] | 1.000 |
