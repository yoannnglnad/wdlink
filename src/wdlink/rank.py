"""Stage 4 — GraphRAG-style candidate selection.

For each mention m and candidate c:
  L(m,c) = w_txt*s_txt + w_name*s_name + w_type*s_type + w_pop*s_pop      (local evidence)
  G(m,c) = mean over other mentions m' of max_{c' in C(m')} r(c,c') * p_L(c')   (coherence)
  S(m,c) = L(m,c) + beta * G(m,c)
s_txt compares the mention's context with the candidate "card"; with verbalise_graph the card
is augmented with facts retrieved from the local graph (the retrieval-augmented part).
r(c,c') is 1 for a direct Wikidata statement between the two candidates, otherwise the
idf-weighted overlap of their neighbourhoods (hubs such as "human" or "France" count little).
p_L(c') is a softmax over the other mention's candidates, so a weak candidate cannot lend
support (no circular evidence), and candidates of the same mention never support each other.
"""

import math
from dataclasses import asdict

import networkx as nx
import numpy as np

from wdlink import config
from wdlink.config import RankingConfig
from wdlink.features import name_similarity, popularity, type_compatibility
from wdlink.models import Candidate, LinkedMention, Mention

COHERENCE_EXCLUDED_PROPS = set(config.TYPE_PROPERTIES)  # "instance of human" is not evidence


def softmax(xs: list[float], temperature: float) -> np.ndarray:
    a = np.array(xs) / temperature
    a = np.exp(a - a.max())
    return a / a.sum()


class GraphIndex:
    """Neighbourhoods, idf weights and direct edges, read once from the NetworkX view."""

    def __init__(
        self, view: nx.MultiDiGraph, candidate_qids: set[str], all_relations: bool = False
    ):
        self.view = view
        self.neighbours: dict[str, set[str]] = {}
        for q in candidate_qids:
            out = set()
            if q in view:
                out = {
                    v
                    for _, v, d in view.out_edges(q, data=True)
                    if d["prop"] in config.RELATION_PROPERTIES
                    or (all_relations and d["prop"] not in COHERENCE_EXCLUDED_PROPS)
                }
            self.neighbours[q] = out
        df: dict[str, int] = {}
        for ns in self.neighbours.values():
            for x in ns:
                df[x] = df.get(x, 0) + 1
        n = max(1, len(candidate_qids))
        self.idf = {x: math.log(1 + n / d) for x, d in df.items()}
        self.mass = {q: sum(self.idf[x] for x in ns) for q, ns in self.neighbours.items()}
        self._memo: dict[tuple, tuple[float, dict]] = {}

    def direct_edges(self, a: str, b: str) -> list[tuple[str, str]]:
        """[(property, direction)] of statements a->b or b->a (negative properties never stored)."""
        edges = []
        for src, dst, direction in ((a, b, "out"), (b, a, "in")):
            if self.view.has_edge(src, dst):
                for d in self.view.get_edge_data(src, dst).values():
                    if d["prop"] not in COHERENCE_EXCLUDED_PROPS:
                        edges.append((d["prop"], direction))
        return edges

    def overlap(self, a: str, b: str, weighted: bool = True) -> tuple[float, list[str]]:
        shared = self.neighbours.get(a, set()) & self.neighbours.get(b, set())
        if not shared:
            return 0.0, []
        if not weighted:  # ablation: plain Jaccard
            union = self.neighbours[a] | self.neighbours[b]
            return len(shared) / len(union), sorted(shared)
        num = sum(self.idf[x] for x in shared)
        return num / math.sqrt(self.mass[a] * self.mass[b]), sorted(
            shared, key=lambda x: -self.idf[x]
        )

    def relatedness(self, a: str, b: str, cfg: RankingConfig) -> tuple[float, dict]:
        """Memoised: evaluation re-ranks the same document under many configurations."""
        key = (a, b, cfg.coherence, cfg.direct_edge_strength)
        if key not in self._memo:
            self._memo[key] = self._relatedness(a, b, cfg)
        return self._memo[key]

    def _relatedness(self, a: str, b: str, cfg: RankingConfig) -> tuple[float, dict]:
        if a == b:
            return 0.0, {}
        edges = self.direct_edges(a, b)
        ov, shared = self.overlap(a, b, weighted=cfg.coherence == "weighted")
        score = max(cfg.direct_edge_strength if edges else 0.0, ov)
        return score, {"direct": edges, "shared_neighbours": shared[:5], "overlap": round(ov, 4)}


def local_scores(
    mentions: list[Mention],
    per_mention: list[list[Candidate]],
    sims: list[np.ndarray],
    cfg: RankingConfig,
) -> list[np.ndarray]:
    weights = {
        "txt": cfg.w_txt,
        "name": cfg.w_name,
        "type": cfg.w_type if cfg.types != "none" else 0.0,
        "pop": cfg.w_pop if cfg.use_popularity else 0.0,
    }
    total = sum(weights.values())
    out = []
    for m, cands, sim in zip(mentions, per_mention, sims, strict=True):
        max_sl = max((c.sitelinks for c in cands), default=0)
        scores = []
        for c, s in zip(cands, sim, strict=True):
            f = {
                "txt": max(0.0, float(s)),
                "name": name_similarity(m.text, c.label, c.aliases, cfg.name_match),
                "type": type_compatibility(m, c, use_ner=cfg.types == "ner"),
                "pop": popularity(c, max_sl),
            }
            c.features = {k: round(v, 4) for k, v in f.items()}
            scores.append(sum(weights[k] * f[k] for k in f) / total)
        out.append(np.array(scores))
    return out


