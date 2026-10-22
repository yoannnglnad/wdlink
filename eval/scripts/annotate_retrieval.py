"""Measure how hard each gold mention is for candidate retrieval, and store it in the JSONL.

Usage: python3 eval/scripts/annotate_retrieval.py eval/data/test.jsonl [more.jsonl ...]

For every mention with a gold qid, the surface form is sent unchanged to
  - wbsearchentities (language=en, uselang=en, type=item, limit=20)
  - REST /wikibase/v1/search/items (language=en, limit=20)
and these fields are written back in place on the mention:
  wbs_rank, rest_rank  1-based rank of the gold qid in each top 20, or null
  api_top1             gold qid is the first wbsearchentities result
  in_wbs20, in_rest20  gold qid is in the wbsearchentities / REST top 20
NIL mentions are left untouched. Gold labels are never changed.
Results depend on the live index: rerun to refresh, and note the date.
Dependencies: stdlib + requests.
"""

import json
import sys
import time

import requests

API = "https://www.wikidata.org/w/api.php"
REST = "https://www.wikidata.org/w/rest.php/wikibase/v1/search/items"
HEADERS = {"User-Agent": "wdlink-eval/0.1 (yoann@qomment.io)"}
PAUSE_S = 0.35  # 200 req/min limit, sequential calls
TOP_K = 20


def fetch(url, params):
    for attempt in range(5):
        r = requests.get(url, params=params, headers=HEADERS, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 5)) + attempt)
            continue
        r.raise_for_status()
        time.sleep(PAUSE_S)
        return r.json()
    raise RuntimeError("too many 429 responses")


def wbs_ids(surface):
    data = fetch(API, {"action": "wbsearchentities", "search": surface, "language": "en",
                       "uselang": "en", "type": "item", "limit": TOP_K, "format": "json",
                       "formatversion": 2})
    return [h["id"] for h in data.get("search", [])]


def rest_ids(surface):
    data = fetch(REST, {"q": surface, "language": "en", "limit": TOP_K})
    return [h["id"] for h in data.get("results", [])]


def rank(qid, ids):
    return ids.index(qid) + 1 if qid in ids else None


def annotate(path, cache):
    with open(path, encoding="utf-8") as f:
        docs = [json.loads(line) for line in f if line.strip()]
    stats = []
    for doc in docs:
        for m in doc["mentions"]:
            if m.get("qid") is None:
                continue
            s = m["surface"]
            if s not in cache:
                cache[s] = (wbs_ids(s), rest_ids(s))
            wbs, rest = cache[s]
            m["wbs_rank"] = rank(m["qid"], wbs)
            m["rest_rank"] = rank(m["qid"], rest)
            m["api_top1"] = m["wbs_rank"] == 1
            m["in_wbs20"] = m["wbs_rank"] is not None
            m["in_rest20"] = m["rest_rank"] is not None
            stats.append((doc["id"], m))
    with open(path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    return stats


def report(path, stats):
    n = len(stats)

    def count(pred):
        return sum(1 for _, m in stats if pred(m))

    def at(key, k):
        return count(lambda m: m[key] is not None and m[key] <= k)

    print(f"\n{path}: {n} linked mentions")
    print(f"  wbsearchentities  @1 {at('wbs_rank', 1):3}  @10 {at('wbs_rank', 10):3}  "
          f"@20 {at('wbs_rank', 20):3}")
    print(f"  REST search       @1 {at('rest_rank', 1):3}  @10 {at('rest_rank', 10):3}  "
          f"@20 {at('rest_rank', 20):3}")
    print(f"  union @20 {count(lambda m: m['in_wbs20'] or m['in_rest20']):3}")
    print(f"  absent from wbs top 20: {count(lambda m: not m['in_wbs20'])}, "
          f"from REST top 20: {count(lambda m: not m['in_rest20'])}, "
          f"from both: {count(lambda m: not m['in_wbs20'] and not m['in_rest20'])}")
    for did, m in stats:
        if not (m["in_wbs20"] and m["in_rest20"]):
            print(f"    {did:8} {m['surface']!r:28} {m['qid']:11} "
                  f"wbs={m['wbs_rank']} rest={m['rest_rank']}")


def main(paths):
    cache = {}
    for path in paths:
        report(path, annotate(path, cache))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
