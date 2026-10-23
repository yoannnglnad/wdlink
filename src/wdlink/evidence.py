"""Measurements behind the factual claims of the ADRs that are not benchmark suites.

`wdlink bench evidence` writes eval/benchmarks/evidence.md. Everything is computed from the
installed packages, the dev split and the Wikidata cache, except the label check, which makes
one live API call (the point is to show what the API returns today).
"""

import argparse
import dataclasses
import json
import time
from collections import Counter, defaultdict
from importlib.util import find_spec
from pathlib import Path

import requests
from wordfreq import zipf_frequency

from wdlink import config
from wdlink.config import DEFAULT_PIPELINE, DEFAULT_RANKING
from wdlink.evaluate import d2kb, load
from wdlink.extract import load_nlp, mentions_from_spans
from wdlink.graph import build_graph, enrich, fact_text, graph_card, to_networkx, verbalise
from wdlink.pipeline import Linker
from wdlink.retrieve import basic_card, prerank, retrieve_candidates
from wdlink.wikidata import WikidataClient

SPACY_MODELS = ("en_core_web_sm", "en_core_web_md", "en_core_web_lg", "en_core_web_trf")
ZIPF_WORDS = (
    "radioactivity",
    "photosynthesis",
    "helium",
    "metadata",
    "physics",
    "protein",
    "planet",
    "research",
    "data",
)
NER_PROBES = {  # mention -> sentence; dev sentences are found by search, the last one is fixed
    "Lincoln": None,
    "Mind": None,
    "Higgs boson": None,
    "Freddie Mercury": (
        "Freddie Mercury sang with Queen; Mercury is also the closest planet to the Sun."
    ),
}
CREATIVE_WORK, PANDAS = "Q17537576", "Q15967387"
BETAS = (0.1, 0.3, 1.0)


def _dir_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


def spacy_models() -> list[dict]:
    rows = []
    for name in SPACY_MODELS:
        spec = find_spec(name)
        if spec is None or spec.submodule_search_locations is None:
            continue
        pkg = Path(next(iter(spec.submodule_search_locations)))
        meta_path = next(pkg.glob("*/meta.json"), None) or next(pkg.glob("meta.json"), None)
        meta = json.loads(meta_path.read_text()) if meta_path else {}
        rows.append(
            {
                "model": name,
                "size_mb": _dir_mb(pkg),
                "ner_f": meta.get("performance", {}).get("ents_f"),
            }
        )
    return rows


def stage_timings(docs: list[dict]) -> dict:
    """Warm-cache time per preparation stage, gold spans, default pipeline."""
    client = WikidataClient(offline=True)
    linker = Linker(client=client)
    pcfg = DEFAULT_PIPELINE
    linker.prepare(docs[0]["text"], [(m["start"], m["end"]) for m in docs[0]["mentions"]])
    linker.embedder.cache.clear()
    t: dict[str, float] = defaultdict(float)
    for doc in docs:
        spans = [(m["start"], m["end"]) for m in doc["mentions"]]
        s = time.perf_counter()
        mentions = mentions_from_spans(doc["text"], spans, linker.nlp, pcfg)
        t["spaCy (extraction, context)"] += time.perf_counter() - s
        s = time.perf_counter()
        found = retrieve_candidates(mentions, client, pcfg)
        t["retrieval (cached search + terms)"] += time.perf_counter() - s
        s = time.perf_counter()
        kept = prerank(mentions, found, linker.embedder, pcfg)
        t["pre-ranking (embeddings)"] += time.perf_counter() - s
        s = time.perf_counter()
        labels = enrich(kept, client)
        view = to_networkx(build_graph(doc["text"], mentions, kept, labels))
        t["enrichment + RDF graph + view"] += time.perf_counter() - s
        s = time.perf_counter()
        for m, cands in zip(mentions, kept, strict=True):
            if not cands:
                continue
            facts = [verbalise(view, c.qid) for c in cands]
            texts = [fact_text(c, f) for c, fs in zip(cands, facts, strict=True) for f in fs]
            linker.embedder.encode([m.context] + [basic_card(c) for c in cands] + texts)
            linker.embedder.encode(
                [graph_card(c, fs[:3]) for c, fs in zip(cands, facts, strict=True)]
            )
        t["fact and card embeddings"] += time.perf_counter() - s
    total = sum(t.values())
    return {k: {"ms_per_doc": 1000 * v / len(docs), "share": v / total} for k, v in t.items()}


def zipf() -> dict:
    return {w: round(zipf_frequency(w, config.LANGUAGE), 2) for w in ZIPF_WORDS}


