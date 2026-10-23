# Evaluation results

## dev (52 documents, 173 in-KB mentions)

### Candidate retrieval

| metric | value |
|---|---|
| n_in_kb | 173 |
| retrieval_recall@1 | 0.699 |
| retrieval_recall@5 | 0.850 |
| retrieval_recall@10 | 0.913 |
| retrieval_recall@20 | 0.936 |
| retrieval_recall@40 | 0.971 |
| retrieval_recall@all | 0.971 |
| after_prerank_recall | 0.954 |
| ranked_recall@1 | 0.902 |
| ranked_recall@3 | 0.942 |
| ranked_recall@5 | 0.954 |

### Linking (D2KB, gold mentions)

| system | accuracy | accuracy_in_kb | accuracy_ambiguous | accuracy_unambiguous | accuracy_isolated | accuracy_with_context | nil_recall | nil_precision | mean_confidence | ece |
|---|---|---|---|---|---|---|---|---|---|---|
| API top-1 (wbsearchentities) | 0.691 | 0.694 | 0.288 | 0.944 | – | 0.694 | 0.667 | 1.000 | – | – |
| baseline (text only) | 0.864 | 0.884 | 0.773 | 0.953 | 1.000 | 0.880 | 0.667 | 1.000 | 0.824 | 0.063 |
| A1 graph verbalisation only | 0.869 | 0.890 | 0.788 | 0.953 | 1.000 | 0.886 | 0.667 | 1.000 | 0.829 | 0.068 |
| A2 graph coherence only | 0.869 | 0.890 | 0.788 | 0.953 | 1.000 | 0.886 | 0.667 | 1.000 | 0.856 | 0.047 |
| A3 naive coherence | 0.874 | 0.896 | 0.803 | 0.953 | 1.000 | 0.892 | 0.667 | 1.000 | 0.838 | 0.062 |
| A4 no entity types | 0.874 | 0.896 | 0.803 | 0.953 | 1.000 | 0.892 | 0.667 | 1.000 | 0.774 | 0.101 |
| A5 spaCy NER entity types | 0.812 | 0.827 | 0.712 | 0.897 | 0.571 | 0.837 | 0.667 | 1.000 | 0.809 | 0.037 |
| GraphRAG (full) | 0.880 | 0.902 | 0.818 | 0.953 | 1.000 | 0.898 | 0.667 | 1.000 | 0.849 | 0.059 |

### End to end (A2KB, extraction + linking)

| system | strong P | strong R | strong F1 | weak F1 |
|---|---|---|---|---|
| baseline (text only) | 0.657 | 0.751 | 0.701 | 0.717 |
| GraphRAG (full) | 0.662 | 0.757 | 0.706 | 0.728 |

McNemar baseline vs GraphRAG: only baseline correct = 0, only GraphRAG correct = 3, exact p = 0.2500

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
| ranked_recall@1 | 0.567 |
| ranked_recall@3 | 0.702 |
| ranked_recall@5 | 0.709 |

### Linking (D2KB, gold mentions)

| system | accuracy | accuracy_in_kb | accuracy_ambiguous | accuracy_unambiguous | accuracy_isolated | accuracy_with_context | nil_recall | nil_precision | mean_confidence | ece |
|---|---|---|---|---|---|---|---|---|---|---|
| API top-1 (wbsearchentities) | 0.227 | 0.227 | 0.227 | – | – | 0.227 | – | – | – | – |
| baseline (text only) | 0.518 | 0.518 | 0.518 | – | 0.500 | 0.518 | – | – | 0.607 | 0.089 |
| A1 graph verbalisation only | 0.532 | 0.532 | 0.532 | – | 0.000 | 0.540 | – | – | 0.635 | 0.103 |
| A2 graph coherence only | 0.539 | 0.539 | 0.539 | – | 0.500 | 0.540 | – | – | 0.638 | 0.099 |
| A3 naive coherence | 0.560 | 0.560 | 0.560 | – | 0.000 | 0.568 | – | – | 0.646 | 0.086 |
| A4 no entity types | 0.582 | 0.582 | 0.582 | – | 0.000 | 0.590 | – | – | 0.546 | 0.069 |
| A5 spaCy NER entity types | 0.582 | 0.582 | 0.582 | – | 0.000 | 0.590 | – | – | 0.669 | 0.087 |
| GraphRAG (full) | 0.567 | 0.567 | 0.567 | – | 0.000 | 0.576 | – | – | 0.651 | 0.084 |

