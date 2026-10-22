# Evaluation data

Gold data for the text-to-Wikidata linker. Every gold QID was checked against the live Wikidata API on 2026-10-22.

| File | Role |
|---|---|
| `data/dev.jsonl` | 52 hand-written documents, used to tune thresholds (θ, δ, τ, weights) and to compare design choices. `dev-01`..`dev-12` are the original set; `dev-13`..`dev-52` were added on 2026-10-22 so that one mention weighs 0.5 point instead of 2.3. |
| `data/test.jsonl` | 28 hand-written documents, held out. Never tune on it. |
| `data/kore50_dywc.jsonl` | KORE50-DYWC converted to the same format, an external test set (see below). |
| `scripts/verify_gold.py` | Checks offsets, schema and every QID against the API. |
| `scripts/annotate_retrieval.py` | Adds the retrieval-hardness fields. |
| `scripts/check_overlap.py` | Leakage check between dev and test. Prints counts only, never test content. Standard library only. |
| `scripts/convert_kore50.py` | Converts the KORE50-DYWC NIF/Turtle file. Uses the standard library only. |
| `raw/kore50/` | The downloaded KORE50-DYWC archive. Treat it as untrusted data: it is parsed, never executed. |

```bash
python3 eval/scripts/verify_gold.py eval/data/dev.jsonl eval/data/test.jsonl    # must print "0 error(s)"
python3 eval/scripts/annotate_retrieval.py eval/data/dev.jsonl eval/data/test.jsonl
python3 -I eval/scripts/check_overlap.py eval/data/dev.jsonl eval/data/test.jsonl  # must print 0 shared shingles
```

The first two scripts need only `requests`. They send `User-Agent: wdlink-eval/0.1 (yoann@qomment.io)` and stay under 200 requests per minute.

## Format

There is one JSON object per line:

```json
{"id": "test-13", "text": "Paris abducted Helen from Sparta and took her to Troy, ...",
 "mentions": [{"start": 0, "end": 5, "surface": "Paris", "qid": "Q167646", "ambiguous": true,
               "note": "Trojan prince, son of Priam; popular reading (French capital) is wrong",
               "wbs_rank": null, "rest_rank": 3, "api_top1": false, "in_wbs20": false, "in_rest20": true}]}
```

### Mention fields

- **`start`, `end`**: Python character offsets, so `text[start:end] == surface`. They were computed by a script with a whole-word match, never typed by hand, and `verify_gold.py` re-checks them.
- **`qid`**: the gold item, or `null` for a NIL mention.
- **`ambiguous`**: annotator judgment. It is true when the surface form plausibly names several Wikidata items.
- **`note`**: why this reading was chosen, and which readings were ruled out.

### Retrieval fields

`annotate_retrieval.py` adds these on linked mentions only. NIL mentions do not get them.

- **`wbs_rank`, `rest_rank`**: the 1-based rank of the gold QID in the top 20 of `wbsearchentities` and of the REST search, or `null` if it is not there.
- **`api_top1`**: the gold QID is the first `wbsearchentities` hit.
- **`in_wbs20`, `in_rest20`**: the gold QID is in the respective top 20.

These fields describe the live search index on 2026-10-22. They were never used to change a gold label.

## Annotation guideline

### What to annotate

1. **Named entities.** People, places, organisations, works (books, films, songs, albums, journals), events, awards, products, software and programming languages, spacecraft and instruments, mythological figures.
2. **Domain terms.** A term counts when it names a specific scientific or technical concept that has a Wikidata item: a phenomenon, process, method, theory, standard, identifier scheme, substance or taxon. Examples: `radioactivity`, `natural selection`, `transit method`, `dwarf planet`, `exoplanets`, `open science`, `FAIR principles`, `DOI`, `polonium`, `jaguar`, `yacare caimans`.

Always link to the most specific correct item: the 1820 `HMS Beagle`, not another ship of that name; the species *Caiman yacare*, not the subfamily; the spacecraft `Galileo`, not the mission programme.

### What not to annotate

