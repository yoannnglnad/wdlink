"""Benchmarks of every design choice, on the dev split only.

Protocol (the test split and KORE50 are never used here):
- each variant is prepared once (retrieval and graph), then ranked;
- its accuracy is a 5-fold cross-validation over dev documents: the NIL threshold (and beta,
  and the margin when relevant) are tuned on four folds and applied to the fifth, so variants
  are compared on predictions none of their own thresholds have seen;
- each variant is compared with the reference (current default) by a paired, document-level
  bootstrap of the accuracy difference (95% interval) and an exact McNemar test;
- speed is the warm-cache preparation time per document (models loaded, Wikidata cached), so it
  measures our own compute, not the network.

Run `wdlink bench <suite>`; results go to eval/benchmarks/<suite>.md and .json.
"""

import argparse
import dataclasses
import gc
import json
import logging
import random
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from wdlink.config import DEFAULT_PIPELINE, DEFAULT_RANKING, PipelineConfig, RankingConfig
from wdlink.evaluate import (
    a2kb_counts,
    a2kb_metrics,
    calibrate,
    d2kb,
    link_metrics,
    load,
    mcnemar,
    retrieval_metrics,
    tune,
)
from wdlink.pipeline import Linker
from wdlink.wikidata import WikidataClient

log = logging.getLogger(__name__)

FOLDS = 5
BOOTSTRAP_SAMPLES = 2000
MARGIN_GRID = (0.0, 0.01, 0.02, 0.03, 0.05, 0.08)
FIXED_TAU = 0.1  # the uncalibrated softmax temperature used before temperature scaling


@dataclass
class Variant:
    name: str
    pcfg: PipelineConfig = DEFAULT_PIPELINE
    rcfg: RankingConfig = DEFAULT_RANKING
    reference: bool = False
    tune_margin: bool = False
    calibrated: bool = False
    notes: dict = field(default_factory=dict)


def _p(**kw) -> PipelineConfig:
    return dataclasses.replace(DEFAULT_PIPELINE, **kw)


def _r(**kw) -> RankingConfig:
    return dataclasses.replace(DEFAULT_RANKING, **kw)


EMBEDDING_MODELS = {
    "sentence-transformers/all-MiniLM-L6-v2": "22M",
    "BAAI/bge-small-en-v1.5": "33M",
    "intfloat/e5-small-v2": "33M",
    "ibm-granite/granite-embedding-small-english-r2": "47M",
    "BAAI/bge-base-en-v1.5": "109M",
    "sentence-transformers/all-mpnet-base-v2": "109M",
}

