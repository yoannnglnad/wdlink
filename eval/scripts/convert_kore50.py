"""Convert KORE 50^DYWC (Wikidata NIF/Turtle) to the eval JSONL format.

Source: KORE 50^DYWC (Noullet, Mix, Faerber, LREC 2020), file KORE_50_Wikidata.ttl
from kore50-lrec2020.zip. Stdlib only; parses the Turtle subset used by the file.

Usage: python3 -I convert_kore50.py <KORE_50_Wikidata.ttl> <output.jsonl> [<kore50-nif-dbpedia.ttl>]

With the original KORE50 NIF file (3rd argument), each mention gets "kore50_core": true when
its (doc, start, end, surface) matches an original KORE50 mention; core mentions are
"ambiguous": true / note "KORE50-DYWC core", the others (pronouns, articles, common nouns
added by DYWC) "ambiguous": false / note "KORE50-DYWC extra".
"""

import json
import re
import sys
from collections import Counter

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
NIF = "http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#"
ITSRDF = "http://www.w3.org/2005/11/its/rdf#"
NIF_CONTEXT = NIF + "Context"
IS_STRING = NIF + "isString"
REF_CONTEXT = NIF + "referenceContext"
BEGIN = NIF + "beginIndex"
END = NIF + "endIndex"
ANCHOR = NIF + "anchorOf"
TA_IDENT_REF = ITSRDF + "taIdentRef"

# Wikidata entity IRI. One annotation in the release uses the page form /wiki/Qn
# instead of /entity/Qn; both name the same item.
WIKIDATA_RE = re.compile(r"^https?://(?:www\.)?wikidata\.org/(entity|wiki)/(Q[1-9][0-9]*)$")
NIL_RE = re.compile(r"notInWiki|/NIL$|/nil$|#NIL$", re.IGNORECASE)
DOC_ID_RE = re.compile(r"/(CEL\d+)#char=")
NOTE = "KORE50-DYWC"
# DYWC renumbers the 50 documents CEL01..CEL50 in the original KORE50 order. Verified by
# exact text match against kore50-nif-dbpedia.ttl (same zip): blocks of 10 per category.
KORE50_CATEGORIES = ["CEL", "MUS", "BUS", "SPO", "POL"]
# Original KORE50 context IRIs end in "/MUS01#char=0," (or "/MUS01" for one context).
KORE50_DOC_RE = re.compile(r"/([A-Z]{3}\d\d)(?:#|$)")


def kore50_doc_id(dywc_id):
    n = int(dywc_id[3:])
    return f"{KORE50_CATEGORIES[(n - 1) // 10]}{(n - 1) % 10 + 1:02d}"

TOKEN_RE = re.compile(
    r"""
    (?P<ws>\s+|\#[^\n]*)
  | (?P<iri><[^<>"{}|^`\\\s]*>)
  | (?P<string>"(?:[^"\\\n]|\\.)*")
  | (?P<dtype>\^\^)
  | (?P<lang>@[a-zA-Z]+(?:-[a-zA-Z0-9]+)*)
  | (?P<pname>[A-Za-z][\w\-]*:[\w\-.]*|:[\w\-.]*)
  | (?P<number>[+-]?\d+)
  | (?P<punct>[;,.])
  | (?P<a>a(?=[\s<]))
    """,
    re.VERBOSE,
)
ESCAPES = {"t": "\t", "b": "\b", "n": "\n", "r": "\r", "f": "\f", '"': '"', "'": "'", "\\": "\\"}


def unescape(body):
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        n = body[i + 1]
        if n == "u":
            out.append(chr(int(body[i + 2 : i + 6], 16)))
            i += 6
        elif n == "U":
            out.append(chr(int(body[i + 2 : i + 10], 16)))
            i += 10
        else:
            out.append(ESCAPES[n])
            i += 2
    return "".join(out)


def tokenize(src):
    pos, toks = 0, []
    if '"""' in src or "'''" in src:
        raise ValueError("long string literals are not supported by this parser")
    while pos < len(src):
        m = TOKEN_RE.match(src, pos)
        if not m:
            raise ValueError(f"cannot tokenize at offset {pos}: {src[pos:pos + 60]!r}")
        kind, val = m.lastgroup, m.group()
        pos = m.end()
        if kind == "ws":
            continue
        if kind == "pname" and val.endswith(".") :
            # PN_LOCAL cannot end with '.', so a trailing dot is the statement terminator.
            stripped = val.rstrip(".")
            toks.append(("pname", stripped))
            toks.extend(("punct", ".") for _ in range(len(val) - len(stripped)))
            continue
        toks.append((kind, val))
    return toks