- **Generic words.** For example research, study, data, dataset, people, year, work, team, sample, metadata.
- **Everyday category nouns,** even when Wikidata has an item for them: planet, telescope, river, snake, genus, cat, company, city, country, state, language, software, unit, thermometer.
- **Other spans.** Dates, numbers, quantities, pronouns, and demonym adjectives.

### Spans

- **Minimal name.** Drop leading determiners and titles: `Large Hadron Collider`, not `The Large Hadron Collider`; `Imke Halvorsen`, not `Dr. Imke Halvorsen`.
- **Possessives.** Drop the possessive `'s` (`Darwin` in "Darwin's voyage", `NASA` in "NASA's Galileo").
- **Inflection.** Keep inflected forms exactly as written (`curies`, `exoplanets`, `yacare caimans`).
- **Overlaps.** Mentions never overlap. When names are nested, annotate the longest name: `Riverbend Jaguar Census` is one NIL mention, and the lowercase `jaguar` later in the same sentence is a separate mention.
- **Short forms.** A short form is annotated with the entity it refers to in context: `Hubble` → Edwin Hubble, `Mercury` → Freddie Mercury, `Helen` → Helen of Troy.

### NIL

A NIL mention is a real entity mention whose referent has no Wikidata item: an invented lab, person, company, dataset, facility, project or tool. Each NIL surface was searched with `wbsearchentities` and the REST search. A plain NIL has no item with that exact label, and its note starts with `NIL:`.

#### Hard NIL

A hard NIL is an invented entity whose surface form leads a candidate generator to real items that look plausible. A linker that always picks its best candidate gets these wrong, so they test the NIL threshold. There are two kinds:

- **Name collision** (note prefix `NIL (hard, name collision)`). Real items carry the exact label: people with the same name, or a company or place with the same name. `verify_gold.py` prints a warning for each of these items. Every warning was checked, and none of the items is the referent. These mentions are marked `ambiguous: true`, because the surface does name several items.
- **Lexical near miss** (note prefix `NIL (hard, lexical)`). The exact surface matches nothing, but its distinctive part retrieves real items of the same type, for example `Atacama Deep Field Telescope` → Atacama Cosmology Telescope. These are marked `ambiguous: false`.

Rules for writing one:

1. The entity is invented. The context gives no fact that matches a namesake, such as the employer, field, place or product.
2. For a person name, list every exact-label item (`wbsearchentities`, limit 50, with continuation) and check its description, P106 (occupation) and P108 (employer).
3. For a multi-word name, also search the distinctive sub-span: `Atacama Telescope`, `Global Ocean`, `Journal of Open`, `Franklin Medal`, `Snow and Ice Data Center`.
4. Write the wrong candidates and their QIDs in `note`.

### QID checks

These are applied to every gold QID:

- The entity exists and is not a redirect.
- Its English (or `mul`) label, description and P31 match the intended referent.
- P31 is not a disambiguation page (Q4167410), category, template, list, family name or given name.

`verify_gold.py` automates the mechanical part and prints a `doc | surface | qid | label | description | P31 | name-match` table for the human check.

## Statistics

