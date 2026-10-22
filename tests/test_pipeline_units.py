"""Offline unit tests: extraction, features, SKOS graph, ranking and Wikidata helpers."""

import dataclasses

import numpy as np
import pytest
from rdflib.namespace import SKOS

from wdlink.config import DEFAULT_RANKING
from wdlink.extract import extract_mentions
from wdlink.features import name_similarity, popularity, type_compatibility
from wdlink.graph import EX, WDT, build_graph, concept, to_networkx, verbalise
from wdlink.models import Candidate, Mention
from wdlink.rank import GraphIndex, rank
from wdlink.wikidata import DiskCache, WikidataClient, _terms_from_entity

EXAMPLE = (
    "Marie Curie conducted research on radioactivity in Paris and won the Nobel Prize in Physics."
)


def mention(text, start=0, ner=None, common=False):
    return Mention(text, start, start + len(text), "test", ner, text, common, [text])


def cand(qid, label="", types=(), relations=(), sitelinks=0, p31=()):
    return Candidate(
        qid=qid,
        label=label or qid,
        types=set(types),
        relations=list(relations),
        sitelinks=sitelinks,
        p31=list(p31),
    )


# --- extraction ---------------------------------------------------------------------------------


def test_extraction_offsets_and_filters():
    _, mentions = extract_mentions(EXAMPLE)
    texts = [m.text for m in mentions]
    assert texts == ["Marie Curie", "radioactivity", "Paris", "Nobel Prize in Physics"]
    for m in mentions:
        assert EXAMPLE[m.start : m.end] == m.text
    assert "research" not in texts  # generic noun dropped
    radio = mentions[1]
    assert radio.is_common_noun and radio.ner_label is None


def test_surname_expanded_with_full_name():
    _, mentions = extract_mentions("Marie Curie lived in Paris. Curie discovered polonium.")
    curie = next(m for m in mentions if m.text == "Curie")
    assert curie.queries == ["Curie", "Marie Curie"]


# --- local features -----------------------------------------------------------------------------


def test_name_similarity_levels():
    assert name_similarity("the Nobel Prize", "Nobel Prize", []) == 1.0
    assert name_similarity("Madame Curie", "Marie Curie", ["Madame Curie"]) == 0.9
    assert 0 < name_similarity("Curie", "Marie Curie", []) <= 0.8


def test_common_noun_rejects_works_and_people():
    m = mention("radioactivity", common=True)
    assert type_compatibility(m, cand("Q1081068", types={"Q134556", "Q2188189"})) == 0.0
    assert type_compatibility(m, cand("Q15967387", types={"Q7397", "Q17537576"})) == 1.0
    assert type_compatibility(m, cand("Q11448", types={"Q483247"})) == 1.0


def test_ner_type_compatibility():
    m = mention("Paris", ner="GPE")
    assert type_compatibility(m, cand("Q90", types={"Q515", "Q486972"})) == 1.0
    assert type_compatibility(m, cand("Q167646", types={"Q22988604"})) == 0.0
    assert type_compatibility(m, cand("Q1", types=set())) == 0.5


def test_popularity_is_log_scaled():
    assert popularity(cand("Q90", sitelinks=366), 366) == 1.0
    assert 0.6 < popularity(cand("Q830149", sitelinks=60), 366) < 0.75


# --- SKOS graph ---------------------------------------------------------------------------------


def _toy_graph():
    mentions = [mention("Marie Curie", 0, "PERSON"), mention("radioactivity", 20, common=True)]
    curie = cand(
        "Q7186",
        "Marie Curie",
        {"Q5"},
        [("P31", "Q5"), ("P101", "Q11448"), ("P166", "Q38104"), ("P1889", "Q11448")],
    )
    radio = cand("Q11448", "radioactivity", {"Q483247"}, [("P279", "Q483247"), ("P361", "Q11433")])
    unit = cand("Q229354", "curie", {"Q47574"}, [("P111", "Q317949")])
    per_mention = [[curie], [radio, unit]]
    labels = {
        "Q5": "human",
        "Q38104": "Nobel Prize in Physics",
        "Q483247": "phenomenon",
        "Q11433": "nuclear physics",
        "Q317949": "activity",
    }
    return mentions, per_mention, build_graph("doc", mentions, per_mention, labels)


