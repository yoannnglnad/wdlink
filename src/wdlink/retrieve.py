"""Stage 2 — candidate retrieval: maximise recall, do not decide.

Union of two search APIs (they fail on different mentions), housekeeping items removed,
then a cheap pre-ranking keeps the CANDIDATES_FOR_GRAPH most plausible ones for enrichment.
"""

from wdlink import config
from wdlink.config import DEFAULT_PIPELINE, PipelineConfig
from wdlink.embed import Embedder
from wdlink.features import name_similarity
from wdlink.models import Candidate, Mention
from wdlink.wikidata import WikidataClient


def retrieve_candidates(
    mentions: list[Mention], client: WikidataClient, pcfg: PipelineConfig = DEFAULT_PIPELINE
) -> list[list[Candidate]]:
    """All candidates of every mention, with terms (label, description, aliases)."""
    human_queries = [m.text for m in mentions if _is_bare_name(m)] if pcfg.human_search else []
    results = client.search_many(
        [q for m in mentions for q in m.queries], human_queries, pcfg.search_apis, pcfg.search_limit
    )
    per_mention: list[list[Candidate]] = []
    for m in mentions:
        found: dict[str, Candidate] = {}
        for query in m.queries:
            tag = "" if query == m.text else f"expansion:{query}"
            for api, hits in results[query].items():
                for rank, hit in enumerate(hits):
                    cand = found.setdefault(hit["id"], Candidate(qid=hit["id"]))
                    cand.search_rank = min(cand.search_rank, rank)
                    cand.sources.add(tag or api)
        per_mention.append(list(found.values()))

    terms = client.get_terms([c.qid for cands in per_mention for c in cands])
    for cands in per_mention:
        for c in cands:
            t = terms.get(c.qid, {})
            c.label, c.description, c.aliases = (
                t.get("label", ""),
                t.get("description", ""),
                t.get("aliases", []),
            )
        cands[:] = [
            c
            for c in cands
            if c.label and not (pcfg.exclude_housekeeping and _is_housekeeping(c.description))
        ]
    return per_mention


def _is_bare_name(m: Mention) -> bool:
    """A single capitalised word, e.g. a surname used alone ("Lincoln", "Turing")."""
    return not m.is_common_noun and m.text.isalpha() and m.text[:1].isupper()


def _is_housekeeping(description: str) -> bool:
    d = description.lower()
    return any(d.startswith(x) or d == x for x in config.EXCLUDED_DESCRIPTIONS)


def prerank(
    mentions: list[Mention],
    per_mention: list[list[Candidate]],
    embedder: Embedder,
    pcfg: PipelineConfig = DEFAULT_PIPELINE,
) -> list[list[Candidate]]:
    """Cheap ranking (no graph): context/description similarity, name match, search rank."""
    keep = pcfg.candidates_for_graph
    if pcfg.prerank == "search_rank":  # ablation: trust the search engines' order
        return [sorted(cands, key=lambda c: c.search_rank)[:keep] for cands in per_mention]
    w = config.PRERANK_WEIGHTS
    kept = []
    for m, cands in zip(mentions, per_mention, strict=True):
        if not cands:
            kept.append([])
            continue
        vectors = embedder.encode([m.context] + [basic_card(c) for c in cands])
        sims = vectors[1:] @ vectors[0]
        scored = sorted(
            zip(cands, sims, strict=True),
            key=lambda cs: (
                -(
                    w["txt"] * max(0.0, float(cs[1]))
                    + w["name"] * name_similarity(m.text, cs[0].label, cs[0].aliases)
                    + w["rank"] / (1 + cs[0].search_rank)
                )
            ),
        )
        kept.append([c for c, _ in scored[:keep]])
    return kept


def basic_card(c: Candidate) -> str:
    return f"{c.label}, {c.description}" if c.description else c.label
