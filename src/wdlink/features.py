"""Local (graph-free) features of a mention/candidate pair."""

import math
import re
import unicodedata

from rapidfuzz import fuzz

from wdlink import config
from wdlink.models import Candidate, Mention


def normalise(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"^(the|a|an)\s+", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


def name_similarity(surface: str, label: str, aliases: list[str]) -> float:
    """1.0 exact label, 0.9 exact alias, otherwise a damped fuzzy match against the label.

    Aliases only count when exact: a fuzzy alias match lets "Darwin, Northern Territory"
    score high for the mention "Northern Territory".
    """
    m = normalise(surface)
    if m == normalise(label):
        return 1.0
    names = [normalise(a) for a in aliases]
    if m in names:
        return 0.9
    return 0.8 * fuzz.ratio(m, normalise(label)) / 100


def type_compatibility(mention: Mention, cand: Candidate, use_ner: bool = True) -> float:
    """1 compatible, 0.5 unknown, 0 incompatible with the mention's expected type."""
    if mention.is_common_noun:
        return 0.0 if cand.types & config.COMMON_NOUN_INCOMPATIBLE else 1.0
    allowed = config.NER_TYPE_MAP.get(mention.ner_label or "") if use_ner else None
    if not allowed or not cand.types:
        return 0.5
    return 1.0 if cand.types & allowed else 0.0


def popularity(cand: Candidate, max_sitelinks: int) -> float:
    if max_sitelinks <= 0:
        return 0.0
    return math.log1p(cand.sitelinks) / math.log1p(max_sitelinks)