def test_skos_mapping_keeps_instance_and_subclass_apart():
    _, _, g = _toy_graph()
    c, r = concept("Q7186"), concept("Q11448")
    assert (c, EX.broaderInstantive, concept("Q5")) in g
    assert (c, SKOS.broader, concept("Q5")) not in g  # never a bare skos:broader for P31
    assert (r, EX.broaderGeneric, concept("Q483247")) in g
    assert (r, EX.broaderPartitive, concept("Q11433")) in g
    assert (EX.broaderInstantive, None, SKOS.broader) in g  # declared as sub-property
    assert (c, SKOS.related, r) in g
    assert (c, WDT.P1889, r) not in g  # "different from" is never stored as evidence


def test_related_not_added_on_hierarchical_pair():
    _, _, g = _toy_graph()
    assert (concept("Q11448"), SKOS.related, concept("Q11433")) not in g  # P361 is partitive


def test_networkx_view_and_verbalisation():
    _, _, g = _toy_graph()
    view = to_networkx(g)
    assert view.has_edge("Q7186", "Q11448")
    facts = verbalise(view, "Q7186")
    assert ("instance of", "human") in facts
    assert ("award received", "Nobel Prize in Physics") in facts


# --- ranking ------------------------------------------------------------------------------------


def _rank(per_mention, mentions, sims, cfg=DEFAULT_RANKING):
    g = build_graph("doc", mentions, per_mention, {})
    index = GraphIndex(to_networkx(g), {c.qid for cs in per_mention for c in cs})
    labels = {c.qid: c.label for cs in per_mention for c in cs}
    return rank(mentions, per_mention, [np.array(s) for s in sims], index, labels, cfg)


def test_coherence_breaks_a_text_tie():
    mentions = [mention("Paris", 0, "GPE"), mention("Eiffel Tower", 10, "FAC")]
    paris_fr = cand("Q90", "Paris", {"Q515"}, sitelinks=100)
    paris_tx = cand("Q830149", "Paris", {"Q515"}, sitelinks=100)
    tower = cand("Q243", "Eiffel Tower", {"Q41176"}, [("P131", "Q90")], sitelinks=100)
    sims = [[0.5, 0.5], [0.8]]
    base = _rank(
        [[paris_fr, paris_tx], [tower]],
        mentions,
        sims,
        dataclasses.replace(DEFAULT_RANKING, beta=0.0),
    )
    assert base[0].candidates[0].score == base[0].candidates[1].score
    full = _rank([[paris_fr, paris_tx], [tower]], mentions, sims)
    assert full[0].selected.qid == "Q90"
    assert full[0].selected.evidence["graph"][0]["direct"] == [("P131", "in")]


def test_candidates_of_same_mention_never_support_each_other():
    mentions = [mention("Sorbonne", 0, "ORG")]
    a = cand("Q209842", "Sorbonne", {"Q43229"}, [("P527", "Q1")])
    b = cand("Q1", "Sorbonne University", {"Q43229"})
    linked = _rank([[a, b]], mentions, [[0.5, 0.5]])
    assert all(c.features["coherence"] == 0 for c in linked[0].candidates)


def test_weak_candidate_lends_little_support():
    """Circular evidence: a wrong candidate linked to another wrong one stays weak."""
    mentions = [mention("curie", 0, common=True), mention("radioactivity", 10, common=True)]
    unit = cand("Q229354", "curie", relations=[("P111", "Q317949")])
    activity = cand("Q317949", "activity")
    right = cand("Q11448", "radioactivity")
    linked = _rank([[unit], [right, activity]], mentions, [[0.6], [0.9, 0.2]])
    # the unit's only support is "activity", which has a low local score in its own mention
    assert linked[0].candidates[0].features["coherence"] < 0.1


def test_nil_when_best_score_is_low():
    mentions = [mention("Zorblax Institute", 0, "ORG")]
    linked = _rank([[cand("Q2", "Earth", {"Q3504248"})]], mentions, [[0.1]])
    assert linked[0].selected is None and linked[0].decision == "nil_low_score"


def test_no_candidate_is_nil():
    linked = _rank([[]], [mention("Qwxz", 0)], [[]])
    assert linked[0].decision == "nil_no_candidate"