def live_labels() -> dict:
    out = {}
    for langs in ("en", "en|mul"):
        r = requests.get(
            config.ACTION_API,
            timeout=config.HTTP_TIMEOUT_S,
            headers={"User-Agent": config.USER_AGENT},
            params={
                "action": "wbgetentities",
                "ids": "Q7186|Q42",
                "props": "labels",
                "languages": langs,
                "format": "json",
                "formatversion": 2,
            },
        )
        ents = r.json()["entities"]
        out[langs] = {q: sorted(e.get("labels", {})) for q, e in ents.items()}
    return out


def entity_facts(client: WikidataClient) -> dict:
    rel = client.get_relations(["Q7186"])["Q7186"]
    types = client.get_types([PANDAS, "Q90"])
    paris_labels = client.get_labels(types["Q90"]["types"])
    return {
        "Q7186_item_statements": len(rel),
        "Q7186_properties": len({p for p, _ in rel}),
        "pandas_is_creative_work": CREATIVE_WORK in types[PANDAS]["types"],
        "paris_depth3_classes": sorted(paris_labels.values()),
    }


def ner_labels(dev: list[dict]) -> dict:
    sentences = {}
    for mention, fixed in NER_PROBES.items():
        sentences[mention] = fixed or next(
            (d["text"] for d in dev if any(m["surface"] == mention for m in d["mentions"])), None
        )
    out = {}
    for model in ("en_core_web_sm", "en_core_web_trf"):
        nlp = load_nlp(model)
        for mention, text in sentences.items():
            if text is None:
                continue
            label = next((e.label_ for e in nlp(text).ents if mention in e.text), None)
            out.setdefault(mention, {})[model] = label
    return out


def enigma_cards(dev: list[dict]) -> dict:
    """Similarity of the gold Enigma machine with its context, without and with all facts."""
    doc = next(d for d in dev if any(m["surface"] == "Enigma" for m in d["mentions"]))
    linker = Linker(client=WikidataClient(offline=True))
    prep = linker.prepare(doc["text"], [(m["start"], m["end"]) for m in doc["mentions"]])
    i = next(k for k, m in enumerate(prep.mentions) if m.text == "Enigma")
    machine = next(c for c in prep.candidates[i] if c.qid == "Q150758")
    ctx = prep.mentions[i].context
    all_facts = graph_card(machine, verbalise(prep.view, machine.qid))
    return {
        "label_description": linker.embedder.similarity(ctx, basic_card(machine)),
        "all_facts": linker.embedder.similarity(ctx, all_facts),
        "three_facts": linker.embedder.similarity(ctx, prep.cards[i][machine.qid]),
    }


def coherence_analysis(dev: list[dict]) -> dict:
    """Dev error types, gold-to-gold graph connectivity and coherence fixes per beta."""
    linker = Linker(client=WikidataClient(offline=True))
    prepared = [
        (d, linker.prepare(d["text"], [(m["start"], m["end"]) for m in d["mentions"]]), None)
        for d in dev
    ]
    base = d2kb(prepared, dataclasses.replace(DEFAULT_RANKING, beta=0.0))
    flips = {}
    for beta in BETAS:
        rows = d2kb(prepared, dataclasses.replace(DEFAULT_RANKING, beta=beta))
        flips[beta] = {
            "fixed": sum(
                r["correct"] and not b["correct"] for r, b in zip(rows, base, strict=True)
            ),
            "broken": sum(
                b["correct"] and not r["correct"] for r, b in zip(rows, base, strict=True)
            ),
        }
    connectivity = Counter()
    for d, gp, _ in prepared:
        golds = [m["qid"] for m in d["mentions"] if m["qid"]]
        for q in golds:
            others = [o for o in golds if o != q and o in gp.index.neighbours]
            if q not in gp.index.neighbours:
                connectivity["gold not among kept candidates"] += 1
            elif not others:
                connectivity["no other gold item in the document"] += 1
            else:
                r = max(gp.index.relatedness(q, o, DEFAULT_RANKING)[0] for o in others)
                key = "direct statement" if r >= 1 else "shared neighbours" if r > 0 else "none"
                connectivity[key] += 1
    errors = Counter()
    for r in d2kb(prepared, DEFAULT_RANKING):
        if r["correct"]:
            continue
        if r["gold"] is None:
            errors["NIL linked to a namesake"] += 1
        elif r["gold"] not in r["all_candidates"]:
            errors["gold not retrieved"] += 1
        elif r["gold"] not in r["ranking"]:
            errors["gold cut by the pre-ranking"] += 1
        elif r["pred"] is None:
            errors["wrongly NIL"] += 1
        else:
            errors["wrong candidate ranked first"] += 1
    return {"flips": flips, "connectivity": dict(connectivity), "errors": dict(errors)}


