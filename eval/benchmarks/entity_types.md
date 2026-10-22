# Benchmark: entity_types

**Question.** How should entity types enter the local score?

Dev split, 52 documents, 191 gold mentions, 5-fold cross-validation (thresholds tuned on the other folds). Δ = accuracy difference with the reference (★), in points, with its 95% paired document-level bootstrap interval; p = exact McNemar test.

| variant | CV accuracy | ambiguous | NIL recall | NIL precision | gold retrieved | gold kept | cands/mention | Δ vs ★ [95% CI] | p |
|---|---|---|---|---|---|---|---|---|---|
| no type signal | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | +0.0 [+0.0, +0.0] | 1.000 |
| ★ casing rule only | 0.874 | 0.803 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | – | – |
| spaCy sm NER labels | 0.801 | 0.682 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | -7.3 [-11.5, -3.6] | 0.001 |
| spaCy trf NER labels | 0.864 | 0.773 | 0.667 | 1.000 | 0.971 | 0.954 | 8.764 | -1.0 [-3.8, +1.5] | 0.688 |
