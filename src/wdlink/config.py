"""All tunable constants of the pipeline live here (no magic numbers elsewhere)."""

from dataclasses import dataclass, field
from pathlib import Path

# --- Wikidata access -------------------------------------------------------------------------

USER_AGENT = "wdlink/0.1 (entity-linking research prototype; yoann@qomment.io) python-requests"
ACTION_API = "https://www.wikidata.org/w/api.php"
REST_SEARCH_API = "https://www.wikidata.org/w/rest.php/wikibase/v1/search/items"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# Gateway limit for a client identified by User-Agent only: 200 req/min (Wikimedia, 2026).
# We stay below it and keep concurrency modest, as the API etiquette asks.
MAX_REQUESTS_PER_MINUTE = 150
MAX_PARALLEL_REQUESTS = 3
HTTP_TIMEOUT_S = 30
SPARQL_TIMEOUT_S = 60
MAX_RETRIES = 4
MIN_BACKOFF_S = 5
WBGETENTITIES_BATCH = 50  # hard API limit
SPARQL_VALUES_BATCH = 100  # QIDs per VALUES clause, keeps each query well under the 60 s budget
CACHE_DIR = Path(".cache/wikidata")

LANGUAGE = "en"
LABEL_LANGUAGES = "en|mul"  # many English labels now live under `mul` only (e.g. Q42)

# --- Term extraction -------------------------------------------------------------------------

# Transformer pipeline: end-to-end F1 +3.4 over en_core_web_sm on dev, interval excluding 0
# (ADR-004). en_core_web_sm stays installed as the lightweight option (--spacy-model).
SPACY_MODEL = "en_core_web_trf"
# NER labels that never denote a linkable concept.
SKIPPED_NER_LABELS = frozenset(
    {"DATE", "TIME", "PERCENT", "MONEY", "QUANTITY", "ORDINAL", "CARDINAL"}
)
# A one-word common noun more frequent than this (Zipf scale) is too generic to link
# ("research" 5.4, "planet" 4.7) while specific terms pass ("radioactivity" 2.9, "helium" 3.4).
# Benchmarked on dev end to end (ADR-005): 4.5 -> 3.5 raises A2KB F1 from 0.696 to 0.741.
GENERIC_NOUN_MAX_ZIPF = 3.5
CONTEXT_WINDOW_SENTENCES = 1  # sentences on each side of the mention used as its context

# --- Candidate retrieval ---------------------------------------------------------------------

# Each search API is always asked for its maximum page (50) and the result is cached; the
# configured limit is applied locally, so recall@k curves cost no extra request.
SEARCH_FETCH_LIMIT = 50
SEARCH_LIMIT = 20  # per search API (wbsearchentities and REST search), union is taken
# A bare capitalised word ("Lincoln", "Mercury") is also searched among humans only:
# both search APIs rank places and works first and miss the famous bearer of the name.
HUMAN_SEARCH_LIMIT = 5
CANDIDATES_FOR_GRAPH = 10  # kept per mention after the cheap pre-ranking
# pre-ranking = w_txt * sim(context, label+description) + w_name * name match + w_rank / (1 + rank)
PRERANK_WEIGHTS = {"txt": 0.5, "name": 0.3, "rank": 0.2}
# Wikimedia housekeeping items are never valid link targets.
EXCLUDED_CLASSES = frozenset(
    {
        "Q4167410",  # Wikimedia disambiguation page
        "Q4167836",  # Wikimedia category
        "Q13406463",  # Wikimedia list article
        "Q11266439",  # Wikimedia template
        "Q101352",  # family name
        "Q202444",  # given name
        "Q12308941",  # male given name
        "Q11879590",  # female given name
    }
)
EXCLUDED_DESCRIPTIONS = (
    "wikimedia disambiguation page",
    "wikimedia category",
    "wikimedia list article",
    "wikimedia template",
    "family name",
    "surname",
    "given name",
    # scholarly articles left the main WDQS graph in 2025: they cannot be enriched, and a
    # plain-text mention almost never means a paper that shares its title
    "scientific article",
    "scholarly article",
)