def parse(src):
    """Return {subject: {predicate: [object, ...]}}; literals are (value, datatype|lang)."""
    toks = tokenize(src)
    prefixes, graph, i = {}, {}, 0

    def expand(tok):
        kind, val = tok
        if kind == "iri":
            return val[1:-1]
        if kind == "pname":
            pfx, local = val.split(":", 1)
            return prefixes[pfx] + local
        if kind == "a":
            return RDF_TYPE
        raise ValueError(f"expected IRI, got {tok}")

    def term(j):
        kind, val = toks[j]
        if kind == "string":
            value = unescape(val[1:-1])
            if j + 1 < len(toks) and toks[j + 1][0] == "dtype":
                return ("lit", value, expand(toks[j + 2])), j + 3
            if j + 1 < len(toks) and toks[j + 1][0] == "lang":
                return ("lit", value, toks[j + 1][1]), j + 2
            return ("lit", value, None), j + 1
        if kind == "number":
            return ("lit", val, "integer"), j + 1
        return ("iri", expand(toks[j])), j + 1

    while i < len(toks):
        if toks[i] == ("lang", "@prefix"):
            pfx = toks[i + 1][1]
            if not pfx.endswith(":"):
                raise ValueError(f"bad prefix declaration {toks[i:i + 4]}")
            prefixes[pfx[:-1]] = expand(toks[i + 2])
            if toks[i + 3] != ("punct", "."):
                raise ValueError(f"bad prefix declaration {toks[i:i + 4]}")
            i += 4
            continue
        subj = expand(toks[i])
        i += 1
        props = graph.setdefault(subj, {})
        while True:
            pred = expand(toks[i])
            i += 1
            while True:
                obj, i = term(i)
                props.setdefault(pred, []).append(obj)
                if toks[i] == ("punct", ","):
                    i += 1
                    continue
                break
            if toks[i] == ("punct", ";"):
                i += 1
                if toks[i] == ("punct", "."):
                    break
                continue
            break
        if toks[i] != ("punct", "."):
            raise ValueError(f"expected '.', got {toks[i]} after subject {subj}")
        i += 1
    return graph


def one(props, pred, subj):
    vals = props.get(pred, [])
    if len(vals) != 1:
        raise ValueError(f"{subj}: expected exactly one {pred}, got {vals}")
    return vals[0]


def doc_sort_key(ctx_iri):
    m = DOC_ID_RE.search(ctx_iri)
    return (0, int(m.group(1)[3:])) if m else (1, ctx_iri)