# --- Wikidata helpers ---------------------------------------------------------------------------


def test_terms_fall_back_to_mul_label():
    ent = {
        "labels": {"mul": {"value": "Marie Curie"}},
        "descriptions": {"en": {"value": "physicist"}},
        "aliases": {"en": [{"value": "Madame Curie"}], "mul": [{"value": "Maria Skłodowska"}]},
    }
    t = _terms_from_entity(ent)
    assert t["label"] == "Marie Curie"
    assert t["aliases"] == ["Madame Curie", "Maria Skłodowska"]


def test_disk_cache_roundtrip(tmp_path):
    cache = DiskCache(tmp_path)
    assert cache.get("terms", "Q1") is None
    cache.set("terms", "Q1", {"label": "universe"})
    assert cache.get("terms", "Q1") == {"label": "universe"}


def test_offline_mode_never_calls_network(tmp_path):
    client = WikidataClient(cache_dir=tmp_path, offline=True)
    with pytest.raises(RuntimeError, match="offline"):
        client.search_wbs("Paris")


# --- variants and evaluation helpers ------------------------------------------------------------


def _tie_case():
    mentions = [mention("Paris", 0, "GPE"), mention("Eiffel Tower", 10, "FAC")]
    paris_fr = cand("Q90", "Paris", {"Q515"}, sitelinks=100)
    paris_tx = cand("Q830149", "Paris", {"Q515"}, sitelinks=100)
    tower = cand("Q243", "Eiffel Tower", {"Q41176"}, [("P131", "Q90")], sitelinks=100)
    return mentions, [[paris_fr, paris_tx], [tower]], [[0.5, 0.5], [0.8]]


def test_personalised_pagerank_prefers_the_connected_reading():
    mentions, per_mention, sims = _tie_case()
    linked = _rank(
        per_mention, mentions, sims, dataclasses.replace(DEFAULT_RANKING, coherence="ppr")
    )
    assert linked[0].selected.qid == "Q90"


def test_convex_fusion_formula():
    mentions, per_mention, sims = _tie_case()
    cfg = dataclasses.replace(DEFAULT_RANKING, fusion="convex", beta=0.5)
    linked = _rank(per_mention, mentions, sims, cfg)
    c = linked[0].candidates[0]
    assert c.score == pytest.approx(
        0.5 * c.features["local"] + 0.5 * c.features["coherence"], abs=1e-3
    )


def test_threshold_sweep_reproduces_select():
    """evaluate.decide must take exactly the decision rank.select takes."""
    from wdlink.evaluate import decide

    mentions, per_mention, sims = _tie_case()
    for theta in (0.2, 0.5, 0.9):
        for margin in (0.0, 0.05):
            cfg = dataclasses.replace(DEFAULT_RANKING, nil_threshold=theta, min_margin=margin)
            for lm in _rank(per_mention, mentions, sims, cfg):
                ranked = [(c.qid, c.score) for c in lm.candidates]
                expected = lm.selected.qid if lm.selected else None
                assert decide(ranked, theta, margin) == expected


def test_search_pages_are_cached_once_and_truncated(tmp_path):
    client = WikidataClient(cache_dir=tmp_path, offline=True)
    client.cache.set("search_wbs", "Paris|50", [{"id": f"Q{i}"} for i in range(1, 51)])
    assert [h["id"] for h in client.search_wbs("Paris", 3)] == ["Q1", "Q2", "Q3"]
    assert len(client.search_wbs("Paris", 20)) == 20


def test_bootstrap_of_identical_systems_is_zero():
    from wdlink.bench import bootstrap_delta

    rows = [{"doc": f"d{i % 4}", "correct": i % 3 == 0} for i in range(30)]
    assert bootstrap_delta(rows, rows) == (0.0, 0.0, 0.0)


def test_ppr_handles_a_mention_without_candidates():
    mentions = [mention("Qwxz", 0), *_tie_case()[0]]
    per_mention = [[], *_tie_case()[1]]
    sims = [[], *_tie_case()[2]]
    cfg = dataclasses.replace(DEFAULT_RANKING, coherence="ppr")
    linked = _rank(per_mention, mentions, sims, cfg)
    assert linked[0].decision == "nil_no_candidate"
