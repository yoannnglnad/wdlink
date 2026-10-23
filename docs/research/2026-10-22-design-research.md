# Recherche de conception — pipeline d'entity linking texte → Wikidata

> **Statut : journal de recherche initial (22/10/2026), remplacé par les ADR.** Plusieurs choix proposés ici ont été changés après benchmark (typage NER, cartes avec tous les faits, expansion des requêtes, seuil Zipf, modèle spaCy) et la mesure « P279* = 41 s » n'a pas été reproduite. La référence est `docs/adr/README.md`.


Date : 2026-10-22. Préparation du test technique CODATA. Toutes les mesures ci-dessous ont été faites en live sur l'API Wikidata ce jour-là ; les requêtes et scripts de mesure sont dans `probes/`.

## 1. Décisions proposées

| Sujet | Choix | Raison principale |
|---|---|---|
| Python | 3.12, géré par uv | networkx 3.7 exige ≥ 3.12 et exclut 3.14.1 ; spaCy 3.8.16 a des wheels 3.10–3.14 |
| Extraction | spaCy 3.8 + `en_core_web_sm` (NER + noun_chunks, offsets), `trf` activable par config | sm = 84,3 F1 NER pour 12 Mo ; trf = 89,9 mais 436 Mo + torch |
| Mentions courtes | Expansion intra-document : « Curie » après « Marie Curie » hérite des candidats de la mention longue | `wbsearchentities("Curie")` ne contient pas Q7186 dans son top 20 |
| Candidats | Union `wbsearchentities` top 20 + REST `/v1/search/items` top 20, puis pré-classement local et top 10 gardé pour le graphe | Mesuré sur 19 mentions ambiguës : l'union retrouve 19/19 ; REST est meilleur @1 (12 vs 7) |
| Termes des candidats | `wbgetentities` par lots de 50, `props=labels\|descriptions\|aliases\|sitelinks`, `languages=en\|mul`, `languagefallback=1`, `maxlag=5`, sans `claims` | `claims` = 1,1 Mo pour 5 entités ; labels anglais souvent sous `mul` (Q42) |
| Relations et types | SPARQL sur `query.wikidata.org` (graphe principal) | Arêtes directes entre candidats en 0,4 s ; types `P31/P279{0..3}` en 1,25 s contre 41 s (et faux) pour `P31/P279*` |
| Graphe | rdflib en SKOS (mapping §3), exporté en Turtle, vue NetworkX dérivée pour les calculs | Exigence explicite du sujet ; NetworkX seul ne répond pas à « based on RDF (SKOS) » |
| Embeddings | `BAAI/bge-small-en-v1.5` (33M, MIT, 384 dim), modèle changeable par config | Léger sur CPU ; EmbeddingGemma est gated, jina-v3 en CC-BY-NC |
| « GraphRAG » | Récupérer le sous-graphe de chaque candidat, le verbaliser dans une « carte » embeddée, puis cohérence de graphe déterministe | Microsoft GraphRAG (communautés + résumés LLM) vise la synthèse de corpus : mauvaise granularité, coûteux, non déterministe |
| LLM | Hors cœur. Extension optionnelle : re-ranker activé seulement si la marge top1–top2 est faible | Garder le cœur reproductible et la comparaison avec / sans graphe propre |
| Cache | Cache disque de tous les appels Wikidata, avec date de snapshot | 200 req/min max ; Wikidata change en continu ; évaluation reproductible |

## 2. Récupération des candidats

Recall sur 19 mentions ambiguës (Jaguar, Mercury, Java, Michael Jordan, Washington, Paris → Pâris de Troie, Amazon…) :

| API | @1 | @5 | @10 | @50 |
|---|---|---|---|---|
| `wbsearchentities` | 7 | 16 | 17 | 19 |
| REST `/v1/search/items` | 12 | 17 | 17 | 18 |
| Cirrus `list=search` | 7 | 14 | 16 | 18 |

