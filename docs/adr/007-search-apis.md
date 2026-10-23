# ADR-007 — Candidate sources: `wbsearchentities` + REST search, plus a human search for bare names

**Status:** accepted · **Evidence:** benchmark [`search_apis`](../../eval/benchmarks/search_apis.md), plus the 19-mention retrieval probe from the design research.

## Context

Wikidata exposes three text searches:

| API | What it does |
|---|---|
| `wbsearchentities` | prefix match on labels and aliases in all languages |
| Wikibase REST `/v1/search/items` | full-text search on labels and aliases |
| CirrusSearch (`action=query&list=search`) | full-text search over item pages; accepts `haswbstatement` filters |

Each search costs one request per query, and the API limit is 200 requests per minute. A bare surname such as "Lincoln" or "Curie" is a known failure case: the prefix and REST searches rank places and works first. Restricting CirrusSearch to humans (`haswbstatement:P31=Q5`) returns the famous bearer of the name first.

## Options measured

All variants use the top 20 per API (ADR-008). "+ humans" adds the human search, top 5, for single capitalised words.

| Sources | CV accuracy | NIL recall | gold retrieved | Δ [95% CI] | McNemar p |
|---|---|---|---|---|---|
| wbs | 0.838 | 0.667 | 0.919 | −3.7 [−6.3, −1.5] | 0.016 |
| wbs + humans | 0.864 | 0.667 | 0.942 | −1.0 [−3.2, +0.6] | 0.625 |
| rest | 0.869 | 0.667 | 0.948 | −0.5 [−2.3, +1.1] | 1.000 |
| rest + humans | 0.874 | 0.667 | 0.971 | +0.0 [+0.0, +0.0] | 1.000 |
| cirrus | 0.885 | 0.611 | 0.977 | +1.0 [−1.6, +3.6] | 0.688 |
| cirrus + humans | 0.885 | 0.611 | 0.983 | +1.0 [−1.0, +3.1] | 0.625 |
| wbs + rest | 0.864 | 0.667 | 0.954 | −1.0 [−2.7, +0.0] | 0.500 |
| **wbs + rest + humans** | **0.874** | **0.667** | 0.971 | – | – |
| wbs + rest + cirrus | 0.874 | 0.611 | 0.988 | +0.0 [−2.1, +2.2] | 1.000 |
| wbs + rest + cirrus + humans | 0.880 | 0.611 | 0.988 | +0.5 [−1.1, +2.4] | 1.000 |

## Decision

Keep `wbsearchentities` + REST search + the human search for bare names. CirrusSearch remains available (`search_apis=("wbs", "rest", "cirrus")`) as a recall option.

## Why

- **`wbsearchentities` alone is significantly worse** (−3.7 points, p = 0.016). This is the most common choice in tutorials.
- **The human search earns its request.** It adds between 0 and 2.6 points depending on the combination, and 1.0 point on the default pair. In retrieval, it lifts `wbsearchentities` from 0.919 to 0.942 and REST from 0.948 to 0.971.
- **Why not REST + humans alone?** It ties with the default on dev for one request less per query, so ADR-003 would pick it. But on the independent probe of 19 hard ambiguous mentions, REST alone found 17–18 and the union of both APIs found all 19, with "Curie" → Marie Curie found only by REST and other mentions only by `wbsearchentities`. As in ADR-008, the dev tie is broken by evidence that the cheaper option is weaker on harder text.
- **Why not CirrusSearch?**
  - It retrieves the most: adding it raises gold retrieval from 0.971 to 0.988.
  - It does not convert that into significant accuracy: +0.5 points at best, and every interval contains 0.
  - It lowers NIL recall from 0.667 to 0.611, because more namesakes become available to hard NILs.
  - It costs one more request per query.

  It is the first option to try on a corpus where retrieval is the bottleneck, such as KORE50.

## Consequences

Three search requests at most per bare-name mention, two otherwise. All three are cached per query (ADR-002).