### End to end (A2KB, extraction + linking)

| system | strong P | strong R | strong F1 | weak F1 |
|---|---|---|---|---|
| baseline (text only) | 0.430 | 0.482 | 0.455 | 0.462 |
| GraphRAG (full) | 0.468 | 0.525 | 0.495 | 0.502 |

McNemar baseline vs GraphRAG: only baseline correct = 4, only GraphRAG correct = 11, exact p = 0.1185

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
| ranked_recall@1 | 0.934 |
| ranked_recall@3 | 0.967 |
| ranked_recall@5 | 0.967 |

### Linking (D2KB, gold mentions)

| system | accuracy | accuracy_in_kb | accuracy_ambiguous | accuracy_unambiguous | accuracy_isolated | accuracy_with_context | nil_recall | nil_precision | mean_confidence | ece |
|---|---|---|---|---|---|---|---|---|---|---|
| API top-1 (wbsearchentities) | 0.691 | 0.670 | 0.395 | 0.868 | – | 0.670 | 1.000 | 0.857 | – | – |
| baseline (text only) | 0.918 | 0.912 | 0.816 | 0.981 | 0.750 | 0.920 | 1.000 | 1.000 | 0.835 | 0.082 |
| A1 graph verbalisation only | 0.928 | 0.923 | 0.842 | 0.981 | 1.000 | 0.920 | 1.000 | 1.000 | 0.843 | 0.085 |
| A2 graph coherence only | 0.938 | 0.934 | 0.868 | 0.981 | 0.750 | 0.943 | 1.000 | 1.000 | 0.882 | 0.056 |
| A3 naive coherence | 0.928 | 0.923 | 0.842 | 0.981 | 1.000 | 0.920 | 1.000 | 1.000 | 0.856 | 0.071 |
| A4 no entity types | 0.938 | 0.934 | 0.868 | 0.981 | 1.000 | 0.931 | 1.000 | 1.000 | 0.796 | 0.142 |
| A5 spaCy NER entity types | 0.918 | 0.912 | 0.868 | 0.943 | 1.000 | 0.908 | 1.000 | 1.000 | 0.867 | 0.078 |
| GraphRAG (full) | 0.938 | 0.934 | 0.868 | 0.981 | 1.000 | 0.931 | 1.000 | 1.000 | 0.869 | 0.069 |

### End to end (A2KB, extraction + linking)

| system | strong P | strong R | strong F1 | weak F1 |
|---|---|---|---|---|
| baseline (text only) | 0.701 | 0.747 | 0.723 | 0.745 |
| GraphRAG (full) | 0.722 | 0.769 | 0.745 | 0.766 |

McNemar baseline vs GraphRAG: only baseline correct = 0, only GraphRAG correct = 2, exact p = 0.5000

## Tuned parameters (dev)

| system | nil_threshold | beta | confidence temperature |
|---|---|---|---|
| baseline (text only) | 0.38 | 0.0 | 0.03 |
| A1 graph verbalisation only | 0.38 | 0.0 | 0.03 |
| A2 graph coherence only | 0.38 | 0.2 | 0.03 |
| A3 naive coherence | 0.38 | 0.1 | 0.03 |
| A4 no entity types | 0.4 | 0.2 | 0.05 |
| A5 spaCy NER entity types | 0.36 | 1.0 | 0.05 |
| GraphRAG (full) | 0.38 | 0.1 | 0.03 |

Wikidata calls: {'cache_hits_terms': 74196, 'cache_hits_types': 8255, 'cache_hits_relations': 8255, 'http_calls': 522, 'sparql_calls': 10}
Runtime: 260 s
