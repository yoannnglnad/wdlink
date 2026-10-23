"""Offline tests of the evaluation and benchmarking code (metrics, tuning, data loading)."""

import dataclasses
import json

import numpy as np
import pytest
import requests
from rdflib.namespace import SKOS

from wdlink.config import DEFAULT_RANKING
from wdlink.evaluate import (
    a2kb_counts,
    a2kb_metrics,
    calibrate,
    expected_calibration_error,
    link_metrics,
    load,
    mcnemar,
    retrieval_metrics,
    tune,
)
from wdlink.graph import build_graph, concept, to_networkx
from wdlink.models import Candidate, Mention
from wdlink.pipeline import Prepared, to_json
from wdlink.rank import GraphIndex, rank
from wdlink.wikidata import DiskCache, WikidataClient, retry_after


def mention(text, start=0, ner=None):
    return Mention(text, start, start + len(text), "test", ner, text, False, [text])


def cand(qid, label="", relations=(), sitelinks=10):
    return Candidate(qid=qid, label=label or qid, relations=list(relations), sitelinks=sitelinks)


def prepared_doc(doc_id, mentions, per_mention, sims, gold):
    """A minimal (doc, Prepared, Prepared) triple, as produced by evaluate.prepare_all."""
    g = build_graph(doc_id, mentions, per_mention, {})
    view = to_networkx(g)
    prep = Prepared(
        text=doc_id,
        mentions=mentions,
        all_candidates=[[c.qid for c in cs] for cs in per_mention],
        candidates=per_mention,
        graph=g,
        view=view,
        index=GraphIndex(view, {c.qid for cs in per_mention for c in cs}),
        labels={},
        sims_basic=[np.array(s) for s in sims],
        sims_graph=[np.array(s) for s in sims],
        cards=[{} for _ in mentions],
    )
    doc = {
        "id": doc_id,
        "text": doc_id,
        "mentions": [
            {"start": m.start, "end": m.end, "surface": m.text, "qid": q}
            for m, q in zip(mentions, gold, strict=True)
        ],
    }
    return doc, prep, prep


# --- end-to-end matching -------------------------------------------------------------------------


def test_a2kb_strong_and_weak_matching():
    mentions = [mention("Paris", 0), mention("Texas", 10)]
    per_mention = [[cand("Q90", "Paris")], [cand("Q1439", "Texas")]]
    doc, prep, e2e = prepared_doc("d1", mentions, per_mention, [[0.9], [0.9]], ["Q90", "Q1439"])
    doc["mentions"][1]["start"] = 9  # gold span overlaps the prediction but is not identical
    m = a2kb_metrics(
        a2kb_counts([(doc, prep, e2e)], dataclasses.replace(DEFAULT_RANKING, nil_threshold=0.1))
    )
    assert m["strong_precision"] == 0.5 and m["strong_recall"] == 0.5
    assert m["weak_precision"] == 1.0 and m["weak_recall"] == 1.0


def test_a2kb_weak_precision_never_exceeds_one():
    """One predicted span overlapping two gold spans with the same QID is one true positive."""
    mentions = [mention("New York City", 0)]
    doc, prep, e2e = prepared_doc(
        "d2", mentions, [[cand("Q60", "New York City")]], [[0.9]], ["Q60"]
    )
    doc["mentions"] = [
        {"start": 0, "end": 8, "surface": "New York", "qid": "Q60"},
        {"start": 4, "end": 13, "surface": "York City", "qid": "Q60"},
    ]
    m = a2kb_metrics(
        a2kb_counts([(doc, prep, e2e)], dataclasses.replace(DEFAULT_RANKING, nil_threshold=0.1))
    )
    assert m["weak_precision"] == 1.0 and m["weak_recall"] == 1.0


