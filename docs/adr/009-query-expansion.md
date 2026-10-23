# ADR-009 — Short-mention query expansion: off by default

**Status:** accepted (supersedes the initial design, where it was on) · **Evidence:** benchmark [`query_expansion`](../../eval/benchmarks/query_expansion.md) and a trigger count on dev.

## Context

`wbsearchentities` does not return Marie Curie (Q7186) in its top 20 for the query "Curie"; the REST search ranks it 17th. The first design therefore added *in-document expansion*: a short mention is also searched under any longer mention of the same document that contains it, so "Curie" after "Marie Curie" is also searched as "Marie Curie". Later, a second mechanism was added for bare names: a search restricted to humans (`haswbstatement:P31=Q5`, ADR-007), which returns Q7186 first for "Curie".

## Options measured

| Variant | CV accuracy | gold retrieved | Δ [95% CI] |
|---|---|---|---|
| with expansion | 0.874 | 0.971 | – |
| without expansion | 0.874 | 0.971 | +0.0 [+0.0, +0.0] |

The expansion fires on **2 of 191** dev mentions, and both triggers are wrong:

| Mention | Expanded to | Intended referent |
|---|---|---|
| "Jordan" | "Jordan River" | the country |
| "Kenya" | "Mount Kenya" | the country |

In both cases the ranking still chose the right item, so accuracy did not change. Meanwhile, 97 dev mentions are bare capitalised words and get the human search, which covers the surname case the expansion was built for.

## Decision

Turn the expansion off by default (`surname_expansion=False`) and keep it as an option.

## Why

- **No measured benefit.** With 2 triggers, the benchmark has no power either way. Under ADR-003, the simpler pipeline wins a tie.
- **Its motivating case is now handled elsewhere.** Human search finds the person behind a bare surname without depending on a longer mention being present.
- **Its triggers are mostly noise.** Short names are often *part* of a longer, different entity's name (a country inside a river or mountain name), so the expansion mostly adds wrong candidates.

## Consequences

- One fewer source of candidates per affected mention.
- A multi-word partial mention ("Hadron Collider" after "Large Hadron Collider") now relies on the search APIs alone. This case did not occur on dev; re-enable the option if a corpus shows it.
