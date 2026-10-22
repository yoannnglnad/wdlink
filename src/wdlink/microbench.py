"""Micro-benchmarks of the data-access and graph-representation choices.

- relations: one SPARQL query (item-valued truthy statements) vs wbgetentities with claims;
- types: explicit P31/P279{0..3} UNION vs the transitive path P31/P279*;
- graph: rdflib SKOS graph and its NetworkX view (SPARQL vs triple scan) vs NetworkX alone.
Network timings bypass the cache and are repeated; the median is reported.
"""

import argparse
import json
import statistics
import time
from pathlib import Path

import networkx as nx
import requests

from wdlink import config
from wdlink.evaluate import load
from wdlink.graph import CONCEPT_EDGES, build_graph, qid_of, to_networkx
from wdlink.pipeline import Linker
from wdlink.wikidata import WikidataClient, _relations_query, _types_query, _values

REPEATS = 3
SAMPLE_QIDS = 50
SAMPLE_DOCS = 6
CITY_CHECK = ["Q90", "Q270", "Q84", "Q64", "Q1490"]  # Paris, Warsaw, London, Berlin, Tokyo
ORGANIZATION = "Q43229"


def _get(session: requests.Session, params: dict) -> tuple[float, int]:
    start = time.perf_counter()
    resp = session.get(config.ACTION_API, params=params, timeout=config.HTTP_TIMEOUT_S)
    elapsed = time.perf_counter() - start
    resp.raise_for_status()
    return elapsed, len(resp.content)


def _sparql(session: requests.Session, query: str) -> tuple[float, int, list]:
    start = time.perf_counter()
    resp = session.post(
        config.SPARQL_ENDPOINT,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=config.SPARQL_TIMEOUT_S + 30,
    )
    elapsed = time.perf_counter() - start
    resp.raise_for_status()
    return elapsed, len(resp.content), resp.json()["results"]["bindings"]


def _repeat(client: WikidataClient, fn) -> list:
    runs = []
    for _ in range(REPEATS):
        client.limiter.wait()
        runs.append(fn())
    return runs


def _relations(client, session, qids) -> dict:
    sparql = _repeat(client, lambda: _sparql(session, _relations_query(qids)))
    params = {
        "action": "wbgetentities",
        "ids": "|".join(qids),
        "props": "claims",
        "format": "json",
        "formatversion": 2,
    }
    wbg = _repeat(client, lambda: _get(session, params))
    return {
        "sparql_s": statistics.median(r[0] for r in sparql),
        "sparql_bytes": sparql[0][1],
        "wbgetentities_s": statistics.median(r[0] for r in wbg),
        "wbgetentities_bytes": wbg[0][1],
    }


def _types(client, session, qids) -> dict:
    union = _repeat(client, lambda: _sparql(session, _types_query(qids)))
    star_query = f"""SELECT ?item ?type WHERE {{
  VALUES ?item {{ {_values(qids)} }}
  ?item wdt:P31/wdt:P279* ?type .
}}"""
    cities_query = f"""SELECT DISTINCT ?item WHERE {{
  VALUES ?item {{ {_values(CITY_CHECK)} }}
  ?item wdt:P31/wdt:P279* wd:{ORGANIZATION} .
}}"""
    try:
        star = _repeat(client, lambda: _sparql(session, star_query))
        client.limiter.wait()
        cities = [qid_of(r["item"]["value"]) for r in _sparql(session, cities_query)[2]]
        star_result = {
            "seconds": statistics.median(r[0] for r in star),
            "rows": len(star[0][2]),
            "cities_typed_organization": cities,
        }
    except requests.RequestException as err:
        star_result = {"error": type(err).__name__}
    bounded = client.get_types(CITY_CHECK)
    return {
        "union_depth3": {
            "seconds": statistics.median(r[0] for r in union),
            "rows": len(union[0][2]),
            "cities_typed_organization": [
                q for q in CITY_CHECK if ORGANIZATION in bounded[q]["types"]
            ],
        },
        "transitive_p279_star": star_result,
    }


