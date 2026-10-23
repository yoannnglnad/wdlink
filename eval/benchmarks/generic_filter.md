# Benchmark: generic_filter

**Question.** Which Zipf-frequency cut-off removes generic one-word nouns?

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | A2KB P | A2KB R | A2KB F1 | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no filter | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.458 | 0.780 | 0.577 | +0.0 [+0.0, +0.0] | 1.000 |
| Zipf < 2.5 | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.689 | 0.728 | 0.708 | +0.0 [+0.0, +0.0] | 1.000 |
| Zipf < 3.0 | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.681 | 0.740 | 0.709 | +0.0 [+0.0, +0.0] | 1.000 |
| Zipf < 3.5 | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.662 | 0.757 | 0.706 | +0.0 [+0.0, +0.0] | 1.000 |
| Zipf < 4.0 | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.615 | 0.775 | 0.685 | +0.0 [+0.0, +0.0] | 1.000 |
| ★ Zipf < 4.5 | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.575 | 0.775 | 0.660 | – | – |
| Zipf < 5.0 | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | 0.528 | 0.775 | 0.628 | +0.0 [+0.0, +0.0] | 1.000 |
