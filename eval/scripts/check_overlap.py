"""Check that the dev split does not leak into the held-out test split.

Usage: python3 eval/scripts/check_overlap.py [eval/data/dev.jsonl] [eval/data/test.jsonl]

Prints only two counts, never any test content:
  - dev docs whose text shares at least one 6-word shingle with any test doc
  - (surface, qid) pairs present in both splits (NIL pairs count with qid null)
With --ids, also prints the ids of the overlapping dev docs (dev ids only), so they can be rewritten.
Words are lowercased runs of letters/digits, so punctuation and case are ignored.
Dependencies: stdlib only.
"""

import json
import re
import sys

N = 6
WORD = re.compile(r"\w+")


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def shingles(text):
    words = WORD.findall(text.lower())
    return {tuple(words[i:i + N]) for i in range(len(words) - N + 1)}


def pairs(docs):
    return {(m["surface"], m["qid"]) for d in docs for m in d["mentions"]}


def main(argv):
    show_ids = "--ids" in argv
    paths = [a for a in argv if a != "--ids"]
    dev_path = paths[0] if paths else "eval/data/dev.jsonl"
    test_path = paths[1] if len(paths) > 1 else "eval/data/test.jsonl"
    dev, test = load(dev_path), load(test_path)
    test_sh = set().union(*(shingles(d["text"]) for d in test))
    leaking = [d["id"] for d in dev if shingles(d["text"]) & test_sh]
    shared_pairs = pairs(dev) & pairs(test)
    print(f"dev docs sharing a {N}-word shingle with test: {len(leaking)}")
    print(f"(surface, qid) pairs present in both splits: {len(shared_pairs)}")
    if show_ids and leaking:
        print("overlapping dev ids:", ", ".join(leaking))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
