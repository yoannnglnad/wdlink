"""Stage 5 — evaluation: retrieval recall@k, linking accuracy, baseline vs GraphRAG.

D2KB: gold mention spans are given, so linking is measured in isolation.
A2KB: end to end (our extraction + linking), strong (exact span) and weak (overlap) match.
Each system's NIL threshold (and beta for graph systems) is tuned on dev only, then the
same values are applied to test. Baseline vs GraphRAG is tested with an exact McNemar test.
"""

import argparse
import dataclasses
import json
import logging
import math
import time
from pathlib import Path

from wdlink.config import DEFAULT_RANKING, RankingConfig
from wdlink.pipeline import Linker, Prepared
from wdlink.wikidata import WikidataClient

log = logging.getLogger(__name__)

SYSTEMS: dict[str, RankingConfig] = {
    "baseline (text only)": dataclasses.replace(DEFAULT_RANKING, beta=0.0, verbalise_graph=False),
    "A1 graph verbalisation only": dataclasses.replace(DEFAULT_RANKING, beta=0.0),
    "A2 graph coherence only": dataclasses.replace(DEFAULT_RANKING, verbalise_graph=False),
    "A3 naive coherence": dataclasses.replace(DEFAULT_RANKING, coherence="naive"),
    "GraphRAG (full)": DEFAULT_RANKING,
}
BASELINE, GRAPHRAG = "baseline (text only)", "GraphRAG (full)"
THETA_GRID = [round(0.30 + 0.02 * i, 2) for i in range(26)]  # 0.30 .. 0.80
BETA_GRID = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
RECALL_KS = (1, 5, 10, 20, 40)


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def prepare_all(linker: Linker, docs: list[dict]) -> list[tuple[dict, Prepared, Prepared]]:
    out = []
    for i, doc in enumerate(docs, 1):
        spans = [(m["start"], m["end"]) for m in doc["mentions"]]
        gold_prep = linker.prepare(doc["text"], spans)
        e2e_prep = linker.prepare(doc["text"])
        out.append((doc, gold_prep, e2e_prep))
        log.info("prepared %d/%d %s", i, len(docs), doc["id"])
    return out


def predictions(prep: Prepared, cfg: RankingConfig) -> list[dict]:
    linked = Linker.rank(prep, cfg)
    return [
        {
            "pred": lm.selected.qid if lm.selected else None,
            "decision": lm.decision,
            "confidence": lm.confidence,
            "ranking": [c.qid for c in lm.candidates],
        }
        for lm in linked
    ]


def d2kb(prepared: list, cfg: RankingConfig) -> list[dict]:
    """One row per gold mention with the system's decision."""
    rows = []
    for doc, gold_prep, _ in prepared:
        preds = predictions(gold_prep, cfg)
        n_linkable = sum(1 for m in doc["mentions"] if m["qid"])
        for k, (gm, p) in enumerate(zip(doc["mentions"], preds, strict=True)):
            rows.append(
                {
                    "doc": doc["id"],
                    "surface": gm["surface"],
                    "gold": gm["qid"],
                    "ambiguous": gm.get("ambiguous", False),
                    "isolated": n_linkable <= 1,
                    "all_candidates": gold_prep.all_candidates[k],
                    "correct": p["pred"] == gm["qid"],
                    **p,
                }
            )
    return rows


def accuracy(rows: list[dict]) -> float | None:
    return sum(r["correct"] for r in rows) / len(rows) if rows else None


def link_metrics(rows: list[dict]) -> dict:
    in_kb = [r for r in rows if r["gold"]]
    nil = [r for r in rows if not r["gold"]]
    pred_nil = [r for r in rows if r["pred"] is None]
    return {
        "n": len(rows),
        "accuracy": accuracy(rows),
        "accuracy_in_kb": accuracy(in_kb),
        "accuracy_ambiguous": accuracy([r for r in in_kb if r["ambiguous"]]),
        "accuracy_unambiguous": accuracy([r for r in in_kb if not r["ambiguous"]]),
        "accuracy_isolated": accuracy([r for r in in_kb if r["isolated"]]),
        "accuracy_with_context": accuracy([r for r in in_kb if not r["isolated"]]),
        "nil_recall": accuracy(nil),
        "nil_precision": (sum(1 for r in pred_nil if not r["gold"]) / len(pred_nil))
        if pred_nil
        else None,
    }