SUITES: dict[str, dict] = {
    "spacy_model": {
        "question": "Which spaCy pipeline should extract the mentions?",
        "e2e": True,
        "timing": True,
        "variants": [
            Variant(m, _p(spacy_model=m), reference=m == "en_core_web_sm")
            for m in ("en_core_web_sm", "en_core_web_md", "en_core_web_lg", "en_core_web_trf")
        ],
    },
    "generic_filter": {
        "question": "Which Zipf-frequency cut-off removes generic one-word nouns?",
        "e2e": True,
        "variants": [
            Variant(
                "no filter" if z is None else f"Zipf < {z}",
                _p(generic_noun_max_zipf=z),
                reference=z == 4.5,
            )
            for z in (None, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)
        ],
    },
    "context_window": {
        "question": "How much text around a mention should be compared with the candidates?",
        "variants": [
            Variant(label, _p(context_window=w), reference=w == 1)
            for w, label in (
                (0, "sentence"),
                (1, "sentence ±1"),
                (2, "sentence ±2"),
                (None, "whole document"),
            )
        ],
    },
    "search_apis": {
        "question": "Which Wikidata search APIs should produce candidates?",
        "variants": [
            Variant(
                f"{'+'.join(apis)}{' + humans' if humans else ''}",
                _p(search_apis=apis, human_search=humans),
                reference=apis == ("wbs", "rest") and humans,
            )
            for apis in (
                ("wbs",),
                ("rest",),
                ("cirrus",),
                ("wbs", "rest"),
                ("wbs", "rest", "cirrus"),
            )
            for humans in (False, True)
        ],
    },
    "search_limit": {
        "question": "How many results should each search API return?",
        "variants": [
            Variant(f"top {k} per API", _p(search_limit=k), reference=k == 20)
            for k in (5, 10, 20, 50)
        ],
    },
    "query_expansion": {
        "question": "Should a short mention also be searched as the longer mention containing it?",
        "variants": [
            Variant("with expansion", _p(surname_expansion=True), reference=True),
            Variant("without expansion", _p(surname_expansion=False)),
        ],
    },
    "exclusions": {
        "question": "Should Wikimedia housekeeping items and scholarly articles be removed?",
        "variants": [
            Variant("excluded", _p(exclude_housekeeping=True), reference=True),
            Variant("kept", _p(exclude_housekeeping=False)),
        ],
    },
    "prerank": {
        "question": "How many candidates per mention should enter the graph, ranked how?",
        "timing": True,
        "variants": [
            Variant(
                f"top {k}, {mode}",
                _p(candidates_for_graph=k, prerank=mode),
                reference=k == 10 and mode == "mixed",
            )
            for mode in ("mixed", "search_rank")
            for k in (5, 10, 20, 30)
        ],
    },
    "embedding_model": {
        "question": "Which sentence-embedding model should compare contexts and candidates?",
        "timing": True,
        "variants": [
            Variant(
                name,
                _p(embedding_model=name),
                reference=name == "BAAI/bge-small-en-v1.5",
                notes={"parameters": size},
            )
            for name, size in EMBEDDING_MODELS.items()
        ],
    },
    "graph_facts": {
        "question": "How many verbalised graph facts should the candidate card carry?",
        "timing": True,
        "variants": [
            Variant("no facts (label + description)", rcfg=_r(verbalise_graph=False)),
            *[
                Variant(f"{k} closest facts", _p(facts_per_card=k), reference=k == 3)
                for k in (1, 3, 5)
            ],
            Variant("all facts (up to 24)", _p(facts_per_card=None)),
        ],
    },
    "entity_types": {
        "question": "How should entity types enter the local score?",
        "variants": [
            Variant("no type signal", rcfg=_r(types="none")),
            Variant("casing rule only", rcfg=_r(types="common_noun"), reference=True),
            Variant("spaCy sm NER labels", rcfg=_r(types="ner")),
            Variant("spaCy trf NER labels", _p(spacy_model="en_core_web_trf"), _r(types="ner")),
        ],
    },
    "coherence": {
        "question": "How should graph connections to the other mentions be scored?",
        "timing": True,
        "variants": [
            Variant("no coherence", rcfg=_r(beta=0.0)),
            Variant("naive (Jaccard, unweighted mean)", rcfg=_r(coherence="naive")),
            Variant("weighted pairwise (idf, p_L, max per mention)", reference=True),
            Variant("personalised PageRank", rcfg=_r(coherence="ppr")),
            Variant("weighted, all properties as neighbours", _p(all_relations=True)),
            Variant("weighted, convex fusion (1-β)L + βG", rcfg=_r(fusion="convex")),
        ],
    },
    "local_features": {
        "question": "Which local features and weights should form L?",
        "variants": [
            Variant("default (0.50 / 0.20 / 0.15 / 0.15)", reference=True),
            Variant("no popularity", rcfg=_r(use_popularity=False)),
            Variant("no name match", rcfg=_r(w_name=0.0)),
            Variant("text weight 0.70", rcfg=_r(w_txt=0.70)),
            Variant("text weight 0.30", rcfg=_r(w_txt=0.30)),
            Variant("popularity weight 0.30", rcfg=_r(w_pop=0.30)),
            Variant("fuzzy name match on aliases too", rcfg=_r(name_match="aliases")),
        ],
    },
    "nil_rule": {
        "question": "Should NIL depend on the score only, or also on the top1-top2 margin?",
        "variants": [
            Variant("score threshold θ", reference=True),
            Variant("θ + margin δ", tune_margin=True),
        ],
    },
    "calibration": {
        "question": "Is temperature scaling needed for the reported confidence?",
        "variants": [
            Variant(
                f"fixed softmax temperature {FIXED_TAU}", rcfg=_r(confidence_temperature=FIXED_TAU)
            ),
            Variant("temperature scaling (min NLL)", calibrated=True, reference=True),
        ],
    },
}


@dataclass
class Outcome:
    variant: Variant
    rows: list[dict]
    stats: dict
    counts: dict | None
    tuned: list[dict]


