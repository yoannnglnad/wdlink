"""End-to-end pipeline. `prepare` does the network-bound stages once; `link` ranks.

Evaluation re-ranks the same prepared document under several configurations (baseline,
GraphRAG, ablations), so retrieval and graph construction are never repeated.
"""

import logging
from dataclasses import dataclass, field

import networkx as nx
import numpy as np
from rdflib import Graph

from wdlink.config import DEFAULT_PIPELINE, DEFAULT_RANKING, PipelineConfig, RankingConfig
from wdlink.embed import Embedder
from wdlink.extract import extract_mentions, load_nlp, mentions_from_spans
from wdlink.graph import (
    annotate_links,
    build_graph,
    enrich,
    fact_text,
    graph_card,
    to_networkx,
    verbalise,
)
from wdlink.models import Candidate, LinkedMention, Mention
from wdlink.rank import GraphIndex, describe, rank
from wdlink.retrieve import basic_card, prerank, retrieve_candidates
from wdlink.wikidata import WikidataClient

log = logging.getLogger(__name__)


@dataclass
class Prepared:
    text: str
    mentions: list[Mention]
    all_candidates: list[list[str]]  # QIDs before pre-ranking (for retrieval recall@k)
    candidates: list[list[Candidate]]
    graph: Graph
    view: nx.MultiDiGraph
    index: GraphIndex
    labels: dict[str, str]
    sims_basic: list[np.ndarray] = field(default_factory=list)  # context vs label+description
    sims_graph: list[np.ndarray] = field(default_factory=list)  # context vs graph-augmented card
    cards: list[dict[str, str]] = field(default_factory=list)  # per mention: qid -> card
    pcfg: PipelineConfig = DEFAULT_PIPELINE


class Linker:
    def __init__(
        self,
        client: WikidataClient | None = None,
        embedder: Embedder | None = None,
        pcfg: PipelineConfig = DEFAULT_PIPELINE,
    ):
        self.pcfg = pcfg
        self.client = client or WikidataClient()
        self.embedder = embedder or Embedder(pcfg.embedding_model)
        self.nlp = load_nlp(pcfg.spacy_model)

    def prepare(self, text: str, spans: list[tuple[int, int]] | None = None) -> Prepared:
        pcfg = self.pcfg
        if spans is None:
            _, mentions = extract_mentions(text, self.nlp, pcfg)
        else:
            mentions = mentions_from_spans(text, spans, self.nlp, pcfg)
        found = retrieve_candidates(mentions, self.client, pcfg)
        # ordered by best rank over all APIs, so recall@k means 'in the top k of some API'
        all_qids = [[c.qid for c in sorted(cands, key=lambda c: c.search_rank)] for cands in found]
        kept = prerank(mentions, found, self.embedder, pcfg)
        neighbour_labels = enrich(kept, self.client, pcfg.exclude_housekeeping)
        graph = build_graph(text, mentions, kept, neighbour_labels, pcfg.all_relations)
        view = to_networkx(graph)
        index = GraphIndex(view, {c.qid for cands in kept for c in cands}, pcfg.all_relations)
        labels = {c.qid: c.label for cands in kept for c in cands} | neighbour_labels

        prepared = Prepared(text, mentions, all_qids, kept, graph, view, index, labels, pcfg=pcfg)
        for m, cands in zip(mentions, kept, strict=True):
            prepared.sims_basic.append(np.zeros(0))
            prepared.sims_graph.append(np.zeros(0))
            prepared.cards.append({})
            if not cands:
                continue
            # retrieve: verbalise each candidate's subgraph, keep the facts closest to the context
            facts = [verbalise(view, c.qid) for c in cands]
            texts = [fact_text(c, f) for c, fs in zip(cands, facts, strict=True) for f in fs]
            vectors = self.embedder.encode([m.context] + [basic_card(c) for c in cands] + texts)
            ctx, n = vectors[0], len(cands)
            fact_sims, offset, cards = vectors[1 + n :] @ ctx, 0, []
            for c, fs in zip(cands, facts, strict=True):
                sims = fact_sims[offset : offset + len(fs)]
                offset += len(fs)
                k = len(fs) if pcfg.facts_per_card is None else pcfg.facts_per_card
                top = sorted(np.argsort(-sims)[:k])
                cards.append(graph_card(c, [fs[i] for i in top]))
            # augment: the card with the retrieved facts is what the context is compared with
            prepared.cards[-1] = {c.qid: card for c, card in zip(cands, cards, strict=True)}
            prepared.sims_basic[-1] = vectors[1 : 1 + n] @ ctx
            prepared.sims_graph[-1] = self.embedder.encode(cards) @ ctx
        return prepared

    @staticmethod
    def rank(prepared: Prepared, cfg: RankingConfig = DEFAULT_RANKING) -> list[LinkedMention]:
        sims = prepared.sims_graph if cfg.verbalise_graph else prepared.sims_basic
        return rank(
            prepared.mentions, prepared.candidates, sims, prepared.index, prepared.labels, cfg
        )

    def link(
        self,
        text: str,
        cfg: RankingConfig = DEFAULT_RANKING,
        spans: list[tuple[int, int]] | None = None,
    ) -> tuple[dict, Graph]:
        prepared = self.prepare(text, spans)
        linked = self.rank(prepared, cfg)
        annotate_links(
            prepared.graph,
            text,
            linked,
            {"embedding_model": self.pcfg.embedding_model, **describe(cfg)},
        )
        return to_json(prepared, linked, cfg), prepared.graph


def _candidate_json(c: Candidate) -> dict:
    return {
        "qid": c.qid,
        "uri": f"http://www.wikidata.org/entity/{c.qid}",
        "label": c.label,
        "description": c.description,
        "score": round(c.score, 4),
    }


def to_json(prepared: Prepared, linked: list[LinkedMention], cfg: RankingConfig) -> dict:
    mentions = []
    for i, lm in enumerate(linked):
        best = lm.selected or (lm.candidates[0] if lm.candidates else None)
        mentions.append(
            {
                "mention": lm.mention.text,
                "start": lm.mention.start,
                "end": lm.mention.end,
                "source": lm.mention.source,
                "ner_label": lm.mention.ner_label,
                "decision": lm.decision,
                "selected": _candidate_json(lm.selected) if lm.selected else None,
                "confidence": round(lm.confidence, 4),
                "evidence": None
                if best is None
                else {
                    "features": best.features,
                    "graph_links": best.evidence.get("graph", [])[:5],
                    "card": prepared.cards[i].get(best.qid)
                    if cfg.verbalise_graph
                    else basic_card(best),
                    "search_queries": lm.mention.queries,
                },
                "alternatives": [
                    {**_candidate_json(c), "features": c.features}
                    for c in lm.candidates
                    if c is not lm.selected
                ][:5],
            }
        )
    return {
        "text": prepared.text,
        "mentions": mentions,
        "graph": {
            "triples": len(prepared.graph),
            "concepts": prepared.view.number_of_nodes(),
            "relations": prepared.view.number_of_edges(),
        },
        "config": describe(cfg),
    }