def markdown(e: dict) -> str:
    lines = [
        "# Evidence for the factual claims of the ADRs",
        "",
        "Generated by `uv run wdlink bench evidence` from the installed packages, the dev "
        "split and the Wikidata cache (the label check is live).",
        "",
    ]
    lines += [
        "## spaCy pipelines (ADR-004)",
        "",
        "| model | size on disk | NER F1 (model meta) |",
        "|---|---|---|",
    ]
    lines += [f"| {m['model']} | {m['size_mb']:.0f} MB | {m['ner_f']:.3f} |" for m in e["spacy"]]
    lines += [
        "",
        "## Where preparation time goes (warm cache, dev, default pipeline)",
        "",
        "| stage | ms/doc | share |",
        "|---|---|---|",
    ]
    lines += [
        f"| {k} | {v['ms_per_doc']:.0f} | {100 * v['share']:.0f}% |"
        for k, v in e["timings"].items()
    ]
    lines += ["", "## Zipf frequencies (ADR-005)", "", "| word | Zipf |", "|---|---|"]
    lines += [f"| {w} | {z} |" for w, z in e["zipf"].items()]
    lines += [
        "",
        "## Labels returned by `wbgetentities` (ADR-007, live)",
        "",
        "| languages requested | Q7186 label languages | Q42 label languages |",
        "|---|---|---|",
    ]
    for langs, by_q in e["labels"].items():
        lines.append(f"| `{langs}` | {by_q.get('Q7186') or 'none'} | {by_q.get('Q42') or 'none'} |")
    f = e["entities"]
    lines += [
        "",
        "## Entity facts from the cache (ADR-013, ADR-016, ADR-019)",
        "",
        f"- Marie Curie (Q7186): {f['Q7186_item_statements']} item-valued truthy statements "
        f"under {f['Q7186_properties']} properties.",
        f"- pandas (Q15967387) is a subclass of creative work (Q17537576) within depth 3: "
        f"{f['pandas_is_creative_work']}.",
        f"- Paris (Q90) classes within P31/P279{{0..3}}: {', '.join(f['paris_depth3_classes'])}.",
        "",
        "## spaCy NER labels on probe mentions (ADR-019)",
        "",
        "| mention | en_core_web_sm | en_core_web_trf |",
        "|---|---|---|",
    ]
    for mention, by_model in e["ner"].items():
        lines.append(
            f"| {mention} | {by_model.get('en_core_web_sm')} | {by_model.get('en_core_web_trf')} |"
        )
    g = e["enigma"]
    lines += [
        "",
        "## Card dilution: the Enigma machine (ADR-018)",
        "",
        'Cosine between the context of "Enigma" (dev) and the gold item Q150758\'s card:',
        "",
        f"- label + description: {g['label_description']:.3f}",
        f"- with all verbalised facts: {g['all_facts']:.3f}",
        f"- with the 3 facts closest to the context: {g['three_facts']:.3f}",
        "",
    ]
    c = e["coherence"]
    lines += ["## Coherence on dev (ADR-020)", "", "Error types of the default system:", ""]
    lines += [f"- {k}: {v}" for k, v in c["errors"].items()]
    lines += [
        "",
        "Best graph relation from each gold item to another gold item of its document:",
        "",
    ]
    lines += [f"- {k}: {v}" for k, v in c["connectivity"].items()]
    lines += ["", "| β | errors fixed vs β = 0 | correct answers broken |", "|---|---|---|"]
    lines += [f"| {b} | {v['fixed']} | {v['broken']} |" for b, v in c["flips"].items()]
    return "\n".join(lines) + "\n"


def main(args: argparse.Namespace) -> None:
    dev = load(Path(args.dev))
    client = WikidataClient(offline=args.offline)  # cache first; Paris class labels may fetch
    evidence = {
        "spacy": spacy_models(),
        "timings": stage_timings(dev),
        "zipf": zipf(),
        "labels": {} if args.offline else live_labels(),
        "entities": entity_facts(client),
        "ner": ner_labels(dev),
        "enigma": enigma_cards(dev),
        "coherence": coherence_analysis(dev),
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidence.json").write_text(json.dumps(evidence, indent=2, default=str))
    (out / "evidence.md").write_text(markdown(evidence))
    print(markdown(evidence))
