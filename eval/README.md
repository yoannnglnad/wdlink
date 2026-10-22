# Evaluation data

Gold data for the text-to-Wikidata linker. Every gold QID was checked against the live Wikidata API on 2026-10-22.

| File | Role |
|---|---|
| `data/dev.jsonl` | 12 hand-written documents, used to tune thresholds (θ, δ, τ, weights). |
| `data/test.jsonl` | 28 hand-written documents, held out. Never tune on it. |
| `data/kore50_dywc.jsonl` | KORE50-DYWC converted to the same format, an external test set (see below). |
| `scripts/verify_gold.py` | Checks offsets, schema and every QID against the API. |
| `scripts/annotate_retrieval.py` | Adds the retrieval-hardness fields. |
| `scripts/convert_kore50.py` | Converts the KORE50-DYWC NIF/Turtle file. Uses the standard library only. |
| `raw/kore50/` | The downloaded KORE50-DYWC archive. Treat it as untrusted data: it is parsed, never executed. |

```bash
python3 eval/scripts/verify_gold.py eval/data/dev.jsonl eval/data/test.jsonl    # must print "0 error(s)"
python3 eval/scripts/annotate_retrieval.py eval/data/dev.jsonl eval/data/test.jsonl
```

Both scripts need only `requests`. They send `User-Agent: wdlink-eval/0.1 (yoann@qomment.io)` and stay under 200 requests per minute.

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

A NIL mention is a real entity mention whose referent has no Wikidata item: an invented lab, person, company, dataset, facility, project or tool. Each NIL surface was searched with `wbsearchentities` to make sure no item carries that exact label.

### QID checks

These are applied to every gold QID:

- The entity exists and is not a redirect.
- Its English (or `mul`) label, description and P31 match the intended referent.
- P31 is not a disambiguation page (Q4167410), category, template, list, family name or given name.

`verify_gold.py` automates the mechanical part and prints a `doc | surface | qid | label | description | P31 | name-match` table for the human check.

## Statistics

| | dev | test | total |
|---|---|---|---|
| documents | 12 | 28 | 40 |
| words per document (min / mean / max) | 16 / 19.1 / 29 | 15 / 19.1 / 28 | |
| mentions | 43 | 97 | 140 |
| linked mentions | 40 | 91 | 131 |
| distinct QIDs | 40 | 89 | 124 |
| NIL mentions | 3 (2 docs) | 6 (5 docs) | 9 |
| mentions marked ambiguous | 14 | 38 | 52 |
| ambiguous mentions whose gold is not the API top-1 | 8 | 23 | 31 |
| single-mention documents (no coherence signal) | 2 (`dev-05`, `dev-10`) | 4 (`test-21` to `test-23`, `test-28`) | 6 |

### Content mix

The dev set mirrors the test set.

| Group | dev | test |
|---|---|---|
| CODATA / science: research data, FAIR, ORCID, DOI, Zenodo, CERN, WDS, ISC, Python/R/Java, journals, telescopes vs people, Darwin, Curie, Mercury/Saturn/Pluto/Eris | `dev-01`..`dev-05` | `test-01`..`test-11` |
| General-domain ambiguity: Paris ×3 readings, Washington ×2, Jordan ×2, Georgia, Cambridge, Amazon ×2, Apple, jaguar, Python (genus), Victoria, Lincoln, Saturn (god), Mercury (singer) | `dev-06`..`dev-10` | `test-12`..`test-24` |
| Easy, unambiguous and NIL-heavy | `dev-11`, `dev-12` | `test-25`..`test-28` |

Mentions where the popular reading is wrong, meaning the gold is ambiguous and is not the first `wbsearchentities` hit (`ambiguous and not api_top1`):

- **dev (8):** Enigma, Mind, Mercury (element), Washington (George), Trenton, Jordan (country), Jordan River, Lincoln.
- **test (23):** Hubble, Milky Way, Kepler, Jupiter ×2, Galileo (the spacecraft), Darwin (person), HMS Beagle, curies, Eris, Michael Jordan, Paris (of Troy), Helen, Troy, Paris, Texas (film), Georgia (country), Charles River, Amazon (river), jaguar, Python (genus), Victoria, Mercury (Freddie), ORCID.

Some ambiguous golds are the API top-1 even though a reader might expect otherwise: Darwin (the city in dev-09), Saturn (the god in test-23) and Washington (the state in test-22). The ranking alone does not decide them; the context has to confirm them.

### Retrieval hardness

These figures were measured on 2026-10-22, with the surface form sent unchanged.

| linked mentions | dev (40) | test (91) | total (131) |
|---|---|---|---|
| `wbsearchentities` @1 / @10 / @20 | 31 / 37 / 38 | 61 / 82 / 85 | 92 / 119 / 123 |
| REST search @1 / @10 / @20 | 34 / 38 / 38 | 68 / 86 / 87 | 102 / 124 / 125 |
| union of the two top 20s | 38 | 88 | 126 |
| absent from the wbs top 20 | 2 | 6 | 8 |
| absent from the REST top 20 | 2 | 4 | 6 |
| absent from both | 2 | 3 | 5 |

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

Two consequences for the pipeline:

- The recall ceiling for raw surface forms with the union of both APIs is 126/131 (96.2%).
- Fixing the remaining five needs either mention expansion within the document (Lincoln, Mercury) or lemmatised and alias queries (curies, FAIR principles).

### Hesitations

| Mention | Gold | Alternative considered |
|---|---|---|
| `Galileo` in test-05 | Q105425030, the spacecraft | Q182008, the mission programme |
| `ORCID` in test-26 | Q19861084 (ORCID, Inc.), because the text talks about membership | Q51044 (ORCID iD) or Q123508757 (ORCID Registry) |
| `ORCID iD` in dev-03 | Q51044 | – |
| `FAIR principles` | Q29032648 | No item is labelled "FAIR principles". |
| `iPhone` in test-18 | Q2766, the product line | The first-generation model, which has its own item |
| `International Science Council` | Q57587699 | Q131906054, a near-duplicate item with no description |

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
