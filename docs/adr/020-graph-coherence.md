# ADR-020 — Graph coherence: weighted pairwise relatedness, as an additive bonus

**Status:** accepted · **Evidence:** benchmark [`coherence`](../../eval/benchmarks/coherence.md), the dev error analysis in [`evidence.md`](../../eval/benchmarks/evidence.md), final evaluation (`eval/results/results.md`).

## Context

The core principle of the assignment is that "graph-based contextual reasoning helps determine which concept is the right one". Each candidate needs a score for how well it fits the readings of the *other* mentions, computed on the document's local graph. Collective entity-linking methods include:

- pairwise relatedness: the Milne–Witten measure (Milne & Witten, 2008), used by AIDA (Hoffart et al., 2011);
- random walks: personalised PageRank (Pershina et al., 2015);
- dense-subgraph search.

The fusion with the local score L can be additive, S = L + βG, or convex, S = (1−β)L + βG.

## Options measured

| Variant | CV accuracy | ambiguous | Δ vs ★ [95% CI] |
|---|---|---|---|
| no coherence (β = 0) | 0.869 | 0.788 | −0.5 [−1.7, +0.0] |
| naive: Jaccard overlap, unweighted mean over all candidates | 0.869 | 0.803 | −0.5 [−1.6, +0.0] |
| **★ weighted pairwise:** idf-weighted overlap, direct edges, p_L weights, best candidate per other mention | **0.874** | 0.803 | – |
| personalised PageRank on the local graph | 0.874 | 0.833 | +0.0 [−2.5, +2.6] |
| weighted, neighbours from *all* properties (2,837 triples/doc) | 0.874 | 0.803 | +0.0 [+0.0, +0.0] |
| weighted, convex fusion | 0.874 | 0.803 | +0.0 [+0.0, +0.0] |

The tuned β was 0.1 in 4 of 5 folds.

## Error analysis on dev

At θ = 0.38, the default system makes 23 errors on 191 mentions:

| Error type | Count | Can coherence fix it? |
|---|---|---|
| wrong candidate ranked first | 9 | yes |
| gold item not retrieved | 5 | no, it is a retrieval problem |
| gold item cut by the pre-ranking | 3 | no |
| hard NIL linked to a namesake | 6 | not as a bonus |

The coherence signal is present: 94 gold items have a direct statement linking them to another gold item of their document, and 31 more share weighted neighbours. But the local score already gets most of these mentions right. Coherence can only change the 9 ranking errors.

| β | Errors fixed | Correct answers broken |
|---|---|---|
| 0.1 | 2 | 0 |
| 0.3 | 2 | 1 ("Crick" pulled to a related entity) |
| 1.0 | 4 | 7 |

## Decision

Keep the **weighted pairwise** coherence as an **additive** bonus with a small β (0.1–0.2, tuned on dev).

## Why

- **Why coherence at all.** On dev, the gain is small (+0.5 points, interval touching 0) because the local score leaves only 9 fixable errors. Where text is more ambiguous, the gain grows. In the final evaluation, with thresholds tuned on all of dev, full GraphRAG (verbalised facts and coherence) beats the text-only baseline:
  - on the held-out test split, by +2.0 points (0.918 → 0.938), and by +5.2 on ambiguous mentions (0.816 → 0.868); McNemar gives 2 corrections against 0 regressions, p = 0.50;
  - on KORE50, the hardest benchmark of the three, by +4.9 points (0.518 → 0.567), with 11 corrections against 4 regressions, p = 0.12.

  Coherence alone (ablation A2, no verbalised facts) reaches 0.938 on test (+2.0) and 0.539 on KORE50 (+2.1). Every comparison points the same way, but none is significant on its own at these sample sizes.
- **Why pairwise rather than PageRank.**
  - Both reach the same accuracy. PageRank is slightly better on ambiguous mentions, but its interval spans −2.5 to +2.6.
  - The pairwise score is *explainable*: each bonus is traced to a named statement (Marie Curie —award received→ Nobel Prize in Physics) or to named shared neighbours, which the JSON evidence reports.
  - PageRank gives a stationary probability with no such trace.
- **Why the guards.** Naive coherence loses 0.5 points. It drops three of them:
  - the p_L weighting, so a wrong reading lends full support, as in the unit *curie* and the quantity *activity* supporting each other;
  - the best-candidate-per-mention rule, so every candidate of another mention counts;
  - the idf weighting, so a shared hub neighbour such as *France* counts as much as a rare one.
- **Why the whitelist of properties.** Neighbours from all properties give identical accuracy for 2.2× the triples. The whitelist keeps the graph small and its facts readable.
- **Why additive fusion.** Convex fusion ties on accuracy. But it rescales every score by (1−β), so a mention with no related mention loses score for no reason. Additive fusion leaves S = L when there is no graph evidence, so θ means the same thing for isolated and connected mentions.
- **Why a small β.** A large β trades errors: at β = 1 it fixes 4 and breaks 7. Related-but-wrong entities, such as a scientist's relatives or a city's districts, are close in the graph by construction.

## Consequences

- Coherence is a tie-breaker on top of a strong local score, not the main signal.
- Its value grows with ambiguity, and the evaluation reports it separately on ambiguous mentions and on KORE50.