def test_a2kb_ignores_predictions_on_unscored_spans():
    mentions = [mention("Paris", 0), mention("he", 10)]
    per_mention = [[cand("Q90", "Paris")], [cand("Q7186", "Marie Curie")]]
    doc, prep, e2e = prepared_doc("d3", mentions, per_mention, [[0.9], [0.9]], ["Q90", "Q7186"])
    doc["mentions"] = doc["mentions"][:1]
    doc["ignored_spans"] = [(10, 12)]  # e.g. a KORE50 pronoun annotation
    c = a2kb_counts([(doc, prep, e2e)], dataclasses.replace(DEFAULT_RANKING, nil_threshold=0.1))
    assert c["predicted_links"] == 1 and c["tp_strong"] == 1


# --- D2KB and retrieval metrics -------------------------------------------------------------------


def rows(*cases):
    return [
        {
            "doc": f"d{i}",
            "gold": g,
            "pred": p,
            "correct": g == p,
            "ambiguous": a,
            "isolated": False,
            "confidence": c,
            "all_candidates": cs,
            "ranking": rk,
        }
        for i, (g, p, a, c, cs, rk) in enumerate(cases)
    ]


def test_link_metrics_nil_precision_and_recall():
    r = rows(
        ("Q1", "Q1", True, 0.9, [], []),
        (None, None, False, 0.8, [], []),
        (None, "Q2", False, 0.7, [], []),
        ("Q3", None, False, 0.6, [], []),
    )
    m = link_metrics(r)
    assert m["accuracy"] == 0.5
    assert m["nil_recall"] == 0.5  # one of the two gold NILs predicted NIL
    assert m["nil_precision"] == 0.5  # one of the two predicted NILs is a gold NIL
    assert m["accuracy_ambiguous"] == 1.0


def test_retrieval_recall_counts_by_rank_order():
    r = rows(("Q1", "Q1", False, 1, ["Q9", "Q1"], ["Q1"]), ("Q2", "Q2", False, 1, ["Q2"], ["Q2"]))
    m = retrieval_metrics(r)
    assert m["retrieval_recall@1"] == 0.5 and m["retrieval_recall@5"] == 1.0
    assert m["after_prerank_recall"] == 1.0


def test_expected_calibration_error():
    perfect = rows(*[("Q1", "Q1", False, 1.0, [], [])] * 4)
    assert expected_calibration_error(perfect) == 0.0
    overconfident = rows(("Q1", "Q2", False, 0.95, [], []), ("Q1", "Q1", False, 0.95, [], []))
    assert expected_calibration_error(overconfident) == pytest.approx(0.45)


def test_mcnemar_exact_p_values():
    a = [{"correct": x} for x in [True, True, False, False]]
    b = [{"correct": x} for x in [False, False, True, False]]
    m = mcnemar(a, b)
    assert (m["only_baseline_correct"], m["only_graphrag_correct"]) == (2, 1)
    assert m["p_value"] == 1.0
    assert mcnemar(
        [{"correct": False}] * 11 + [{"correct": True}] * 4,
        [{"correct": True}] * 11 + [{"correct": False}] * 4,
    )["p_value"] == pytest.approx(0.1185, abs=1e-4)


# --- tuning and calibration -----------------------------------------------------------------------


def test_tune_lowers_threshold_to_keep_true_links():
    mentions = [mention("Paris", 0)]
    doc, prep, _ = prepared_doc("d4", mentions, [[cand("Q90", "Paris")]], [[0.2]], ["Q90"])
    cfg = tune([(doc, prep, None)], dataclasses.replace(DEFAULT_RANKING, beta=0.0))
    linked = rank(prep.mentions, prep.candidates, prep.sims_graph, prep.index, {}, cfg)
    assert linked[0].selected is not None


def test_calibrate_picks_a_temperature_from_the_grid():
    from wdlink.evaluate import TAU_GRID

    mentions = [mention("Paris", 0)]
    doc, prep, _ = prepared_doc(
        "d5", mentions, [[cand("Q90", "Paris"), cand("Q830149", "Paris")]], [[0.9, 0.3]], ["Q90"]
    )
    cfg = calibrate([(doc, prep, None)], DEFAULT_RANKING)
    assert cfg.confidence_temperature in TAU_GRID


