"""Wikidata access: search, terms, types and relations, with an entity-keyed disk cache.

Etiquette (Wikimedia 2026): descriptive User-Agent, <= 200 req/min for UA-identified clients,
back off on 429 using Retry-After (min 5 s), batch 50 IDs per wbgetentities call.
Responses are cached per entity, not per batch, so changing batch composition never
invalidates the cache and evaluations are reproducible offline.
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests

from wdlink import config

log = logging.getLogger(__name__)

WD_ENTITY = "http://www.wikidata.org/entity/"
WD_DIRECT = "http://www.wikidata.org/prop/direct/"


class RateLimiter:
    """Spaces requests evenly so the per-minute budget is never exceeded (thread-safe)."""

    def __init__(self, per_minute: int):
        self.interval = 60.0 / per_minute
        self.lock = threading.Lock()
        self.next_slot = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            slot = max(now, self.next_slot)
            self.next_slot = slot + self.interval
        time.sleep(max(0.0, slot - now))


class DiskCache:
    """One JSON file per (kind, key). Writes are atomic."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, kind: str, key: str) -> Path:
        return self.root / kind / (hashlib.sha1(key.encode()).hexdigest() + ".json")

    def get(self, kind: str, key: str):
        path = self._path(kind, key)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def set(self, kind: str, key: str, value) -> None:
        path = self._path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value))
        os.replace(tmp, path)


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