# --- Knowledge graph -------------------------------------------------------------------------

# Relations kept for the verbalised card and for shared-neighbour relatedness.
# P31/P279 are kept apart (types), P1346 "winner" is excluded (hundreds of values on prizes).
RELATION_PROPERTIES: dict[str, str] = {
    "P17": "country",
    "P131": "located in the administrative territorial entity",
    "P276": "location",
    "P159": "headquarters location",
    "P19": "place of birth",
    "P20": "place of death",
    "P27": "country of citizenship",
    "P106": "occupation",
    "P101": "field of work",
    "P166": "award received",
    "P69": "educated at",
    "P108": "employer",
    "P463": "member of",
    "P361": "part of",
    "P527": "has part(s)",
    "P50": "author",
    "P57": "director",
    "P175": "performer",
    "P495": "country of origin",
    "P800": "notable work",
    "P26": "spouse",
    "P22": "father",
    "P25": "mother",
    "P40": "child",
    "P737": "influenced by",
    "P921": "main subject",
    "P136": "genre",
    "P178": "developer",
    "P176": "manufacturer",
    "P61": "discoverer or inventor",
    "P138": "named after",
    "P1269": "facet of",
    "P2578": "studies",
    "P397": "parent astronomical body",
    "P398": "child astronomical body",
    "P150": "contains the administrative territorial entity",
    "P36": "capital",
    "P1376": "capital of",
    "P30": "continent",
    "P206": "located in or next to body of water",
    "P155": "follows",
    "P156": "followed by",
}
TYPE_PROPERTIES = {"P31": "instance of", "P279": "subclass of"}
# Statements that assert a NEGATIVE or ambiguous relation must never count as evidence.
NEGATIVE_PROPERTIES = frozenset({"P1889", "P460"})  # different from, said to be the same as
TYPE_DEPTH = 3  # P31/P279{0..3}; unbounded P279* types capitals as organizations (ADR-013)
MAX_VALUES_PER_PROPERTY_IN_CARD = 4
MAX_FACTS_PER_CANDIDATE = 24  # pool of verbalised facts the card is built from
# Query-focused selection: only the facts closest to the mention's context go into the card.
# Appending every fact dilutes the embedding of well-described items (ADR-018).
FACTS_PER_CARD = 3

# --- Entity types ----------------------------------------------------------------------------

# spaCy NER label -> Wikidata classes it is compatible with (checked against P31/P279{0..3}).
NER_TYPE_MAP: dict[str, frozenset[str]] = {
    "PERSON": frozenset({"Q5", "Q95074", "Q15632617", "Q4271324", "Q178885", "Q22988604"}),
    "NORP": frozenset({"Q41710", "Q231002", "Q9174", "Q7278", "Q33829", "Q6256"}),
    "FAC": frozenset({"Q13226383", "Q41176", "Q811979", "Q12280"}),
    "ORG": frozenset({"Q43229", "Q4830453", "Q2385804", "Q215380", "Q41710"}),
    "GPE": frozenset({"Q56061", "Q6256", "Q515", "Q486972", "Q7275", "Q107390"}),
    "LOC": frozenset({"Q2221906", "Q618123", "Q15324", "Q4022", "Q8502", "Q23397", "Q46831"}),
    "PRODUCT": frozenset({"Q2424752", "Q9143", "Q7397", "Q1183543"}),
    "EVENT": frozenset({"Q1656682", "Q1190554", "Q198"}),
    "WORK_OF_ART": frozenset({"Q17537576", "Q838948", "Q7725634", "Q47461344", "Q618779"}),
    "LAW": frozenset({"Q7748", "Q820655"}),
    "LANGUAGE": frozenset({"Q34770", "Q9143"}),
}
# Lower-case common nouns ("radioactivity") almost never refer to people, songs, films or
# games; this removes the Kraftwerk single "Radioactivity" without any graph evidence.
# "creative work" and "business" are deliberately absent: lower-case software and brand
# names ("pandas", "numpy") are creative works in Wikidata and are common in science text.
COMMON_NOUN_INCOMPATIBLE = frozenset(
    {
        "Q5",  # human
        "Q215380",  # musical group
        "Q2188189",  # musical work
        "Q105543609",  # musical work/composition
        "Q108346082",  # release group
        "Q134556",  # single
        "Q7366",  # song
        "Q482994",  # album
        "Q11424",  # film
        "Q5398426",  # television series
        "Q7889",  # video game
        "Q7725634",  # literary work
    }
)