# --- data loading and outputs ---------------------------------------------------------------------


def test_load_keeps_kore50_core_mentions_and_ignores_the_rest(tmp_path):
    doc = {
        "id": "k1",
        "text": "He met David.",
        "mentions": [
            {"start": 0, "end": 2, "surface": "He", "qid": "Q1", "kore50_core": False},
            {"start": 7, "end": 12, "surface": "David", "qid": "Q2", "kore50_core": True},
        ],
    }
    path = tmp_path / "kore50.jsonl"
    path.write_text(json.dumps(doc) + "\n")
    [loaded] = load(path)
    assert [m["surface"] for m in loaded["mentions"]] == ["David"]
    assert loaded["ignored_spans"] == [(0, 2)]


def test_json_output_for_nil_decisions():
    mentions = [mention("Zorblax", 0), mention("Qwxz", 10)]
    doc, prep, _ = prepared_doc(
        "d6", mentions, [[cand("Q2", "Earth")], []], [[0.05], []], [None, None]
    )
    cfg = dataclasses.replace(DEFAULT_RANKING, beta=0.0)
    out = to_json(
        prep, rank(prep.mentions, prep.candidates, prep.sims_graph, prep.index, {}, cfg), cfg
    )
    low, none = out["mentions"]
    assert low["decision"] == "nil_low_score" and low["selected"] is None
    assert low["alternatives"][0]["qid"] == "Q2"  # the near-miss is still reported
    assert none["decision"] == "nil_no_candidate" and none["evidence"] is None


# --- SKOS integrity -------------------------------------------------------------------------------


def test_related_is_not_added_inside_the_transitive_hierarchy():
    """S27: skos:related must be disjoint with skos:broaderTransitive, not only skos:broader."""
    a = cand("Q1", "GBIF Norway", [("P361", "Q2"), ("P101", "Q3")])
    b = cand("Q2", "GBIF", [("P31", "Q3")])
    c = cand("Q3", "data library")
    g = build_graph("d7", [mention("x"), mention("y", 5), mention("z", 9)], [[a], [b], [c]], {})
    assert (concept("Q1"), SKOS.related, concept("Q3")) not in g


# --- Wikidata client robustness -------------------------------------------------------------------


def test_retry_after_accepts_seconds_and_http_dates():
    resp = requests.Response()
    resp.headers["Retry-After"] = "7"
    assert retry_after(resp, 5) == 7
    resp.headers["Retry-After"] = "Wed, 21 Oct 2015 07:28:00 GMT"  # in the past
    assert retry_after(resp, 5) == 0
    resp.headers["Retry-After"] = "soon"
    assert retry_after(resp, 5) == 5


def test_truncated_body_is_retried(tmp_path, monkeypatch):
    from wdlink import config as cfg

    monkeypatch.setattr(cfg, "MIN_BACKOFF_S", 0)
    client = WikidataClient(cache_dir=tmp_path)
    bad, good = requests.Response(), requests.Response()
    bad.status_code, bad._content = 200, b'{"results": '
    good.status_code, good._content = 200, b'{"results": {"bindings": []}}'
    replies = iter([bad, good])
    monkeypatch.setattr(client.session, "request", lambda *_, **__: next(replies))
    assert client.sparql("SELECT * WHERE {}") == []


def test_cache_built_with_other_settings_is_refused(tmp_path):
    DiskCache(tmp_path, {"label_languages": "en|mul"})
    with pytest.raises(RuntimeError, match="label_languages"):
        DiskCache(tmp_path, {"label_languages": "en"})


def test_errors_of_external_benchmarks_stay_out_of_the_committed_file():
    from wdlink.evaluate import split_errors

    errors = [{"split": "dev"}, {"split": "test"}, {"split": "kore50_dywc"}]
    own, external = split_errors(errors)
    assert [e["split"] for e in own] == ["dev", "test"]
    assert [e["split"] for e in external] == ["kore50_dywc"]