def cross_validate(prepared: list, v: Variant, e2e: bool) -> tuple[list[dict], dict | None, list]:
    """Rows predicted by fold-tuned configurations, summed A2KB counts, tuned parameters."""
    rows, counts, tuned = [], None, []
    for f in range(FOLDS):
        train = [p for i, p in enumerate(prepared) if i % FOLDS != f]
        held = [p for i, p in enumerate(prepared) if i % FOLDS == f]
        cfg = tune(train, v.rcfg, MARGIN_GRID if v.tune_margin else None)
        if v.calibrated:
            cfg = calibrate(train, cfg)
        tuned.append(
            {
                "beta": cfg.beta,
                "theta": cfg.nil_threshold,
                "margin": cfg.min_margin,
                "tau": cfg.confidence_temperature,
            }
        )
        rows += d2kb(held, cfg)
        if e2e:
            c = a2kb_counts(held, cfg)
            counts = c if counts is None else {k: counts[k] + c[k] for k in c}
    return rows, counts, tuned


def bootstrap_delta(rows: list[dict], ref: list[dict]) -> tuple[float, float, float]:
    """Paired document-level bootstrap of accuracy(rows) - accuracy(ref)."""
    by_doc: dict[str, list[tuple[bool, bool]]] = {}
    for a, b in zip(rows, ref, strict=True):
        by_doc.setdefault(a["doc"], []).append((a["correct"], b["correct"]))
    docs = list(by_doc)
    rng = random.Random(0)
    deltas = []
    for _ in range(BOOTSTRAP_SAMPLES):
        pairs = [p for d in rng.choices(docs, k=len(docs)) for p in by_doc[d]]
        deltas.append(sum(a - b for a, b in pairs) / len(pairs))
    deltas.sort()
    point = sum(a["correct"] - b["correct"] for a, b in zip(rows, ref, strict=True)) / len(rows)
    lo = deltas[int(0.025 * BOOTSTRAP_SAMPLES)]
    hi = deltas[int(0.975 * BOOTSTRAP_SAMPLES) - 1]
    return point, lo, hi


def prepare(linker: Linker, docs: list[dict], e2e: bool, timing: bool) -> tuple[list, dict]:
    prepared = []
    for doc in docs:
        spans = [(m["start"], m["end"]) for m in doc["mentions"]]
        gold = linker.prepare(doc["text"], spans)
        prepared.append((doc, gold, linker.prepare(doc["text"]) if e2e else None))
    stats = {
        "candidates_per_mention": statistics.mean(
            len(c) for _, g, _ in prepared for c in g.candidates
        ),
        "triples_per_doc": statistics.mean(len(g.graph) for _, g, _ in prepared),
    }
    if timing:  # second, warm pass: our compute only
        linker.embedder.cache.clear()
        start = time.perf_counter()
        for doc in docs:
            linker.prepare(doc["text"], [(m["start"], m["end"]) for m in doc["mentions"]])
        stats["ms_per_doc"] = 1000 * (time.perf_counter() - start) / len(docs)
        stats["power_source"] = power_source()
    return prepared, stats


def power_source() -> str:
    """'AC' or 'battery' on macOS (timings on battery with Low Power Mode are not comparable)."""
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    if "AC Power" in out.stdout:
        return "AC"
    return "battery" if "Battery Power" in out.stdout else "unknown"