| | dev | test | total |
|---|---|---|---|
| documents | 52 (12 original + 40 added) | 28 | 80 |
| words per document (min / mean / max) | 16 / 22.6 / 38 | 15 / 19.1 / 28 | |
| mentions | 191 | 97 | 288 |
| linked mentions | 173 | 91 | 264 |
| distinct QIDs | 172 | 89 | 253 (8 QIDs are in both splits) |
| NIL mentions | 18 (12 docs) | 6 (5 docs) | 24 |
| hard NIL mentions (see [Hard NIL](#hard-nil)) | 12: 6 name collisions, 6 lexical near misses | not classified | |
| mentions marked ambiguous | 72 (66 linked + 6 name-collision NILs) | 38 | 110 |
| ambiguous mentions whose gold is not the API top-1 | 47 | 23 | 70 |
| single-mention documents (no coherence signal) | 9 (`dev-05`, `dev-10`, `dev-16`, `dev-26`, `dev-30`, `dev-39`, `dev-49`, `dev-50`, `dev-52`) | 4 (`test-21` to `test-23`, `test-28`) | 13 |

In the 40 added documents (`dev-13`..`dev-52`) there are 148 mentions: 133 linked, 15 NIL, 58 marked ambiguous and 7 single-mention documents.

**Leakage check** (`check_overlap.py`, 2026-10-22):

- 0 dev documents share a 6-word shingle with a test document.
- 8 (surface, QID) pairs and 8 QIDs appear in both splits. Five of them come from `dev-01`..`dev-12`, and none is a NIL.

### Hard NILs in dev

| doc | surface | kind | wrong candidates |
|---|---|---|---|
| dev-15 | Thomas Berger | name collision | 44 people with this label: novelist Q1353956, badminton player Q1432002, researchers at Bern, DLR and Vienna. None is a hydrologist in Innsbruck. |
| dev-18 | Tidewater | name collision | US coastal region Q7800894, marine-services company Q7800873, villages, a hymn tune. None is an ocean model. |
| dev-22 | Lena Fischer | name collision | 5 people: badminton player Q65928264, researcher Q88769653 (Edinburgh, TCD), politician, film producer, biologist |
| dev-22 | Global Ocean Carbon Archive | lexical | "Global Ocean" retrieves GLODAP Q3108961, GOOS Q1531644 and the Global Oceanographic Data Center Q11422506. |
| dev-24 | Journal of Open Data Stewardship | lexical | "Journal of Open" retrieves JOSS Q50817797, the Journal of Open Research Software Q27725945 and the Journal of Open Humanities Data Q96720095. |
| dev-25 | Atacama Deep Field Telescope | lexical | Atacama Cosmology Telescope Q753067, ALMA Q725364 |
| dev-28 | Linnaeus Biodiversity Portal | lexical | Carl Linnaeus Q1043, Linnaeus University Q1751928, India Biodiversity Portal Q50658883 |
| dev-29 | Franklin Medal for Open Data | lexical | Franklin Medal Q3141777, Benjamin Franklin Medal Q817496 |
| dev-29 | Sophie Martin | name collision | 15 people: Swiss biologist Q21264712, Canadian singer Q3490997, researchers at Johns Hopkins and Bristol. None works on air-quality data in Lyon. |
| dev-30 | Nordic Snow and Ice Data Centre | lexical | National Snow and Ice Data Center Q1216646 |
| dev-45 | Northwind | name collision | Canadian software company Q7060448, an album, a band, a video game, a DC Comics character |
| dev-45 | Daniel Hughes | name collision | 14 people: herpetologist Q54226954, cricketer Q16232638, rugby player, game programmer, researchers. None is an investor in Leeds. |

The plain NILs in dev are Kestrel Wetland Survey, Varrow Coastal Data Lab, Imke Halvorsen, Alpine Water Observatory, Baltic Sediment Data Centre and Quillfen Birdwatchers' Club.

### Content mix

The dev set mirrors the test set. The 40 added documents use new texts, and their entities were chosen to differ from those listed for test below.

| Group | dev | test |
|---|---|---|
| CODATA / science: research data, FAIR, ORCID, DOI, Zenodo, CERN, WDS, ISC, Python/R/Java, journals, telescopes vs people, Darwin, Curie, Mercury/Saturn/Pluto/Eris | `dev-01`..`dev-05`, `dev-13`..`dev-30` | `test-01`..`test-11` |
| General-domain ambiguity: Paris ×3 readings, Washington ×2, Jordan ×2, Georgia, Cambridge, Amazon ×2, Apple, jaguar, Python (genus), Victoria, Lincoln, Saturn (god), Mercury (singer) | `dev-06`..`dev-10`, `dev-31`..`dev-45` | `test-12`..`test-24` |
| Easy, unambiguous and NIL-heavy | `dev-11`, `dev-12`, `dev-46`..`dev-52` | `test-25`..`test-28` |

The added documents cover the following entities:

- **Science (`dev-13`..`dev-30`):**
  - people: Franklin, Watson and Crick; Faraday and Maxwell
  - space: Gaia, Sentinel-2, Cassini, Huygens and Titan, SDSS
  - repositories: GenBank, Protein Data Bank, Dryad, PANGAEA, Software Heritage
  - standards and identifiers: BIPM, CODATA and the Planck constant, Dublin Core, ROR, ISSN, DataCite, GBIF and Darwin Core
  - software, journals, taxa and elements: Fortran, Julia, Matplotlib and Ruby; the Data Science Journal; the monarch butterfly and milkweed; lead
  - 10 hard NILs and 2 plain NILs
- **General (`dev-31`..`dev-45`):**
  - places: Boston (Lincolnshire), Perth (Scotland), Alexandria (Virginia)
  - people named by surname or nickname: Ford, Nixon and Carter; Bush (H. W.); Tesla and Edison; Puma and Adi Dassler
  - works and companies: Orange (the telecom group), Dune, Mars (the company), Michael Jackson (the beer writer)
  - other readings: Columbia (the shuttle); Apollo, Python (the serpent), Delphi and the Pythia; Chelsea and Bayern
  - 2 hard NILs
- **Easy (`dev-46`..`dev-52`):** Mendeleev and three elements, Kilimanjaro and Mount Kenya, the Mona Lisa, Mandela, the Panama Canal, Fleming and penicillin, and one plain NIL.

Mentions where the popular reading is wrong, meaning the gold is ambiguous and is not the first `wbsearchentities` hit (`ambiguous and not api_top1`):

- **dev (47):**
  - original documents (8): Enigma, Mind, Mercury (element), Washington (George), Trenton, Jordan (country), Jordan River, Lincoln
  - added documents (39): Watson, Crick, double helix, Gaia, Dryad, Julia, Maxwell, monarchs, PANGAEA, Cassini, Titan, redshifts, ROR, Boston, Lincolnshire, Perth, Ford, Nixon, Carter, Orange, Dune, Alexandria, Potomac, Michael Jackson, Puma, Adi, Columbia, Apollo, Python (serpent), Delphi, Pythia, Mars (company), McLean, Bush, Chelsea, Bayern, Tesla, Edison, Florence
- **test (23):** Hubble, Milky Way, Kepler, Jupiter ×2, Galileo (the spacecraft), Darwin (person), HMS Beagle, curies, Eris, Michael Jordan, Paris (of Troy), Helen, Troy, Paris, Texas (film), Georgia (country), Charles River, Amazon (river), jaguar, Python (genus), Victoria, Mercury (Freddie), ORCID.

Some ambiguous golds are the API top-1 even though a reader might expect otherwise: Darwin (the city in dev-09), Lead (the element in dev-16), Faraday (dev-20), Ruby (the language in dev-26), Saturn (the god in test-23) and Washington (the state in test-22). The ranking alone does not decide them; the context has to confirm them.

### Retrieval hardness

These figures were measured on 2026-10-22, with the surface form sent unchanged.

| linked mentions | dev (173) | test (91) | total (264) |
|---|---|---|---|
| `wbsearchentities` @1 / @10 / @20 | 120 / 154 / 159 | 61 / 82 / 85 | 181 / 236 / 244 |
| REST search @1 / @10 / @20 | 134 / 162 / 164 | 68 / 86 / 87 | 202 / 248 / 251 |
| union of the two top 20s | 165 | 88 | 253 |
| absent from the wbs top 20 | 14 | 6 | 20 |
| absent from the REST top 20 | 9 | 4 | 13 |
| absent from both | 8 | 3 | 11 |

The added documents are harder for retrieval than the original 12: wbs@1 is 89/133 (66.9%), against 31/40 (77.5%).

Mentions missing from at least one top 20:

| doc | surface | gold | wbs rank | REST rank | why |
|---|---|---|---|---|---|
| dev-03, test-06 | FAIR principles | Q29032648 (label "FAIR data") | – | – | the phrase is neither a label nor an alias |
| dev-10 | Lincoln | Q91 Abraham Lincoln | – | – | surname only |
| test-24 | Mercury | Q15869 Freddie Mercury | – | – | surname only |
| test-08 | curies | Q229354 curie | – | – | plural; wbs returns streets named Curiestraat / Curiestraße |
| test-13 | Paris | Q167646 Paris of Troy | – | 3 | wbs returns other items labelled Paris: places, names, ships, an album |
| test-17 | Amazon | Q3783 Amazon River | 13 | – | the label is "Amazon River" |
| test-03 | exoplanets | Q44559 | – | 1 | plural; wbs is a prefix match on the exact string |
| test-19 | yacare caimans | Q756678 | – | 1 | plural |
| dev-13 | Watson | Q83333 James Watson | – | – | surname only |
| dev-13 | Crick | Q123280 Francis Crick | – | 7 | surname only |
| dev-14 | parallaxes | Q906561 stellar parallax | – | – | plural, and the label adds "stellar" |
| dev-18 | Julia | Q2613697 (programming language) | – | 4 | the wbs top 20 is filled with people and given names |
| dev-20 | electromagnetic waves | Q11386 | – | 6 | plural |
| dev-21 | monarchs | Q212398 Danaus plexippus | – | 8 | plural; the label is the Latin name |
| dev-21 | oyamel fir | Q378592 Abies religiosa | – | – | the English common name is neither a label nor an alias |
| dev-25 | quasars | Q83373 | – | 1 | plural |
| dev-25 | redshifts | Q76250 | – | – | plural |
| dev-27 | DOIs | Q25670 | – | 2 | plural |
| dev-33 | Carter | Q23685 Jimmy Carter | – | – | surname only |
| dev-38 | Adi | Q76751 Adolf Dassler | – | – | nickname only |
| dev-42 | Bush | Q23505 George H. W. Bush | 19 | – | surname only; George W. Bush ranks higher |

Two consequences for the pipeline:

- The recall ceiling for raw surface forms with the union of both APIs is 165/173 (95.4%) on dev, 88/91 (96.7%) on test and 253/264 (95.8%) overall.
- The 11 mentions absent from both APIs need one of two fixes:
  - **Surname or nickname only** (Lincoln, Mercury, Watson, Carter, Adi): a query on the person's full name, taken from the document or from a name index.
  - **Plural or common name** (curies, parallaxes, redshifts, oyamel fir, FAIR principles): lemmatised and alias queries.

### Hesitations

| Mention | Gold | Alternative considered |
|---|---|---|
| `Galileo` in test-05 | Q105425030, the spacecraft | Q182008, the mission programme |
| `Cassini` in dev-23 | Q2941291, the orbiter | Q165585, the Cassini–Huygens mission (the same choice as for Galileo) |
| `ORCID` in test-26 | Q19861084 (ORCID, Inc.), because the text talks about membership | Q51044 (ORCID iD) or Q123508757 (ORCID Registry) |
| `ORCID iD` in dev-03 | Q51044 | – |
| `FAIR principles` | Q29032648 | No item is labelled "FAIR principles". |
| `iPhone` in test-18 | Q2766, the product line | The first-generation model, which has its own item |
| `International Science Council` | Q57587699 | Q131906054, a near-duplicate item with no description |
| `double helix` in dev-13 | Q60535862, nucleic acid double helix (alias "double helix") | Q40120282, structure of DNA |
| `Dryad` in dev-17 | Q5309616, Dryad Digital Repository (alias "Dryad"), because data is deposited there | Q108872504, the Dryad non-profit |
| `Software Heritage` in dev-24 | Q28127082, the infrastructure | Q112594892, "Software Heritage archive", which has no description |
| `milkweed` in dev-21 | Q162153, the genus *Asclepias* | Danaus plexippus (Q212398) also carries the alias "milkweed" |
| `Boston` in dev-31 | Q311975, the town | Q894076, the Borough of Boston district, which was the actual counting area of the 2016 referendum |
| `Lincolnshire` in dev-31 | Q23090, the ceremonial county | Q67533486 (historic county), Q21269047 (non-metropolitan county) |

## KORE50-DYWC (external test set)

- **Paper:** Noullet, Mix, Färber. *KORE 50^DYWC: An Evaluation Data Set for Entity Linking Based on DBpedia, YAGO, Wikidata, and Crunchbase.* LREC 2020. https://aclanthology.org/2020.lrec-1.291
- **Source:**
  - The official URL in the paper, `http://people.aifb.kit.edu/mfa/datasets/kore50-lrec2020.zip`, now returns 404, and there is no GitHub repository.
  - The archive was retrieved from the Wayback Machine snapshot https://web.archive.org/web/20221124215821id_/https://people.aifb.kit.edu/mfa/datasets/kore50-lrec2020.zip. It is 33 KB, SHA-1 `367bf3d19527eab006bdd6ba5276ec021dd94f80`, and that checksum is identical in all four captures from 2021 to 2022.
  - The file used is `KORE_50_Wikidata.ttl`, dated 2020-03-18.
- **License:**
  - The DYWC annotations have no license. The zip has no LICENSE file, and the archived AIFB dataset page says nothing about one. The CC BY-NC notice of the LREC paper covers the paper, not the data.
  - The original KORE50 texts are CC BY-SA 3.0, according to the MPI AIDA downloads page.
  - Use it for local evaluation. Before redistributing `kore50_dywc.jsonl` or `raw/kore50/` in a public repository, ask the authors (michael.faerber@kit.edu).
- **Conversion command:** `python3 -I eval/scripts/convert_kore50.py eval/raw/kore50/KORE_50_Wikidata.ttl eval/data/kore50_dywc.jsonl eval/raw/kore50/kore50-nif-dbpedia.ttl`
  - **Format.** The NIF fields used are `nif:isString`, `nif:referenceContext`, `nif:beginIndex`, `nif:endIndex`, `nif:anchorOf` and `itsrdf:taIdentRef`. Only Wikidata IRIs are kept.
  - **Counts.** There are 50 documents and 307 linked mentions; the paper says 309. None are NIL and none were dropped.
  - **Offsets.** No mismatches.
  - **Live check.** `verify_gold.py` on 2026-10-22 found 0 errors: no missing or redirected QID and no disambiguation page among the 221 distinct QIDs. Its 32 warnings are all for documents shorter than 15 words, which is how KORE50 is written.
- **Quirks fixed:**
  - The file is Latin-1, not UTF-8.
  - One IRI has the form `wikidata.org/wiki/Q728646`; it was normalised to the QID.
  - BUS07 had stray backslashes before quotes. They were removed and the offsets shifted.
  - A stray trailing "?" was removed from POL03 and POL04.
  - DYWC numbers the documents CEL01–CEL50. They were mapped back to the original KORE50 IDs, checked by exact text match.
- **Core vs extra mentions:**
  - DYWC also links pronouns, articles and common nouns ("their", "children", "the"…).
  - **The `kore50_core` field.** It is true for the 141 mentions whose span matches a mention of the original KORE50 file (`kore50-nif-dbpedia.ttl`, from the same zip). It is false for the 166 extra mentions.
  - Only core mentions have `ambiguous: true`, and their `note` reads "KORE50-DYWC core"; the extras read "KORE50-DYWC extra".
  - **Evaluate named-entity linking on core mentions only:** 141 mentions, 124 distinct QIDs.
- **Original KORE50 mentions without an exact DYWC match (3):** DYWC links a longer span in each case:
  - `Windows` → "Windows operating system" (BUS02)
  - `Mayall` → "Mayall 's band" (MUS10)
  - `Gunners` → "The Gunners" (SPO02)
- **Quirks in the original DBpedia file, handled during alignment:**
  - In SPO04 and SPO07, the offsets count bytes rather than characters.
  - POL10's "Kennedy" is attached to the POL09 context.

## Sources

- Wikidata Action API, `wbgetentities` and `wbsearchentities`: https://www.wikidata.org/w/api.php
- Wikibase REST API, search: https://www.wikidata.org/w/rest.php/wikibase/v1/search/items
- Rate limits: https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
- KORE50-DYWC: https://aclanthology.org/2020.lrec-1.291
- Original KORE50 (AIDA, MPI): https://www.mpi-inf.mpg.de/departments/databases-and-information-systems/research/ambiverse-nlu/aida/downloads