def coherence(
    per_mention: list[list[Candidate]],
    local: list[np.ndarray],
    index: GraphIndex,
    labels: dict[str, str],
    mention_texts: list[str],
    cfg: RankingConfig,
) -> list[np.ndarray]:
    probs = [softmax(list(L), cfg.softmax_temperature) if len(L) else L for L in local]
    out = []
    for i, cands in enumerate(per_mention):
        g = np.zeros(len(cands))
        for k, c in enumerate(cands):
            contributions, evidence = [], []
            for j, others in enumerate(per_mention):
                if j == i or not others:
                    continue
                if cfg.coherence == "naive":  # ablation A3: no softmax weights, no max per mention
                    rs = [index.relatedness(c.qid, o.qid, cfg)[0] for o in others]
                    contributions.append(float(np.mean(rs)))
                    continue
                best, best_ev = 0.0, None
                for o, p in zip(others, probs[j], strict=True):
                    r, ev = index.relatedness(c.qid, o.qid, cfg)
                    if r * p > best:
                        best, best_ev = (
                            r * p,
                            {
                                "mention": mention_texts[j],
                                "qid": o.qid,
                                "label": labels.get(o.qid, o.qid),
                                "relatedness": round(r, 4),
                                "weight": round(float(p), 4),
                                **ev,
                            },
                        )
                contributions.append(best)
                if best_ev and best > 0:
                    evidence.append(best_ev)
            g[k] = float(np.mean(contributions)) if contributions else 0.0
            c.evidence["graph"] = sorted(evidence, key=lambda e: -e["relatedness"] * e["weight"])
        out.append(g)
    return out


def ppr_coherence(
    per_mention: list[list[Candidate]],
    local: list[np.ndarray],
    index: GraphIndex,
    cfg: RankingConfig,
) -> list[np.ndarray]:
    """Alternative G: personalised PageRank (Pershina et al., 2015) over the local graph.

    The walk restarts on the other mentions' candidates, weighted by p_L; a candidate's
    stationary probability, scaled by the best candidate of its mention, is its coherence.
    """
    graph = nx.Graph()
    for u, v, d in index.view.edges(data=True):
        if d["prop"] not in COHERENCE_EXCLUDED_PROPS:
            graph.add_edge(u, v)
    probs = [softmax(list(L), cfg.softmax_temperature) if len(L) else L for L in local]
    out = []
    for i, cands in enumerate(per_mention):
        own = {c.qid for c in cands}
        seeds: dict[str, float] = {}
        for j, others in enumerate(per_mention):
            if j == i:
                continue
            for o, p in zip(others, probs[j], strict=True):
                if o.qid in graph and o.qid not in own:
                    seeds[o.qid] = seeds.get(o.qid, 0.0) + float(p)
        scores = np.zeros(len(cands))
        if seeds:
            pr = nx.pagerank(graph, alpha=config.PPR_DAMPING, personalization=seeds)
            scores = np.array([pr.get(c.qid, 0.0) for c in cands])
            if scores.size and scores.max() > 0:
                scores = scores / scores.max()
        for c in cands:
            c.evidence["graph"] = []
        out.append(scores)
    return out


def select(
    mentions: list[Mention],
    per_mention: list[list[Candidate]],
    local: list[np.ndarray],
    coh: list[np.ndarray] | None,
    cfg: RankingConfig,
) -> list[LinkedMention]:
    results = []
    for i, (m, cands) in enumerate(zip(mentions, per_mention, strict=True)):
        if not cands:
            results.append(LinkedMention(m, [], None, 1.0, "nil_no_candidate"))
            continue
        g = coh[i] if coh is not None else np.zeros(len(cands))
        for c, l_score, g_score in zip(cands, local[i], g, strict=True):
            c.features["local"] = round(float(l_score), 4)
            c.features["coherence"] = round(float(g_score), 4)
            if cfg.fusion == "convex":
                c.score = float((1 - cfg.beta) * l_score + cfg.beta * g_score)
            else:
                c.score = float(l_score + cfg.beta * g_score)
        ranked = sorted(cands, key=lambda c: -c.score)
        top = ranked[0]
        second = ranked[1].score if len(ranked) > 1 else -math.inf
        p = softmax([c.score for c in ranked] + [cfg.nil_threshold], cfg.confidence_temperature)
        if top.score < cfg.nil_threshold:
            results.append(LinkedMention(m, ranked, None, float(p[-1]), "nil_low_score"))
        elif top.score - second < cfg.min_margin:
            results.append(LinkedMention(m, ranked, None, float(p[-1]), "nil_ambiguous"))
        else:
            results.append(LinkedMention(m, ranked, top, float(p[0]), "linked"))
    return results


def rank(
    mentions: list[Mention],
    per_mention: list[list[Candidate]],
    sims: list[np.ndarray],
    index: GraphIndex,
    labels: dict[str, str],
    cfg: RankingConfig,
) -> list[LinkedMention]:
    local = local_scores(mentions, per_mention, sims, cfg)
    coh = None
    if cfg.beta > 0 and cfg.coherence == "ppr":
        coh = ppr_coherence(per_mention, local, index, cfg)
    elif cfg.beta > 0:
        coh = coherence(per_mention, local, index, labels, [m.text for m in mentions], cfg)
    else:
        for cands in per_mention:
            for c in cands:
                c.evidence["graph"] = []
    return select(mentions, per_mention, local, coh, cfg)


def describe(cfg: RankingConfig) -> dict:
    return {k: v for k, v in asdict(cfg).items() if k != "extra"}
