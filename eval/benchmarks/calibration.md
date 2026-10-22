# Benchmark: calibration

**Question.** Is temperature scaling needed for the reported confidence?

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | mean confidence | ECE | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| fixed softmax temperature 0.1 | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.452 | 0.425 | +0.0 [+0.0, +0.0] | 1.000 |
| ★ temperature scaling (min NLL) | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.851 | 0.051 | – | – |