class WikidataClient:
    def __init__(self, cache_dir: Path = config.CACHE_DIR, offline: bool = False):
        self.cache = DiskCache(cache_dir)
        self.offline = offline  # fail on cache miss instead of calling the network
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": config.USER_AGENT, "Accept-Encoding": "gzip, deflate"}
        )
        self.limiter = RateLimiter(config.MAX_REQUESTS_PER_MINUTE)
        self.stats = defaultdict(int)  # network calls and cache hits, reported by the evaluation

    # --- HTTP -----------------------------------------------------------------------------

    def _request(self, method: str, url: str, **kwargs) -> dict:
        if self.offline:
            raise RuntimeError(f"offline mode: cache miss for {url}")
        kwargs.setdefault("timeout", config.HTTP_TIMEOUT_S)
        backoff = config.MIN_BACKOFF_S
        for attempt in range(config.MAX_RETRIES + 1):
            self.limiter.wait()
            self.stats["http_calls"] += 1
            try:
                resp = self.session.request(method, url, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as err:
                # WDQS sometimes drops long-lived connections; treat it like a 503
                if attempt == config.MAX_RETRIES:
                    raise
                log.warning("%s on %s, retrying in %.0fs", type(err).__name__, url, backoff)
                time.sleep(backoff)
                backoff *= 2
                continue
            if resp.status_code == 200:
                return resp.json()
            retryable = resp.status_code == 429 or resp.status_code >= 500
            if not retryable or attempt == config.MAX_RETRIES:
                resp.raise_for_status()
            wait = float(resp.headers.get("Retry-After", backoff))
            log.warning("HTTP %s on %s, retrying in %.0fs", resp.status_code, url, wait)
            time.sleep(wait)
            backoff *= 2
        raise RuntimeError("unreachable")

    def _action(self, **params) -> dict:
        params.update(format="json", formatversion=2)
        data = self._request("GET", config.ACTION_API, params=params)
        if "error" in data:
            raise RuntimeError(f"Wikidata API error: {data['error']}")
        return data

    def sparql(self, query: str) -> list[dict]:
        data = self._request(
            "POST",
            config.SPARQL_ENDPOINT,
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=config.SPARQL_TIMEOUT_S,
        )
        self.stats["sparql_calls"] += 1
        return data["results"]["bindings"]

    def _cached_many(self, kind: str, keys: list[str], fetch) -> dict[str, Any]:
        """Return {key: value} for every key, fetching only cache misses (in batches)."""
        out, missing = {}, []
        for key in dict.fromkeys(keys):
            hit = self.cache.get(kind, key)
            if hit is None:
                missing.append(key)
            else:
                out[key] = hit
                self.stats[f"cache_hits_{kind}"] += 1
        if missing:
            fetched = fetch(missing)
            for key in missing:
                value = fetched.get(key, {})
                self.cache.set(kind, key, value)
                out[key] = value
        return out

    # --- Search ---------------------------------------------------------------------------

    def search_wbs(self, query: str, limit: int = config.SEARCH_LIMIT) -> list[dict]:
        """Prefix search on labels and aliases (all languages) via wbsearchentities."""
        key = f"{query}|{config.SEARCH_FETCH_LIMIT}"
        hits = self.cache.get("search_wbs", key)
        if hits is None:
            data = self._action(
                action="wbsearchentities",
                search=query,
                language=config.LANGUAGE,
                uselang=config.LANGUAGE,
                type="item",
                limit=config.SEARCH_FETCH_LIMIT,
            )
            hits = [{"id": r["id"]} for r in data.get("search", [])]
            self.cache.set("search_wbs", key, hits)
        return hits[:limit]

    def search_rest(self, query: str, limit: int = config.SEARCH_LIMIT) -> list[dict]:
        """Full-text search on labels and aliases via the Wikibase REST API."""
        key = f"{query}|{config.SEARCH_FETCH_LIMIT}"
        hits = self.cache.get("search_rest", key)
        if hits is None:
            data = self._request(
                "GET",
                config.REST_SEARCH_API,
                params={
                    "q": query,
                    "language": config.LANGUAGE,
                    "limit": config.SEARCH_FETCH_LIMIT,
                },
            )
            hits = [{"id": r["id"]} for r in data.get("results", [])]
            self.cache.set("search_rest", key, hits)
        return hits[:limit]

    def search_cirrus(
        self,
        query: str,
        limit: int = config.SEARCH_LIMIT,
        kind: str = "cirrus",
        statement_filter: str = "",
    ) -> list[dict]:
        """CirrusSearch full-text search (action=query&list=search), optionally filtered."""
        fetch = config.SEARCH_FETCH_LIMIT if kind == "cirrus" else limit
        key = f"{query}|{fetch}"
        hits = self.cache.get(f"search_{kind}", key)
        if hits is None:
            data = self._action(
                action="query",
                list="search",
                srsearch=f"{query} {statement_filter}".strip(),
                srlimit=fetch,
                srnamespace=0,
            )
            hits = [{"id": r["title"]} for r in data.get("query", {}).get("search", [])]
            self.cache.set(f"search_{kind}", key, hits)
        return hits[:limit]

    def search_humans(self, query: str, limit: int = config.HUMAN_SEARCH_LIMIT) -> list[dict]:
        """People matching the query: CirrusSearch restricted with haswbstatement:P31=Q5."""
        return self.search_cirrus(query, limit, "humans", "haswbstatement:P31=Q5")

    def search_many(
        self,
        queries: list[str],
        human_queries: Sequence[str] = (),
        apis: tuple[str, ...] = ("wbs", "rest"),
        limit: int = config.SEARCH_LIMIT,
    ) -> dict[str, dict[str, list[dict]]]:
        """Run the selected searches for every query (and the human search), in parallel."""
        search = {"wbs": self.search_wbs, "rest": self.search_rest, "cirrus": self.search_cirrus}
        unique = list(dict.fromkeys(queries))
        out: dict[str, dict[str, list[dict]]] = {q: {} for q in unique}
        with ThreadPoolExecutor(config.MAX_PARALLEL_REQUESTS) as pool:
            for api in apis:
                hits = pool.map(lambda q, f=search[api]: f(q, limit), unique)
                for q, h in zip(unique, hits, strict=True):
                    out[q][api] = h
            humans = list(dict.fromkeys(human_queries))
            for q, h in zip(humans, pool.map(self.search_humans, humans), strict=True):
                out.setdefault(q, {})["humans"] = h
        return out

    # --- Entity data ----------------------------------------------------------------------

    def get_terms(self, qids: list[str]) -> dict[str, dict]:
        """Label, description and aliases in English, falling back to `mul`."""

        def fetch(missing: list[str]) -> dict[str, dict]:
            out = {}
            for batch in _chunks(missing, config.WBGETENTITIES_BATCH):
                data = self._action(
                    action="wbgetentities",
                    ids="|".join(batch),
                    props="labels|descriptions|aliases",
                    languages=config.LABEL_LANGUAGES,
                    languagefallback=1,
                )
                for qid, ent in data.get("entities", {}).items():
                    out[qid] = _terms_from_entity(ent)
            return out

        return self._cached_many("terms", qids, fetch)

    def get_types(self, qids: list[str]) -> dict[str, dict]:
        """Direct P31, the P31/P279{0..3} (or P279{1..3} for classes) closure, and sitelinks."""

        def fetch(missing: list[str]) -> dict[str, dict]:
            out: dict[str, dict[str, Any]] = {
                q: {"p31": [], "types": [], "sitelinks": 0} for q in missing
            }
            for batch in _chunks(missing, config.SPARQL_VALUES_BATCH):
                for row in self.sparql(_types_query(batch)):
                    entry = out[_qid(row["item"]["value"])]
                    if "sitelinks" in row:
                        entry["sitelinks"] = int(row["sitelinks"]["value"])
                    if "type" in row:
                        t = _qid(row["type"]["value"])
                        if row["depth"]["value"] == "1" and t not in entry["p31"]:
                            entry["p31"].append(t)
                        if t not in entry["types"]:
                            entry["types"].append(t)
            return out

        return self._cached_many("types", qids, fetch)

    def get_relations(self, qids: list[str]) -> dict[str, list[list[str]]]:
        """All outgoing truthy statements whose value is an item: [[property, value_qid], ...]."""

        def fetch(missing: list[str]) -> dict[str, list]:
            out = {q: [] for q in missing}
            for batch in _chunks(missing, config.SPARQL_VALUES_BATCH // 2):
                for row in self.sparql(_relations_query(batch)):
                    prop = row["prop"]["value"].removeprefix(WD_DIRECT)
                    out[_qid(row["item"]["value"])].append([prop, _qid(row["value"]["value"])])
            return out

        return self._cached_many("relations", qids, fetch)

    def get_labels(self, qids: list[str]) -> dict[str, str]:
        """English (or `mul`) labels only, used to verbalise neighbours."""
        terms = self.get_terms(qids)
        return {q: t.get("label") or q for q, t in terms.items()}


def _terms_from_entity(ent: dict) -> dict:
    labels = ent.get("labels", {})
    descriptions = ent.get("descriptions", {})
    label = (labels.get(config.LANGUAGE) or labels.get("mul") or {}).get("value", "")
    description = (descriptions.get(config.LANGUAGE) or {}).get("value", "")
    aliases = []
    for lang in (config.LANGUAGE, "mul"):
        aliases += [a["value"] for a in ent.get("aliases", {}).get(lang, [])]
    return {"label": label, "description": description, "aliases": list(dict.fromkeys(aliases))}


def _values(qids: list[str]) -> str:
    return " ".join(f"wd:{q}" for q in qids)


def _types_query(qids: list[str]) -> str:
    # depth 1 = direct P31; the explicit UNION is ~30x faster than wdt:P31/wdt:P279* on WDQS
    instance_paths = ["wdt:P31"] + [
        "wdt:P31" + "/wdt:P279" * d for d in range(1, config.TYPE_DEPTH + 1)
    ]
    class_paths = ["/".join(["wdt:P279"] * d) for d in range(1, config.TYPE_DEPTH + 1)]
    branches = [
        f"{{ ?item {p} ?type . BIND({i + 1} AS ?depth) }}" for i, p in enumerate(instance_paths)
    ]
    branches += [
        f"{{ ?item {p} ?type . BIND({10 + i} AS ?depth) }}" for i, p in enumerate(class_paths)
    ]
    branches.append("{ ?item wikibase:sitelinks ?sitelinks }")
    return f"""SELECT ?item ?type ?depth ?sitelinks WHERE {{
  VALUES ?item {{ {_values(qids)} }}
  {" UNION ".join(branches)}
}}"""


def _relations_query(qids: list[str]) -> str:
    return f"""SELECT ?item ?prop ?value WHERE {{
  VALUES ?item {{ {_values(qids)} }}
  ?item ?prop ?value .
  FILTER(STRSTARTS(STR(?prop), "{WD_DIRECT}"))
  FILTER(isIRI(?value) && STRSTARTS(STR(?value), "{WD_ENTITY}Q"))
}}"""