- `wbsearchentities` : préfixe sur labels et alias de toutes les langues, `mul` compris ; limite 50 ; ne renvoie que l'alias qui a matché.
- REST `/v1/search/items` : labels et alias, limite jusqu'à 500. `/v1/suggest/items` donne exactement le classement de `wbsearchentities`.
- Cirrus `list=search` : pas d'alias dans la réponse, a raté l'alias `mul` « Big Apple ». Écarté.
- Cas « Curie » : absent du top 20 de `wbsearchentities`, 17ᵉ en REST. Cas « Mercury » pour Freddie Mercury (Q15869) : absent des deux top 20. Les mentions réduites au nom de famille sont une limite connue, traitée par l'expansion intra-document.
- Filtre à l'entrée : écarter les candidats dont P31 ∈ {Q4167410 page d'homonymie, Q4167836 catégorie, Q101352 nom de famille, Q202444 prénom, Q13406463 liste, Q11266439 modèle}.
- Limites 2026 : 200 req/min avec un User-Agent conforme, 10/min sans ; 429 + `Retry-After` au-delà ; 3 requêtes simultanées max. WDQS : 60 s par requête, 60 s de calcul par minute, 5 requêtes parallèles par IP. Depuis mai 2025 les articles scientifiques sont dans `query-scholarly.wikidata.org`, pas dans le graphe principal.
- Vector DB Wikidata (Embedding Project) : alpha, 5 req/min par worker, requêtes envoyées à Jina (conservées 90 jours), modèle en CC-BY-NC, hôtes injoignables le jour du test. Écartée du cœur.

## 3. Graphe RDF / SKOS

L'export RDF de Wikidata utilise déjà `skos:prefLabel` et `skos:altLabel`, mais `schema:description` (pas `skos:definition`) : d'après Help:Description, un item est défini par ses déclarations, pas par sa description.

| Wikidata | Graphe local |
|---|---|
| candidat | `cand:Qx a skos:Concept ; skos:inScheme doc:scheme ; skos:exactMatch wd:Qx` |
| label / alias | `skos:prefLabel` / `skos:altLabel` |
| description | `schema:description` |
| P279 (sous-classe de) | `ex:broaderGeneric` ⊑ `skos:broader` |
| P31 (instance de) | `ex:broaderInstantive` ⊑ `skos:broader`, et `wdt:P31` conservé |
| P361 / P527 (partie de / a pour partie) | `ex:broaderPartitive` / `ex:narrowerPartitive` |
| autres propriétés de la liste blanche | `wdt:Pxx` conservé + `skos:related` si la paire n'a pas déjà de lien hiérarchique (contrainte S27) |
| document | `doc:scheme a skos:ConceptScheme` |
| mention | `nif:Phrase` (anchorOf, beginIndex, endIndex) + `itsrdf:taIdentRef wd:Qx`, `itsrdf:taConfidence`, `itsrdf:taClassRef` |
| exécution | `prov:Activity` (poids, modèle, date du snapshot) |

- Ne pas mapper P31 sur `skos:broader` nu : `skos:broaderTransitive` mélangerait les chaînes instance et sous-classe. Les sous-propriétés Generic / Partitive / Instantive viennent du SKOS Primer §4.7 et correspondent aux relations BTG / BTP / BTI de l'ISO 25964.
- NIF + ITS RDF est le format des mentions utilisé par GERBIL.

Construction :
1. SPARQL A : labels, alias, description, nombre de sitelinks, types `P31/P279{0..3}` (UNION).
2. SPARQL B : arêtes directes entre candidats de mentions différentes, toutes propriétés sauf P1889 (« différent de ») et P460.
3. SPARQL C : voisins sortants à 1 saut sur la liste blanche, intersectés en local (pas de requête de chemins à 2 sauts : 8,8 s, croissance quadratique, dominée par le hub Q142 France).
4. Liste blanche : P17, P131, P276, P159, P19, P20, P27, P106, P101, P166, P69, P108, P463, P361, P527, P50, P57, P175, P495, P800. P1346 exclu (238 voisins pour Q38104).

