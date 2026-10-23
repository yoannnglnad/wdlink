# Benchmark: generic_filter

**Question.** Which Zipf-frequency cut-off removes generic one-word nouns?

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | A2KB P | A2KB R | A2KB F1 | Δ vs ★ [95% CI] | p | ΔF1 A2KB vs ★ [95% CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no filter | 0.880 | 0.818 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.485 | 0.832 | 0.613 | +0.0 [+0.0, +0.0] | 1.000 | -12.8 [-16.6, -9.1] |
| Zipf < 2.5 | 0.880 | 0.818 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.734 | 0.751 | 0.743 | +0.0 [+0.0, +0.0] | 1.000 | +0.2 [-2.2, +2.8] |
| Zipf < 3.0 | 0.880 | 0.818 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.728 | 0.775 | 0.751 | +0.0 [+0.0, +0.0] | 1.000 | +1.0 [-0.6, +2.8] |
| ★ Zipf < 3.5 | 0.880 | 0.818 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.695 | 0.792 | 0.741 | – | – | – |
| Zipf < 4.0 | 0.880 | 0.818 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.648 | 0.809 | 0.720 | +0.0 [+0.0, +0.0] | 1.000 | -2.1 [-4.0, +0.2] |
| Zipf < 4.5 | 0.880 | 0.818 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.608 | 0.815 | 0.696 | +0.0 [+0.0, +0.0] | 1.000 | -4.4 [-7.1, -1.7] |
| Zipf < 5.0 | 0.880 | 0.818 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.555 | 0.815 | 0.660 | +0.0 [+0.0, +0.0] | 1.000 | -8.0 [-11.3, -4.8] |