# --- Embeddings ------------------------------------------------------------------------------

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_BATCH = 64


# --- Pipeline (everything decided before ranking) -------------------------------------------


@dataclass(frozen=True)
class PipelineConfig:
    """Extraction, retrieval and enrichment choices (benchmarked in eval/benchmarks)."""

    spacy_model: str = SPACY_MODEL
    embedding_model: str = EMBEDDING_MODEL
    generic_noun_max_zipf: float | None = GENERIC_NOUN_MAX_ZIPF  # None keeps every noun chunk
    context_window: int | None = CONTEXT_WINDOW_SENTENCES  # None = the whole document
    surname_expansion: bool = False  # redundant with human search (ADR-009)
    search_apis: tuple[str, ...] = ("wbs", "rest")  # among "wbs", "rest", "cirrus"
    human_search: bool = True
    search_limit: int = SEARCH_LIMIT
    exclude_housekeeping: bool = True
    prerank: str = "mixed"  # "mixed" (similarity + name + rank) or "search_rank"
    candidates_for_graph: int = CANDIDATES_FOR_GRAPH
    facts_per_card: int | None = FACTS_PER_CARD  # None = every verbalised fact
    all_relations: bool = False  # neighbourhoods from every property instead of the whitelist


DEFAULT_PIPELINE = PipelineConfig()


# --- Ranking ---------------------------------------------------------------------------------

PPR_DAMPING = 0.85  # personalised PageRank continuation probability (restart = 0.15)


@dataclass(frozen=True)
class RankingConfig:
    """Weights and thresholds of the scoring function (tuned on the dev split only)."""

    # local score L = w_txt*s_txt + w_name*s_name + w_type*s_type + w_pop*s_pop
    w_txt: float = 0.50
    w_name: float = 0.20
    w_type: float = 0.15
    w_pop: float = 0.15
    # final score S = L + beta * G  (coherence is a bonus: S == L when there is no graph evidence)
    beta: float = 0.10  # tuned on dev (52 documents, eval/results/results.md)
    # the card embedded for s_txt: label+description only, or also the verbalised graph facts
    verbalise_graph: bool = True
    # coherence variant: "weighted" (idf + softmax weights + c1/c2), "naive" (ablation A3),
    # or "ppr" (personalised PageRank over the local graph, Pershina et al. 2015)
    coherence: str = "weighted"
    # "additive": S = L + beta*G (no penalty without evidence); "convex": (1-beta)*L + beta*G
    fusion: str = "additive"
    # fuzzy name match against the label only, or against label and aliases (token-set)
    name_match: str = "label"
    softmax_temperature: float = 0.1  # sharpness of p_L(c') used to weight other mentions
    direct_edge_strength: float = 1.0
    # selection: link only if S1 >= nil_threshold and S1 - S2 >= min_margin, else NIL
    nil_threshold: float = 0.38  # tuned on dev
    min_margin: float = 0.0
    confidence_temperature: float = 0.03  # temperature scaling on dev (min NLL), ADR-023
    # entity-type signal: "ner" (spaCy label vs P31/P279 closure, plus the common-noun rule),
    # "common_noun" (only: lower-case terms are not people/works/companies), or "none"
    # spaCy NER labels: -7.3 points with sm (p = 0.001), not significant with trf (ADR-019)
    types: str = "common_noun"
    use_popularity: bool = True
    extra: dict = field(default_factory=dict)


DEFAULT_RANKING = RankingConfig()
