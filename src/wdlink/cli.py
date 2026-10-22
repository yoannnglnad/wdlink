"""Command line: `wdlink link "text"` and `wdlink eval`."""

import argparse
import dataclasses
import json
import logging
import sys
from pathlib import Path

from wdlink.config import DEFAULT_PIPELINE, DEFAULT_RANKING


def _print_table(result: dict) -> None:
    rows = [("Mention", "Candidate concept", "Wikidata ID", "Score", "Confidence", "Decision")]
    for m in result["mentions"]:
        sel = m["selected"]
        rows.append(
            (
                m["mention"],
                sel["label"] if sel else "—",
                sel["qid"] if sel else "NIL",
                f"{sel['score']:.2f}" if sel else "—",
                f"{m['confidence']:.3f}",
                m["decision"],
            )
        )
    widths = [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print("  ".join(str(v).ljust(w) for v, w in zip(r, widths, strict=True)))


def cmd_link(args: argparse.Namespace) -> None:
    from wdlink.pipeline import Linker

    text = Path(args.file).read_text() if args.file else args.text
    cfg = DEFAULT_RANKING
    if args.no_graph:
        cfg = dataclasses.replace(cfg, beta=0.0, verbalise_graph=False)
    pcfg = dataclasses.replace(DEFAULT_PIPELINE, spacy_model=args.spacy_model)
    result, graph = Linker(pcfg=pcfg).link(text, cfg)
    _print_table(result)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\nJSON written to {args.json}")
    if args.ttl:
        graph.serialize(args.ttl, format="turtle")
        print(f"RDF/SKOS graph written to {args.ttl}")


def cmd_eval(args: argparse.Namespace) -> None:
    from wdlink.evaluate import main as eval_main

    eval_main(args)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="wdlink")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("link", help="link the terms of a text to Wikidata")
    p.add_argument("text", nargs="?")
    p.add_argument("--file")
    p.add_argument("--json", help="write the structured output to this file")
    p.add_argument("--ttl", help="write the local RDF/SKOS graph (Turtle) to this file")
    p.add_argument("--no-graph", action="store_true", help="baseline ranking without graph")
    p.add_argument("--spacy-model", default="en_core_web_sm")
    p.set_defaults(func=cmd_link)

    e = sub.add_parser("eval", help="evaluate baseline vs GraphRAG on the gold datasets")
    e.add_argument("--data-dir", default="eval/data")
    e.add_argument("--out", default="eval/results")
    e.add_argument("--spacy-model", default="en_core_web_sm")
    e.add_argument("--offline", action="store_true", help="use the Wikidata cache only")
    e.set_defaults(func=cmd_eval)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if args.command == "link" and not (args.text or args.file):
        parser.error("give a text or --file")
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
