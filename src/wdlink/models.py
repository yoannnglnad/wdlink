"""Data structures passed between pipeline stages."""

from dataclasses import dataclass, field


@dataclass
class Mention:
    """A span of the input text that may refer to a Wikidata concept."""

    text: str
    start: int  # character offsets in the original document: doc[start:end] == text
    end: int
    source: str  # "ner" or "noun_chunk" (or "gold" when spans are given)
    ner_label: str | None  # spaCy NER label, None for noun chunks
    context: str  # the sentence window used for semantic similarity
    is_common_noun: bool = False  # lower-case, non-NER term such as "radioactivity"
    queries: list[str] = field(default_factory=list)  # search strings (surface + expansions)


@dataclass
class Candidate:
    """A Wikidata item that may be the referent of a mention."""

    qid: str
    label: str = ""
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    search_rank: int = 999  # best (0-based) rank over all search APIs and queries
    sources: set[str] = field(default_factory=set)  # "wbs", "rest", "expansion:<text>"
    p31: list[str] = field(default_factory=list)
    types: set[str] = field(default_factory=set)  # P31/P279{0..3} closure
    sitelinks: int = 0
    # outgoing truthy statements with an item value: (property, value QID)
    relations: list[tuple[str, str]] = field(default_factory=list)
    # filled by the ranker
    features: dict[str, float] = field(default_factory=dict)
    score: float = 0.0
    evidence: dict = field(default_factory=dict)


@dataclass
class LinkedMention:
    mention: Mention
    candidates: list[Candidate]  # ranked, best first
    selected: Candidate | None  # None means NIL
    confidence: float
    decision: str  # "linked", "nil_low_score", "nil_ambiguous", "nil_no_candidate"