## 4. Score, confiance, NIL

Score local d'un candidat c pour une mention m :

`L = 0.50·s_txt + 0.20·s_name + 0.15·s_type + 0.15·s_pop`

- `s_txt = max(0, cos(E(contexte), E(carte)))`, la carte étant label + description + triples verbalisés (« Marie Curie — award received: Nobel Prize in Physics; field of work: radioactivity »).
- `s_name` : correspondance entre la mention et le label ou un alias.
- `s_type` ∈ {1 compatible, 0.5 inconnu, 0 incompatible}, via une table faite à la main de label spaCy vers classe Wikidata, vérifiée à profondeur ≤ 3 : PERSON→Q5, ORG→Q43229, GPE→Q56061/Q6256/Q515/Q486972, LOC→Q2221906/Q618123, NORP→Q41710/Q231002/Q9174/Q7278, FAC→Q13226383/Q41176, EVENT→Q1656682, WORK_OF_ART→Q17537576/Q838948, PRODUCT→Q2424752, LAW→Q7748, LANGUAGE→Q34770. Les noun chunks sans label NER ont `s_type = 0.5`.
- `s_pop = log(1+sitelinks) / max sur les candidats de log(1+sitelinks)`.

Relation entre deux candidats (voisins pondérés par leur rareté, pour neutraliser les hubs comme Q5 ou Q142) :

`r(c,c') = max(δ_edge, Σ_{x∈N(c)∩N(c')} idf(x) / √(Σ_{N(c)} idf · Σ_{N(c')} idf))`, avec `idf(x) = log(1 + |V| / df(x))`

Cohérence (Pershina et al. : c1 = ignorer les candidats de la même mention, c2 = ne garder que la meilleure contribution de chaque autre mention) :

`G(m,c) = moyenne_{m'≠m} max_{c'∈C(m')} r(c,c') · softmax_{C(m')}(L/τ)(c')`

Score final : `S = 0.7·L + 0.3·G`, avec `S = L` si la mention est seule ou si aucun de ses candidats n'a d'arête.

Confiance et NIL :
- `p = softmax sur C ∪ {NIL} de S/τ`, avec `S_NIL = θ` ; seul τ est ajusté sur le dev.
- Sélection du premier candidat si `S1 ≥ θ` (0,35) et `S1 − S2 ≥ δ` (0,03), sinon NIL avec le classement conservé dans la sortie.
- θ, δ et les poids : grille sur le dev, jamais sur le test. Régression logistique en contrôle seulement (leave-one-doc-out), le jeu est trop petit.

Les poids ci-dessus sont des points de départ (AIDA utilisait 0,43 / 0,47 / 0,10 pour prior / similarité / cohérence).

## 5. Évaluation

Jeux de données :
- Jeu fait main, ~40 phrases, domaine scientifique et données, ambiguës et non ambiguës, avec des NIL, QIDs vérifiés sur l'API, découpé en dev / test.
- KORE50-DYWC (LREC 2020, annotations Wikidata, ~144 mentions très ambiguës) comme test externe. Licence et taille exacte à vérifier.
- Option : ZELDA SLINKS-SHADOW / SLINKS-TOP (904 mentions chacun, entité rare vs populaire de même nom), titres Wikipedia à convertir en QID. Le dépôt n'a pas de licence.

Métriques :
- recall@k des candidats (avant et après pré-classement) : plafond atteignable par le linking ;
- accuracy en mode D2KB (mentions gold fournies) et micro-F1 en mode A2KB (extraction comprise) ;
- précision et rappel des NIL à part ;
- précision séparée pour les mentions isolées et non isolées.