def retrieval_metrics(rows: list[dict]) -> dict:
    in_kb = [r for r in rows if r["gold"]]
    out = {"n_in_kb": len(in_kb)}
    for k in RECALL_KS:
        out[f"retrieval_recall@{k}"] = sum(
            r["gold"] in r["all_candidates"][:k] for r in in_kb
        ) / len(in_kb)
    out["retrieval_recall@all"] = sum(r["gold"] in r["all_candidates"] for r in in_kb) / len(in_kb)
    out["after_prerank_recall"] = sum(r["gold"] in r["ranking"] for r in in_kb) / len(in_kb)
    for k in (1, 3, 5):
        out[f"ranked_recall@{k}"] = sum(r["gold"] in r["ranking"][:k] for r in in_kb) / len(in_kb)
    return out


def a2kb(prepared: list, cfg: RankingConfig) -> dict:
    """End-to-end micro P/R/F1 on linkable gold mentions (strong and weak span match)."""
    tp_strong = tp_weak = n_pred = n_gold = 0
    for doc, _, e2e_prep in prepared:
        preds = [
            (m.start, m.end, p["pred"])
            for m, p in zip(e2e_prep.mentions, predictions(e2e_prep, cfg), strict=True)
            if p["pred"]
        ]
        gold = [(g["start"], g["end"], g["qid"]) for g in doc["mentions"] if g["qid"]]
        n_pred, n_gold = n_pred + len(preds), n_gold + len(gold)
        for s, e, q in gold:
            tp_strong += any(ps == s and pe == e and pq == q for ps, pe, pq in preds)
            tp_weak += any(ps < e and s < pe and pq == q for ps, pe, pq in preds)
    out = {"predicted_links": n_pred, "gold_links": n_gold}
    for name, tp in (("strong", tp_strong), ("weak", tp_weak)):
        p = tp / n_pred if n_pred else 0.0
        r = tp / n_gold if n_gold else 0.0
        out[f"{name}_precision"], out[f"{name}_recall"] = p, r
        out[f"{name}_f1"] = 2 * p * r / (p + r) if p + r else 0.0
    return out


def tune(prepared: list, cfg: RankingConfig) -> RankingConfig:
    """Grid search on dev: NIL threshold, and beta when the system uses coherence."""
    betas = BETA_GRID if cfg.beta > 0 else [0.0]
    best, best_acc = cfg, -1.0
    for beta in betas:
        for theta in THETA_GRID:
            trial = dataclasses.replace(cfg, beta=beta, nil_threshold=theta)
            acc = accuracy(d2kb(prepared, trial))
            if acc > best_acc + 1e-9:
                best, best_acc = trial, acc
    return best


def mcnemar(rows_a: list[dict], rows_b: list[dict]) -> dict:
    """Exact two-sided McNemar test on paired per-mention correctness."""
    b = sum(1 for x, y in zip(rows_a, rows_b, strict=True) if x["correct"] and not y["correct"])
    c = sum(1 for x, y in zip(rows_a, rows_b, strict=True) if not x["correct"] and y["correct"])
    n = b + c
    p = 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2**n)
    return {"only_baseline_correct": b, "only_graphrag_correct": c, "p_value": p}


def api_top1(prepared: list, client: WikidataClient) -> dict:
    """Trivial reference: first wbsearchentities hit for the surface form, never NIL."""
    rows = []
    for doc, _, _ in prepared:
        for gm in doc["mentions"]:
            hits = client.search_wbs(gm["surface"])
            pred = hits[0]["id"] if hits else None
            rows.append(
                {
                    "gold": gm["qid"],
                    "pred": pred,
                    "correct": pred == gm["qid"],
                    "ambiguous": gm.get("ambiguous", False),
                    "isolated": False,
                }
            )
    return link_metrics(rows)


def _fmt(v) -> str:
    if v is None:
        return "–"
    return f"{v:.3f}" if isinstance(v, float) else str(v)


