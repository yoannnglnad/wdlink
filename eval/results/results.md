# Evaluation results

## dev (12 documents, 40 in-KB mentions)

### Candidate retrieval

| metric | value |
|---|---|
| n_in_kb | 40 |
| retrieval_recall@1 | 0.775 |
| retrieval_recall@5 | 0.900 |
| retrieval_recall@10 | 0.925 |
| retrieval_recall@20 | 0.950 |
| retrieval_recall@40 | 0.975 |
| retrieval_recall@all | 0.975 |
| after_prerank_recall | 0.975 |
| ranked_recall@1 | 0.950 |
| ranked_recall@3 | 0.975 |
| ranked_recall@5 | 0.975 |

### Linking (D2KB, gold mentions)

| system | accuracy | accuracy_in_kb | accuracy_ambiguous | accuracy_unambiguous | accuracy_isolated | accuracy_with_context | nil_recall | nil_precision | mean_confidence | ece |
|---|---|---|---|---|---|---|---|---|---|---|
| API top-1 (wbsearchentities) | 0.791 | 0.775 | 0.429 | 0.962 | – | 0.775 | 1.000 | 1.000 | – | – |
| baseline (text only) | 0.953 | 0.950 | 0.929 | 0.962 | 1.000 | 0.947 | 1.000 | 1.000 | 0.959 | 0.046 |
| A1 graph verbalisation only | 0.953 | 0.950 | 0.929 | 0.962 | 1.000 | 0.947 | 1.000 | 1.000 | 0.973 | 0.045 |
| A2 graph coherence only | 0.977 | 0.975 | 1.000 | 0.962 | 1.000 | 0.974 | 1.000 | 1.000 | 0.970 | 0.048 |
| A3 naive coherence | 0.953 | 0.950 | 0.929 | 0.962 | 1.000 | 0.947 | 1.000 | 1.000 | 0.973 | 0.029 |
| A4 no entity types | 0.953 | 0.950 | 0.929 | 0.962 | 1.000 | 0.947 | 1.000 | 1.000 | 0.986 | 0.033 |
| A5 spaCy NER entity types | 0.860 | 0.850 | 0.643 | 0.962 | 0.000 | 0.895 | 1.000 | 1.000 | 0.849 | 0.047 |
| GraphRAG (full) | 0.953 | 0.950 | 0.929 | 0.962 | 1.000 | 0.947 | 1.000 | 1.000 | 0.982 | 0.039 |

### End to end (A2KB, extraction + linking)

| system | strong P | strong R | strong F1 | weak F1 |
|---|---|---|---|---|
| baseline (text only) | 0.750 | 0.900 | 0.818 | 0.841 |
| GraphRAG (full) | 0.750 | 0.900 | 0.818 | 0.841 |

McNemar baseline vs GraphRAG: only baseline correct = 0, only GraphRAG correct = 0, exact p = 1.0000

## kore50_dywc (50 documents, 141 in-KB mentions)

### Candidate retrieval

| metric | value |
|---|---|
| n_in_kb | 141 |
| retrieval_recall@1 | 0.270 |
| retrieval_recall@5 | 0.489 |
| retrieval_recall@10 | 0.567 |
| retrieval_recall@20 | 0.723 |
| retrieval_recall@40 | 0.837 |
| retrieval_recall@all | 0.837 |
| after_prerank_recall | 0.709 |
| ranked_recall@1 | 0.582 |
| ranked_recall@3 | 0.709 |
| ranked_recall@5 | 0.709 |

### Linking (D2KB, gold mentions)

| system | accuracy | accuracy_in_kb | accuracy_ambiguous | accuracy_unambiguous | accuracy_isolated | accuracy_with_context | nil_recall | nil_precision | mean_confidence | ece |
|---|---|---|---|---|---|---|---|---|---|---|
| API top-1 (wbsearchentities) | 0.227 | 0.227 | 0.227 | – | – | 0.227 | – | – | – | – |
| baseline (text only) | 0.518 | 0.518 | 0.518 | – | 0.500 | 0.518 | – | – | 0.870 | 0.352 |
| A1 graph verbalisation only | 0.532 | 0.532 | 0.532 | – | 0.000 | 0.540 | – | – | 0.870 | 0.339 |
| A2 graph coherence only | 0.560 | 0.560 | 0.560 | – | 0.500 | 0.561 | – | – | 0.886 | 0.326 |
| A3 naive coherence | 0.574 | 0.574 | 0.574 | – | 0.000 | 0.583 | – | – | 0.881 | 0.306 |
| A4 no entity types | 0.582 | 0.582 | 0.582 | – | 0.000 | 0.590 | – | – | 0.900 | 0.319 |
| A5 spaCy NER entity types | 0.525 | 0.525 | 0.525 | – | 0.000 | 0.532 | – | – | 0.619 | 0.095 |
| GraphRAG (full) | 0.582 | 0.582 | 0.582 | – | 0.000 | 0.590 | – | – | 0.883 | 0.311 |