Systèmes comparés :
- top-1 de l'API (référence triviale) ;
- baseline sans graphe : même récupération, carte = label + description, poids de G = 0 ;
- GraphRAG complet.

Ablations : A1 sans G (verbalisation seule), A2 sans verbalisation (cohérence seule), A3 cohérence naïve (sans idf, sans pondération par L, sans c1/c2).

Références externes : spacy-entity-linker (max-prior, MIT, dernière activité 2023, KB de 1,3 Go ; compatibilité spaCy 3.8 non vérifiée) comme baseline lançable ; ReFinED (Amazon) cité comme état de l'art. Travaux LLM à citer : ChatEL (LREC-COLING 2024), OneNet (EMNLP 2024), LELA (ISWC 2026).

## 6. Pièges observés

- Évidence circulaire : Q229354 (curie, unité) —P111→ Q317949 (activité, grandeur) ; deux mauvais candidats se soutiennent et finissent à égalité avec Q11448 (radioactivity). Corrigé par c1/c2 et la pondération par L.
- Arête négative : P1889 (« différent de ») relie Q11448 et Q317949. Exclue.
- Arêtes au sein d'une même mention (candidats de « Sorbonne » reliés par P527, P155). Exclues par c1.
- Hubs : Q142 (France) relie 8 candidats ; P1346 donne 238 voisins à Q38104 ; Q5 arrive via P31. D'où l'idf.
- Limite du graphe : Q38104 (Nobel de physique) et Q44585 (Nobel de chimie) sont à égalité en cohérence, Marie Curie ayant reçu les deux. Seul le texte tranche.
- Popularité : Q90 (Paris) a 366 sitelinks, face à Paris (Texas) ; le prior doit rester minoritaire.
- L'exemple du sujet donne radioactivity = Q11452, qui est *general relativity* ; le bon QID est Q11448.

## 7. Outils Claude Code retenus

Audit de 25 skills du registre skills.sh et des 315 plugins du marketplace officiel.

| Outil | Pourquoi |
|---|---|
| fuzheado/wikipedia-ai-skills@wikidata-reconciliation | Scoring des candidats, pénalité homonymie, réponse « UNRESOLVED », seuil réglé sur un gold set |
| fuzheado/wikipedia-ai-skills@wikidata | Piège `mul`, lots de 50, entités renommées |
| fuzheado/wikipedia-ai-skills@wikimedia-api-access | User-Agent, limites 2026, cache, backoff 429 |
| plugin `astral` (astral-sh/claude-code-plugins) | uv, ruff, LSP ty |
| plugin `context7` (officiel) | Docs à jour de rdflib, spaCy, sentence-transformers |

Écartés : skills GraphRAG (Neo4j / LangChain, orientés QA), skills spaCy et NetworkX génériques, skills d'évaluation liés à d'autres frameworks. Risques notés : `allowed-tools` Bash accordé d'avance (nvidia rag-eval, neo4j graphrag), skill « ontology » qui se déclenche sur « remember ».

## 8. Sources

- https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
- https://www.mediawiki.org/wiki/Wikibase/Indexing/RDF_Dump_Format
- https://www.wikidata.org/wiki/Help:Description
- https://www.wikidata.org/wiki/Wikidata:Vector_Database
- https://www.w3.org/TR/skos-primer/ (§4.7)
- https://www.w3.org/TR/skos-reference/ (S19–S20, S27)
- https://www.w3.org/2005/11/its/rdf
- https://aclanthology.org/D11-1072/ (AIDA)
- https://aclanthology.org/N15-1026/ (PPR, Pershina et al.)
- https://arxiv.org/abs/1904.09131 (OpenTapioca)
- https://arxiv.org/abs/2008.05190 (Mulang et al., contexte KG depuis Wikidata)
- https://arxiv.org/abs/2404.16130 (Microsoft GraphRAG)
- https://aclanthology.org/2020.lrec-1.291 (KORE50-DYWC)
- https://github.com/flairNLP/zelda
