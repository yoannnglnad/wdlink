"""Offline tests of retrieval, the Wikidata client parsing, and the benchmark cross-validation."""

import dataclasses
import time

from wdlink.bench import FOLDS, Variant, cross_validate
from wdlink.config import DEFAULT_PIPELINE
from wdlink.models import Mention
from wdlink.retrieve import retrieve_candidates
from wdlink.wikidata import RateLimiter, WikidataClient


def mention(text, start=0):
    return Mention(text, start, start + len(text), "test", None, text, False, [text])


class FakeClient:
    """search_many / get_terms with canned answers, recording which searches were asked."""

    def __init__(self, hits, terms):
        self.hits, self.terms, self.calls = hits, terms, []

    def search_many(self, queries, human_queries=(), apis=("wbs", "rest"), limit=20):
        self.calls.append((tuple(queries), tuple(human_queries), apis, limit))
        out = {q: {api: self.hits.get((api, q), [])[:limit] for api in apis} for q in queries}
        for q in human_queries:
            out.setdefault(q, {})["humans"] = self.hits.get(("humans", q), [])
        return out

    def get_terms(self, qids):
        return {q: self.terms.get(q, {}) for q in qids}


def test_retrieval_unions_apis_keeps_best_rank_and_drops_housekeeping():
    hits = {
        ("wbs", "Curie"): [{"id": "Q1"}, {"id": "Q2"}],
        ("rest", "Curie"): [{"id": "Q3"}, {"id": "Q1"}],
        ("humans", "Curie"): [{"id": "Q7186"}],
    }
    terms = {
        "Q1": {"label": "curie", "description": "unit of radioactivity"},
        "Q2": {"label": "Curie", "description": "family name"},  # housekeeping: removed
        "Q3": {"label": "Curie", "description": "crater on the Moon"},
        "Q7186": {"label": "Marie Curie", "description": "physicist"},
    }
    client = FakeClient(hits, terms)
    [cands] = retrieve_candidates([mention("Curie")], client, DEFAULT_PIPELINE)
    by_qid = {c.qid: c for c in cands}
    assert set(by_qid) == {"Q1", "Q3", "Q7186"}
    assert by_qid["Q1"].search_rank == 0 and by_qid["Q1"].sources == {"wbs", "rest"}
    assert client.calls[0][1] == ("Curie",)  # a bare capitalised word gets the human search


def test_human_search_can_be_disabled():
    client = FakeClient({}, {})
    pcfg = dataclasses.replace(DEFAULT_PIPELINE, human_search=False)
    retrieve_candidates([mention("Curie")], client, pcfg)
    assert client.calls[0][1] == ()


def test_types_and_relations_are_parsed_from_sparql_rows(tmp_path, monkeypatch):
    client = WikidataClient(cache_dir=tmp_path)
    wd = "http://www.wikidata.org/entity/"
    rows = {
        "types": [
            {
                "item": {"value": wd + "Q90"},
                "type": {"value": wd + "Q515"},
                "depth": {"value": "1"},
            },
            {
                "item": {"value": wd + "Q90"},
                "type": {"value": wd + "Q486972"},
                "depth": {"value": "2"},
            },
            {"item": {"value": wd + "Q90"}, "sitelinks": {"value": "366"}},
        ],
        "relations": [
            {
                "item": {"value": wd + "Q90"},
                "prop": {"value": "http://www.wikidata.org/prop/direct/P17"},
                "value": {"value": wd + "Q142"},
            },
        ],
    }
    monkeypatch.setattr(client, "sparql", lambda q: rows["types" if "?depth" in q else "relations"])
    t = client.get_types(["Q90"])["Q90"]
    assert t == {"p31": ["Q515"], "types": ["Q515", "Q486972"], "sitelinks": 366}
    assert client.get_relations(["Q90"])["Q90"] == [["P17", "Q142"]]
    assert client.cache.get("types", "Q90") == t  # cached per entity


def test_rate_limiter_spaces_requests():
    limiter = RateLimiter(per_minute=600)  # one slot every 0.1 s
    start = time.monotonic()
    for _ in range(4):
        limiter.wait()
    assert time.monotonic() - start >= 0.29


def test_cross_validation_never_scores_a_document_its_thresholds_saw(monkeypatch):
    from wdlink import bench

    docs = [({"id": f"d{i}", "mentions": []}, None, None) for i in range(12)]
    seen = []

    def fake_tune(train, cfg, margins=None):
        seen.append({d["id"] for d, _, _ in train})
        return cfg

    def fake_d2kb(held, cfg):
        held_ids = {d["id"] for d, _, _ in held}
        assert not held_ids & seen[-1]
        return [{"doc": i} for i in held_ids]

    monkeypatch.setattr(bench, "tune", fake_tune)
    monkeypatch.setattr(bench, "d2kb", fake_d2kb)
    rows, _, tuned = cross_validate(docs, Variant("x"), e2e=False)
    assert len(tuned) == FOLDS
    assert sorted(r["doc"] for r in rows) == sorted(f"d{i}" for i in range(12))