def markdown_report(results: dict) -> str:
    lines = ["# Evaluation results", ""]
    for split, res in results["splits"].items():
        lines += [
            f"## {split} ({res['docs']} documents, {res['retrieval']['n_in_kb']} in-KB mentions)",
            "",
        ]
        lines += ["### Candidate retrieval", "", "| metric | value |", "|---|---|"]
        lines += [f"| {k} | {_fmt(v)} |" for k, v in res["retrieval"].items()]
        cols = [
            "accuracy",
            "accuracy_in_kb",
            "accuracy_ambiguous",
            "accuracy_unambiguous",
            "accuracy_isolated",
            "accuracy_with_context",
            "nil_recall",
            "nil_precision",
        ]
        lines += [
            "",
            "### Linking (D2KB, gold mentions)",
            "",
            "| system | " + " | ".join(cols) + " |",
            "|---" * (len(cols) + 1) + "|",
        ]
        for name, m in res["d2kb"].items():
            lines.append(f"| {name} | " + " | ".join(_fmt(m.get(c)) for c in cols) + " |")
        lines += [
            "",
            "### End to end (A2KB, extraction + linking)",
            "",
            "| system | strong P | strong R | strong F1 | weak F1 |",
            "|---|---|---|---|---|",
        ]
        for name, m in res["a2kb"].items():
            lines.append(
                f"| {name} | {_fmt(m['strong_precision'])} | {_fmt(m['strong_recall'])} | "
                f"{_fmt(m['strong_f1'])} | {_fmt(m['weak_f1'])} |"
            )
        mc = res["mcnemar"]
        lines += [
            "",
            f"McNemar baseline vs GraphRAG: only baseline correct = {mc['only_baseline_correct']}, "
            f"only GraphRAG correct = {mc['only_graphrag_correct']}, exact p = {mc['p_value']:.4f}",
            "",
        ]
    lines += ["## Tuned parameters (dev)", "", "| system | nil_threshold | beta |", "|---|---|---|"]
    for name, p in results["tuned"].items():
        lines.append(f"| {name} | {p['nil_threshold']} | {p['beta']} |")
    lines += [
        "",
        f"Wikidata calls: {results['api_stats']}",
        f"Runtime: {results['runtime_s']:.0f} s",
    ]
    return "\n".join(lines) + "\n"


def main(args: argparse.Namespace) -> None:
    start = time.time()
    data_dir, out_dir = Path(args.data_dir), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = WikidataClient(offline=args.offline)
    linker = Linker(client=client, spacy_model=args.spacy_model)

    splits = {p.stem: load(p) for p in sorted(data_dir.glob("*.jsonl"))}
    prepared = {name: prepare_all(linker, docs) for name, docs in splits.items()}

    tuned = {name: tune(prepared["dev"], cfg) for name, cfg in SYSTEMS.items()}
    results = {
        "tuned": {n: {"nil_threshold": c.nil_threshold, "beta": c.beta} for n, c in tuned.items()},
        "splits": {},
    }
    errors = []
    for split, prep in prepared.items():
        rows = {name: d2kb(prep, cfg) for name, cfg in tuned.items()}
        results["splits"][split] = {
            "docs": len(prep),
            "retrieval": retrieval_metrics(rows[GRAPHRAG]),
            "d2kb": {"API top-1 (wbsearchentities)": api_top1(prep, client)}
            | {name: link_metrics(r) for name, r in rows.items()},
            "a2kb": {name: a2kb(prep, tuned[name]) for name in (BASELINE, GRAPHRAG)},
            "mcnemar": mcnemar(rows[BASELINE], rows[GRAPHRAG]),
        }
        for rb, rg in zip(rows[BASELINE], rows[GRAPHRAG], strict=True):
            if not (rb["correct"] and rg["correct"]):
                errors.append(
                    {
                        "split": split,
                        "doc": rg["doc"],
                        "surface": rg["surface"],
                        "gold": rg["gold"],
                        "baseline": rb["pred"],
                        "graphrag": rg["pred"],
                        "graphrag_decision": rg["decision"],
                        "gold_retrieved": rg["gold"] in rg["all_candidates"]
                        if rg["gold"]
                        else None,
                    }
                )
    results["api_stats"] = dict(client.stats)
    results["runtime_s"] = time.time() - start

    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    (out_dir / "errors.json").write_text(json.dumps(errors, indent=2, ensure_ascii=False))
    report = markdown_report(results)
    (out_dir / "results.md").write_text(report)
    print(report)
