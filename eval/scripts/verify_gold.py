"""Check a gold JSONL file: offsets, schema, and every gold QID against the live Wikidata API.

Usage: python3 eval/scripts/verify_gold.py eval/data/test.jsonl [more.jsonl ...]

Errors (exit code 1): bad JSON/schema, text[start:end] != surface, overlapping spans,
duplicate doc ids, QID missing or redirected, QID that is a disambiguation page /
category / template / list / name item.
Warnings (exit code 0): document length outside 15-60 words, NIL surface that exactly
matches an English label of some Wikidata item (worth a manual look).
Dependencies: stdlib + requests.
"""

import json
import re
import sys
import time

import requests

API = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "wdlink-eval/0.1 (yoann@qomment.io)"}
PAUSE_S = 0.6  # API limit is 200 req/min with a proper User-Agent
BATCH = 50  # wbgetentities maximum
BAD_P31 = {
    "Q4167410": "Wikimedia disambiguation page",
    "Q4167836": "Wikimedia category",
    "Q11266439": "Wikimedia template",
    "Q13406463": "Wikimedia list article",
    "Q101352": "family name",
    "Q202444": "given name",
}
QID_RE = re.compile(r"^Q[1-9][0-9]*$")


def call(params):
    params = {**params, "format": "json", "formatversion": 2}
    for attempt in range(5):
        r = requests.get(API, params=params, headers=HEADERS, timeout=60)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 5)) + attempt)
            continue
        r.raise_for_status()
        time.sleep(PAUSE_S)
        return r.json()
    raise RuntimeError("too many 429 responses")


def term(entity, key):
    """English term with `mul` fallback (many labels are stored only under `mul`)."""
    terms = entity.get(key, {})
    value = terms.get("en") or terms.get("mul")
    return value["value"] if value else ""


def aliases(entity):
    out = []
    for lang in ("en", "mul"):
        out += [a["value"] for a in entity.get("aliases", {}).get(lang, [])]
    return out


def p31_ids(entity):
    ids = []
    for claim in entity.get("claims", {}).get("P31", []):
        value = claim["mainsnak"].get("datavalue", {}).get("value", {})
        if isinstance(value, dict) and value.get("id"):
            ids.append(value["id"])
    return ids


def get_entities(ids, props):
    out = {}
    ids = sorted(set(ids))
    for i in range(0, len(ids), BATCH):
        data = call({
            "action": "wbgetentities",
            "ids": "|".join(ids[i:i + BATCH]),
            "props": props,
            "languages": "en|mul",
            "languagefallback": 1,
        })
        out.update(data.get("entities", {}))
    return out


def name_match(surface, entity):
    """exact / partial / none: does the surface look like the label or an alias?"""
    s = surface.casefold().rstrip("s")
    names = [n.casefold() for n in [term(entity, "labels"), *aliases(entity)] if n]
    if any(s == n.rstrip("s") for n in names):
        return "exact"
    if any(s in n or n in s for n in names):
        return "partial"
    return "none"


def load(path, errors, warnings):
    docs, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"{path}:{lineno}: invalid JSON ({e})")
                continue
            did, text = doc.get("id"), doc.get("text")
            if not isinstance(did, str) or not isinstance(text, str):
                errors.append(f"{path}:{lineno}: missing id or text")
                continue
            if did in seen:
                errors.append(f"{did}: duplicate id")
            seen.add(did)
            nwords = len(text.split())
            if not 15 <= nwords <= 60:
                warnings.append(f"{did}: {nwords} words (guideline: 15-60)")
            prev_end = -1
            for m in sorted(doc.get("mentions", []), key=lambda x: x.get("start", -1)):
                s, e, surf, qid = m.get("start"), m.get("end"), m.get("surface"), m.get("qid")
                if not (isinstance(s, int) and isinstance(e, int) and 0 <= s < e <= len(text)):
                    errors.append(f"{did}: bad offsets {s}-{e} for {surf!r}")
                    continue
                if text[s:e] != surf:
                    errors.append(f"{did}: text[{s}:{e}]={text[s:e]!r} != surface {surf!r}")
                if s < prev_end:
                    errors.append(f"{did}: overlapping mention at {s} ({surf!r})")
                prev_end = max(prev_end, e)
                if qid is not None and not (isinstance(qid, str) and QID_RE.match(qid)):
                    errors.append(f"{did}: malformed qid {qid!r} for {surf!r}")
                if not isinstance(m.get("ambiguous"), bool):
                    errors.append(f"{did}: 'ambiguous' must be a bool for {surf!r}")
            docs.append(doc)
    return docs


def check_nil(surfaces, warnings):
    for surface in sorted(set(surfaces)):
        data = call({"action": "wbsearchentities", "search": surface, "language": "en",
                     "uselang": "en", "type": "item", "limit": 10})
        hits = [h for h in data.get("search", [])
                if h.get("label", "").casefold() == surface.casefold()]
        for h in hits:
            warnings.append(f"NIL {surface!r} has an exact-label item {h['id']} "
                            f"({h.get('description', '')}): check it is not the referent")


def main(paths):
    errors, warnings = [], []
    docs = [d for p in paths for d in load(p, errors, warnings)]
    mentions = [(d["id"], m) for d in docs for m in d.get("mentions", [])]
    qids = [m["qid"] for _, m in mentions
            if isinstance(m.get("qid"), str) and QID_RE.match(m["qid"])]
    entities = get_entities(qids, "labels|descriptions|aliases|claims")
    class_ids = {c for q in qids for c in p31_ids(entities.get(q, {}))}
    class_labels = {k: term(v, "labels") for k, v in get_entities(class_ids, "labels").items()}

    rows = []
    for did, m in mentions:
        qid = m.get("qid")
        if qid is None:
            rows.append((did, m["surface"], "NIL", "", "", "", ""))
            continue
        ent = entities.get(qid)
        if ent is None or "missing" in ent:
            errors.append(f"{did}: {qid} ({m['surface']!r}) does not exist")
            continue
        if ent.get("id") != qid:
            errors.append(f"{did}: {qid} redirects to {ent.get('id')}, use the target")
        p31 = p31_ids(ent)
        for c in p31:
            if c in BAD_P31:
                errors.append(f"{did}: {qid} ({m['surface']!r}) is a {BAD_P31[c]} ({c})")
        p31_txt = ", ".join(f"{c} {class_labels.get(c, '')}".strip() for c in p31[:3])
        rows.append((did, m["surface"], qid, term(ent, "labels"), term(ent, "descriptions"),
                     p31_txt, name_match(m["surface"], ent)))

    check_nil([m["surface"] for _, m in mentions if m.get("qid") is None], warnings)

    widths = (9, 26, 11, 32, 50, 40, 7)
    header = ("doc", "surface", "qid", "label", "description", "P31", "name")
    print(" | ".join(h.ljust(w) for h, w in zip(header, widths, strict=True)))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(" | ".join(str(c)[:w].ljust(w) for c, w in zip(row, widths, strict=True)))

    n_nil = sum(1 for _, m in mentions if m.get("qid") is None)
    print(f"\n{len(docs)} docs, {len(mentions)} mentions ({n_nil} NIL), "
          f"{len(set(qids))} distinct QIDs checked")
    for w in warnings:
        print("WARNING", w)
    for e in errors:
        print("ERROR", e)
    print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