### End to end (A2KB, extraction + linking)

| system | strong P | strong R | strong F1 | weak F1 |
|---|---|---|---|---|
| baseline (text only) | 0.389 | 0.482 | 0.430 | 0.437 |
| GraphRAG (full) | 0.434 | 0.539 | 0.481 | 0.487 |

McNemar baseline vs GraphRAG: only baseline correct = 4, only GraphRAG correct = 13, exact p = 0.0490

## test (28 documents, 91 in-KB mentions)

### Candidate retrieval

| metric | value |
|---|---|
| n_in_kb | 91 |
| retrieval_recall@1 | 0.681 |
| retrieval_recall@5 | 0.879 |
| retrieval_recall@10 | 0.912 |
| retrieval_recall@20 | 0.967 |
| retrieval_recall@40 | 0.978 |
| retrieval_recall@all | 0.978 |
| after_prerank_recall | 0.967 |
| ranked_recall@1 | 0.945 |
| ranked_recall@3 | 0.967 |
| ranked_recall@5 | 0.967 |

### Linking (D2KB, gold mentions)

| system | accuracy | accuracy_in_kb | accuracy_ambiguous | accuracy_unambiguous | accuracy_isolated | accuracy_with_context | nil_recall | nil_precision | mean_confidence | ece |
|---|---|---|---|---|---|---|---|---|---|---|
| API top-1 (wbsearchentities) | 0.691 | 0.670 | 0.395 | 0.868 | – | 0.670 | 1.000 | 0.857 | – | – |
| baseline (text only) | 0.918 | 0.912 | 0.816 | 0.981 | 0.750 | 0.920 | 1.000 | 1.000 | 0.966 | 0.064 |
| A1 graph verbalisation only | 0.928 | 0.923 | 0.842 | 0.981 | 1.000 | 0.920 | 1.000 | 1.000 | 0.971 | 0.061 |
| A2 graph coherence only | 0.938 | 0.934 | 0.868 | 0.981 | 0.750 | 0.943 | 1.000 | 1.000 | 0.986 | 0.048 |
| A3 naive coherence | 0.928 | 0.923 | 0.842 | 0.981 | 1.000 | 0.920 | 1.000 | 1.000 | 0.975 | 0.065 |
| A4 no entity types | 0.938 | 0.934 | 0.868 | 0.981 | 1.000 | 0.931 | 1.000 | 1.000 | 0.976 | 0.044 |
| A5 spaCy NER entity types | 0.897 | 0.890 | 0.789 | 0.962 | 1.000 | 0.885 | 1.000 | 1.000 | 0.814 | 0.096 |
| GraphRAG (full) | 0.948 | 0.945 | 0.895 | 0.981 | 1.000 | 0.943 | 1.000 | 1.000 | 0.973 | 0.051 |

### End to end (A2KB, extraction + linking)

| system | strong P | strong R | strong F1 | weak F1 |
|---|---|---|---|---|
| baseline (text only) | 0.648 | 0.747 | 0.694 | 0.714 |
| GraphRAG (full) | 0.676 | 0.780 | 0.724 | 0.745 |

McNemar baseline vs GraphRAG: only baseline correct = 0, only GraphRAG correct = 3, exact p = 0.2500

## Tuned parameters (dev)

| system | nil_threshold | beta | confidence temperature |
|---|---|---|---|
| baseline (text only) | 0.4 | 0.0 | 0.01 |
| A1 graph verbalisation only | 0.42 | 0.0 | 0.01 |
| A2 graph coherence only | 0.4 | 0.5 | 0.01 |
| A3 naive coherence | 0.42 | 0.3 | 0.01 |
| A4 no entity types | 0.44 | 0.2 | 0.01 |
| A5 spaCy NER entity types | 0.4 | 0.3 | 0.05 |
| GraphRAG (full) | 0.42 | 0.2 | 0.01 |

Wikidata calls: {'cache_hits_terms': 54424, 'cache_hits_types': 5797, 'cache_hits_relations': 5797}
Runtime: 199 s