def _graph(prepared) -> dict:
    build, scan, sparql, direct = [], [], [], []
    for p in prepared:
        start = time.perf_counter()
        g = build_graph(p.text, p.mentions, p.candidates, p.labels)
        build.append(time.perf_counter() - start)
        start = time.perf_counter()
        view = to_networkx(g)
        scan.append(time.perf_counter() - start)
        start = time.perf_counter()
        edges = sorted((qid_of(s), qid_of(o), qid_of(r)) for s, r, o in g.query(CONCEPT_EDGES))
        sparql.append(time.perf_counter() - start)
        assert edges == sorted(view.edges(data="prop")), "the two views must be identical"
        start = time.perf_counter()
        alone = nx.MultiDiGraph()
        for cands in p.candidates:
            for c in cands:
                for prop, v in c.relations:
                    alone.add_edge(c.qid, v, prop=prop)
        direct.append(time.perf_counter() - start)
    ms = lambda xs: 1000 * statistics.mean(xs)  # noqa: E731
    return {
        "rdf_build_ms": ms(build),
        "view_triple_scan_ms": ms(scan),
        "view_sparql_ms": ms(sparql),
        "direct_networkx_ms": ms(direct),
        "triples_per_doc": statistics.mean(len(p.graph) for p in prepared),
        "docs": len(prepared),
    }


def run(dev: Path, out_dir: Path) -> dict:
    client = WikidataClient()
    linker = Linker(client=client)
    docs = load(dev)[:SAMPLE_DOCS]
    prepared = [
        linker.prepare(d["text"], [(m["start"], m["end"]) for m in d["mentions"]]) for d in docs
    ]
    qids = list(dict.fromkeys(c.qid for p in prepared for cs in p.candidates for c in cs))
    qids = qids[:SAMPLE_QIDS]
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    out = {
        "sample_qids": len(qids),
        "relations": _relations(client, session, qids),
        "types": _types(client, session, qids),
        "graph": _graph(prepared),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "micro.json").write_text(json.dumps(out, indent=2))
    (out_dir / "micro.md").write_text(markdown(out))
    return out


def markdown(out: dict) -> str:
    r, t, g = out["relations"], out["types"], out["graph"]
    union, star = t["union_depth3"], t["transitive_p279_star"]
    if "seconds" in star:
        star_cell = f"{star['seconds']:.2f} s, {star['rows']} rows"
        star_orgs = ", ".join(star["cities_typed_organization"]) or "none"
    else:
        star_cell, star_orgs = star["error"], "–"
    union_orgs = ", ".join(union["cities_typed_organization"]) or "none"
    wbg_mb = r["wbgetentities_bytes"] / 1e6
    return f"""# Micro-benchmarks: data access and graph representation

Sample: {out["sample_qids"]} candidate QIDs from the first {g["docs"]} dev documents. Network
timings are medians of {REPEATS} cache-bypassing requests from one laptop; they vary with load.

## Fetching relations for {out["sample_qids"]} candidates

| method | median time | response size |
|---|---|---|
| SPARQL, item-valued truthy statements | {r["sparql_s"]:.2f} s | {r["sparql_bytes"] / 1e6:.2f} MB |
| `wbgetentities&props=claims` | {r["wbgetentities_s"]:.2f} s | {wbg_mb:.2f} MB |

## Type closure

Cities checked: Paris, Warsaw, London, Berlin, Tokyo; which ones end up typed "organization"?

| query | median time | cities typed organization (Q43229) |
|---|---|---|
| explicit UNION, P31/P279{{0..3}} | {union["seconds"]:.2f} s, {union["rows"]} rows | {union_orgs} |
| transitive `wdt:P31/wdt:P279*` | {star_cell} | {star_orgs} |

## Graph representation, per document (warm data)

| step | time |
|---|---|
| build the rdflib SKOS graph ({g["triples_per_doc"]:.0f} triples) | {g["rdf_build_ms"]:.1f} ms |
| NetworkX view by SPARQL over the rdflib graph | {g["view_sparql_ms"]:.1f} ms |
| NetworkX view by scanning the rdflib triples (used) | {g["view_triple_scan_ms"]:.1f} ms |
| NetworkX built directly from the statements, no RDF | {g["direct_networkx_ms"]:.1f} ms |

The two views are asserted to contain exactly the same edges.
"""


def main(args: argparse.Namespace) -> None:
    run(Path(args.dev), Path(args.out))
    print((Path(args.out) / "micro.md").read_text())