def run_suite(name: str, dev_path: Path, out_dir: Path, offline: bool) -> dict:
    suite = SUITES[name]
    docs = load(dev_path)
    client = WikidataClient(offline=offline)
    e2e, timing = suite.get("e2e", False), suite.get("timing", False)
    prepared_by_pcfg: dict[PipelineConfig, tuple[list, dict]] = {}
    results: list[Outcome] = []
    for v in suite["variants"]:
        if v.pcfg not in prepared_by_pcfg:
            log.info("preparing %s", v.name)
            linker = Linker(client=client, pcfg=v.pcfg)
            prepared_by_pcfg[v.pcfg] = prepare(linker, docs, e2e, timing)
            del linker
            gc.collect()
        prepared, stats = prepared_by_pcfg[v.pcfg]
        rows, counts, tuned = cross_validate(prepared, v, e2e)
        results.append(Outcome(v, rows, stats, counts, tuned))
    ref = next(r for r in results if r.variant.reference)
    report = []
    for r in results:
        point, lo, hi = bootstrap_delta(r.rows, ref.rows)
        a2kb = a2kb_metrics(r.counts) if e2e and r.counts else {}
        report.append(
            {
                "variant": r.variant.name,
                "reference": r.variant.reference,
                **r.variant.notes,
                **link_metrics(r.rows),
                **retrieval_metrics(r.rows),
                **{f"a2kb_{k}": v for k, v in a2kb.items()},
                **r.stats,
                "delta_vs_reference": point,
                "delta_ci95": [lo, hi],
                "mcnemar_p": mcnemar(ref.rows, r.rows)["p_value"],
                "tuned_per_fold": r.tuned,
            }
        )
    out = {
        "suite": name,
        "question": suite["question"],
        "dev_docs": len(docs),
        "dev_mentions": len(ref.rows),
        "folds": FOLDS,
        "results": report,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps(out, indent=2, default=str))
    (out_dir / f"{name}.md").write_text(markdown(out, e2e, timing))
    return out


def _f(v, pct: bool = False) -> str:
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{100 * v:+.1f}" if pct else f"{v:.3f}"
    return str(v)


def markdown(out: dict, e2e: bool, timing: bool) -> str:
    cols = [
        ("accuracy", "CV accuracy"),
        ("accuracy_ambiguous", "ambiguous"),
        ("nil_recall", "NIL recall"),
        ("nil_precision", "NIL precision"),
        ("retrieval_recall@all", "gold retrieved"),
        ("after_prerank_recall", "gold kept"),
        ("candidates_per_mention", "cands/mention"),
    ]
    if e2e:
        cols += [
            ("a2kb_strong_precision", "A2KB P"),
            ("a2kb_strong_recall", "A2KB R"),
            ("a2kb_strong_f1", "A2KB F1"),
        ]
    if timing:
        cols += [("ms_per_doc", "ms/doc (warm)"), ("triples_per_doc", "triples/doc")]
    if out["suite"] == "calibration":
        cols += [("mean_confidence", "mean confidence"), ("ece", "ECE")]
    lines = [
        f"# Benchmark: {out['suite']}",
        "",
        f"**Question.** {out['question']}",
        "",
        f"Dev split, {out['dev_docs']} documents, {out['dev_mentions']} gold mentions, "
        f"{out['folds']}-fold cross-validation (thresholds tuned on the other folds). "
        "Δ = accuracy difference with the reference (★), in points, with its 95% paired "
        "document-level bootstrap interval; p = exact McNemar test.",
        "",
        "| variant | " + " | ".join(c[1] for c in cols) + " | Δ vs ★ [95% CI] | p |",
        "|---" * (len(cols) + 3) + "|",
    ]
    sources = sorted({r["power_source"] for r in out["results"] if "power_source" in r})
    if sources:
        lines.insert(
            4,
            f"Timings measured on: {', '.join(sources)} power"
            + (" — not comparable to AC timings." if "battery" in sources else ".")
            + "\n",
        )
    for r in out["results"]:
        name = f"★ {r['variant']}" if r["reference"] else r["variant"]
        if "parameters" in r:
            name += f" ({r['parameters']})"
        vals = []
        for key, _ in cols:
            v = r.get(key)
            vals.append(f"{v:.0f}" if key in ("ms_per_doc", "triples_per_doc") and v else _f(v))
        lo, hi = r["delta_ci95"]
        delta = (
            "–"
            if r["reference"]
            else f"{_f(r['delta_vs_reference'], True)} [{_f(lo, True)}, {_f(hi, True)}]"
        )
        p = "–" if r["reference"] else f"{r['mcnemar_p']:.3f}"
        lines.append(f"| {name} | " + " | ".join(vals) + f" | {delta} | {p} |")
    return "\n".join(lines) + "\n"


def main(args: argparse.Namespace) -> None:
    if args.suite == "micro":
        from wdlink.microbench import main as micro_main

        micro_main(args)
        return
    names = list(SUITES) if args.suite == "all" else args.suite.split(",")
    for name in names:
        start = time.time()
        out = run_suite(name, Path(args.dev), Path(args.out), args.offline)
        log.warning("suite %s done in %.0fs", name, time.time() - start)
        print((Path(args.out) / f"{name}.md").read_text())
        del out
        gc.collect()