def read_ttl(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # The 2020 DYWC .ttl files are Latin-1 encoded (e.g. "M\xfcller"),
        # not UTF-8 as Turtle requires.
        print(f"NOTE {path} is not valid UTF-8; decoded as Latin-1")
        return raw.decode("latin-1")


def load_kore50(path):
    """Original KORE50 NIF: ({doc_id: text}, {(doc_id, start, end): surface})."""
    graph = parse(read_ttl(path))
    texts, spans = {}, {}
    for subj, props in graph.items():
        m = KORE50_DOC_RE.search(subj)
        if m and IS_STRING in props:
            texts[m.group(1)] = one(props, IS_STRING, subj)[1]
    for subj, props in graph.items():
        if REF_CONTEXT not in props:
            continue
        doc = KORE50_DOC_RE.search(subj).group(1)
        ref_doc = KORE50_DOC_RE.search(one(props, REF_CONTEXT, subj)[1]).group(1)
        if ref_doc != doc:
            # POL10 "Kennedy" points to POL09 as referenceContext;
            # its IRI and offsets belong to POL10.
            name = subj.rsplit("/", 1)[1]
            print(f"NOTE KORE50 {name}: referenceContext {ref_doc} ignored, using {doc}")
        start, end = int(one(props, BEGIN, subj)[1]), int(one(props, END, subj)[1])
        surface = one(props, ANCHOR, subj)[1]
        text = texts[doc]
        if text[start:end] != surface:
            # kore50-nif-dbpedia.ttl counts UTF-8 bytes in docs with non-ASCII text
            # (e.g. "Müller" = 0,7).
            data = text.encode("utf-8")
            assert data[start:end].decode("utf-8") == surface, (subj, surface)
            start, end = len(data[:start].decode("utf-8")), len(data[:end].decode("utf-8"))
            print(f"NOTE KORE50 {doc} {surface!r}: byte offsets converted to [{start}:{end}]")
        assert text[start:end] == surface, (subj, surface)
        spans[(doc, start, end)] = surface
    return texts, spans


def main(in_path, out_path, kore50_path=None):
    graph = parse(read_ttl(in_path))
    kore50_texts, kore50_spans = load_kore50(kore50_path) if kore50_path else (None, None)
    matched_core = set()

    contexts = {
        s: p for s, p in graph.items() if ("iri", NIF_CONTEXT) in p.get(RDF_TYPE, [])
    }
    docs = {}
    for ctx, props in contexts.items():
        text = one(props, IS_STRING, ctx)[1]
        end = props.get(END)
        if end and int(end[0][1]) != len(text):
            print(f"WARN context length mismatch {ctx}: endIndex={end[0][1]} len={len(text)}")
        docs[ctx] = {"text": text, "mentions": []}

    stats = Counter()
    mismatches = []
    for subj, props in graph.items():
        if REF_CONTEXT not in props:
            continue
        stats["phrases_total"] += 1
        ctx = one(props, REF_CONTEXT, subj)[1]
        if ctx not in docs:
            raise ValueError(f"{subj}: unknown context {ctx}")
        text = docs[ctx]["text"]
        start = int(one(props, BEGIN, subj)[1])
        end = int(one(props, END, subj)[1])
        surface = one(props, ANCHOR, subj)[1]
        if text[start:end] != surface:
            mismatches.append((subj, start, end, surface, text[start:end]))
            stats["dropped_offset_mismatch"] += 1
            continue
        refs = [o[1] for o in props.get(TA_IDENT_REF, []) if o[0] == "iri"]
        if not refs:
            stats["dropped_no_taIdentRef"] += 1
            continue
        if len(refs) > 1:
            stats["dropped_multiple_taIdentRef"] += 1
            continue
        ref = refs[0]
        m = WIKIDATA_RE.match(ref)
        if m:
            qid = m.group(2)
            if m.group(1) == "wiki":
                stats["normalized_wiki_page_iri"] += 1
                where = DOC_ID_RE.search(ctx).group(1)
                print(f"NOTE normalized {ref} -> {qid} ({surface!r} in {where})")
        elif NIL_RE.search(ref):
            qid = None
            stats["nil"] += 1
        else:
            stats["dropped_non_wikidata_iri"] += 1
            print(f"DROP non-Wikidata IRI {ref} ({surface!r})")
            continue
        docs[ctx]["mentions"].append(
            {"start": start, "end": end, "surface": surface, "qid": qid,
             "ambiguous": True, "note": NOTE}
        )

    for subj, start, end, surface, got in mismatches:
        print(f"OFFSET MISMATCH {subj}: [{start}:{end}] anchorOf={surface!r} text={got!r}")

    n_mentions = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for ctx in sorted(docs, key=doc_sort_key):
            doc = docs[ctx]
            if '\\"' in doc["text"]:
                # CEL27 was double-escaped at export (literal \" in the text, offsets counted
                # with the backslashes). Drop the stray backslashes and shift offsets to match.
                text, new_pos = [], []
                for k, ch in enumerate(doc["text"]):
                    new_pos.append(len(text))
                    if not (ch == "\\" and doc["text"][k + 1 : k + 2] == '"'):
                        text.append(ch)
                new_pos.append(len(text))
                doc["text"] = "".join(text)
                for x in doc["mentions"]:
                    x["start"], x["end"] = new_pos[x["start"]], new_pos[x["end"]]
                where = DOC_ID_RE.search(ctx).group(1)
                print(f"NOTE removed stray backslashes before quotes in {where}")
            if doc["text"].endswith(".?"):
                # Original KORE50 ends these sentences with U+FEFF;
                # the Latin-1 export turned it into '?'.
                doc["text"] = doc["text"][:-1]
                assert all(x["end"] <= len(doc["text"]) for x in doc["mentions"])
                where = DOC_ID_RE.search(ctx).group(1)
                print(f"NOTE removed trailing '?' (lost U+FEFF) in {where}")
            m = DOC_ID_RE.search(ctx)
            doc_id = "kore50-" + (kore50_doc_id(m.group(1)) if m else ctx)
            mentions = sorted(doc["mentions"], key=lambda x: (x["start"], x["end"]))
            for x in mentions:
                assert doc["text"][x["start"] : x["end"]] == x["surface"]
            if kore50_spans is not None:
                kid = doc_id[len("kore50-") :]
                # Original texts differ only by a trailing U+FEFF (POL03, POL04),
                # after the end of every mention.
                if kore50_texts.get(kid, "").rstrip("﻿") != doc["text"]:
                    print(f"WARN text differs from original KORE50 {kid}")
                for x in mentions:
                    key = (kid, x["start"], x["end"])
                    core = kore50_spans.get(key) == x["surface"]
                    if core:
                        matched_core.add(key)
                    x["ambiguous"] = core
                    x["note"] = NOTE + (" core" if core else " extra")
                    x["kore50_core"] = core
            n_mentions += len(mentions)
            row = {"id": doc_id, "text": doc["text"], "mentions": mentions}
            out.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"documents: {len(docs)}")
    print(f"phrases in source: {stats['phrases_total']}")
    print(f"mentions kept: {n_mentions}")
    print(f"mentions with null qid (NIL): {stats['nil']}")
    print(f"normalized /wiki/Qn IRIs: {stats['normalized_wiki_page_iri']}")
    for key in sorted(k for k in stats if k.startswith("dropped_")):
        print(f"{key}: {stats[key]}")
    if kore50_spans is not None:
        print(f"kore50_core mentions: {len(matched_core)}; extra: {n_mentions - len(matched_core)}")
        missing = sorted(set(kore50_spans) - matched_core)
        print("original KORE50 mentions without a Wikidata-linked DYWC counterpart:", len(missing))
        for doc, start, end in missing:
            print(f"  {doc} [{start}:{end}] {kore50_spans[(doc, start, end)]!r}")
    if mismatches:
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    main(*sys.argv[1:])
