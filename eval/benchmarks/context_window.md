# Benchmark: context_window

**Question.** How much text around a mention should be compared with the candidates?

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|
| sentence | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | +0.0 [+0.0, +0.0] | 1.000 |
| ★ sentence ±1 | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | – | – |
| sentence ±2 | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | +0.0 [+0.0, +0.0] | 1.000 |
| whole document | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | +0.0 [+0.0, +0.0] | 1.000 |
