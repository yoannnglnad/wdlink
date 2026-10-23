"""Stage 1 — term extraction: named entities and specific noun phrases, with character offsets."""

from functools import lru_cache

import spacy
from spacy.tokens import Doc, Span
from wordfreq import zipf_frequency

from wdlink import config
from wdlink.config import DEFAULT_PIPELINE, PipelineConfig
from wdlink.models import Mention

STRIP_POS = {"DET", "PRON", "NUM", "PUNCT"}
STRIP_TAGS = {"JJS", "JJR", "PRP$", "POS", "WDT"}  # superlatives, possessives ("its", "'s")


@lru_cache(maxsize=2)
def load_nlp(model: str = config.SPACY_MODEL):
    return spacy.load(model)


def _trim(span: Span) -> Span | None:
    """Drop leading determiners/possessives/superlatives and trailing possessive markers."""
    start, end = span.start, span.end
    doc = span.doc
    while start < end and (doc[start].pos_ in STRIP_POS or doc[start].tag_ in STRIP_TAGS):
        start += 1
    while end > start and (doc[end - 1].tag_ == "POS" or doc[end - 1].pos_ == "PUNCT"):
        end -= 1
    return doc[start:end] if end > start else None


def _context(span: Span, window: int | None) -> str:
    """The sentence of the mention plus `window` sentences on each side (None: whole text)."""
    if window is None:
        return span.doc.text
    sents = list(span.doc.sents)
    idx = next(i for i, s in enumerate(sents) if s.start <= span.start < s.end)
    return " ".join(s.text for s in sents[max(0, idx - window) : idx + window + 1])


def _is_specific(span: Span, max_zipf: float | None) -> bool:
    """Keep proper nouns, compounds and rare nouns; drop generic words like "research"."""
    if max_zipf is None:
        return span.root.pos_ in {"NOUN", "PROPN"}
    if any(t.pos_ == "PROPN" for t in span):
        return True
    if span.root.pos_ not in {"NOUN", "PROPN"}:
        return False
    if len(span) > 1 and any(t.dep_ == "compound" for t in span):
        return True
    content = [t for t in span if t.pos_ in {"NOUN", "ADJ"} and not t.is_stop]
    return any(zipf_frequency(t.text.lower(), config.LANGUAGE) < max_zipf for t in content)


def is_common_noun(text: str, ner_label: str | None, tokens: Span) -> bool:
    """A lower-case term that is not a named entity ("radioactivity"), the casing rule's input.

    One rule for extracted and gold mentions: no NER label, no proper-noun token, no capital.
    """
    return (
        ner_label is None
        and not any(t.pos_ == "PROPN" for t in tokens)
        and not any(c.isupper() for c in text)
    )


def _mention(span: Span, source: str, ner_label: str | None, window: int | None) -> Mention:
    is_common = is_common_noun(span.text, ner_label, span)
    return Mention(
        text=span.text,
        start=span.start_char,
        end=span.end_char,
        source=source,
        ner_label=ner_label,
        context=_context(span, window),
        is_common_noun=is_common,
        queries=[span.text],
    )


def extract_mentions(
    text: str, nlp=None, pcfg: PipelineConfig = DEFAULT_PIPELINE
) -> tuple[Doc, list[Mention]]:
    """Named entities first; noun chunks only where they do not overlap an entity."""
    nlp = nlp or load_nlp(pcfg.spacy_model)
    doc = nlp(text)
    mentions: list[Mention] = []
    taken = set()
    for ent in doc.ents:
        if ent.label_ in config.SKIPPED_NER_LABELS:
            continue
        span = _trim(ent)
        if span is None:
            continue
        mentions.append(_mention(span, "ner", ent.label_, pcfg.context_window))
        taken.update(range(ent.start, ent.end))
    for chunk in doc.noun_chunks:
        span = _trim(chunk)
        if span is None or taken.intersection(range(span.start, span.end)):
            continue
        if _is_specific(span, pcfg.generic_noun_max_zipf):
            mentions.append(_mention(span, "noun_chunk", None, pcfg.context_window))
            taken.update(range(span.start, span.end))
    mentions.sort(key=lambda m: m.start)
    if pcfg.surname_expansion:
        expand_short_mentions(mentions)
    return doc, mentions


def mentions_from_spans(
    text: str, spans: list[tuple[int, int]], nlp=None, pcfg: PipelineConfig = DEFAULT_PIPELINE
) -> list[Mention]:
    """Build mentions for given (gold) spans, reusing spaCy for context and NER type."""
    nlp = nlp or load_nlp(pcfg.spacy_model)
    doc = nlp(text)
    mentions = []
    for start, end in spans:
        span = doc.char_span(start, end, alignment_mode="expand")
        ner_label = next(
            (
                e.label_
                for e in doc.ents
                if e.start_char <= start
                and end <= e.end_char
                and e.label_ not in config.SKIPPED_NER_LABELS
            ),
            None,
        )
        m = _mention(span, "gold", ner_label, pcfg.context_window)
        m.text, m.start, m.end, m.queries = text[start:end], start, end, [text[start:end]]
        m.is_common_noun = is_common_noun(m.text, ner_label, span)
        mentions.append(m)
    if pcfg.surname_expansion:
        expand_short_mentions(mentions)
    return mentions


def expand_short_mentions(mentions: list[Mention]) -> None:
    """In-document expansion: "Curie" after "Marie Curie" also searches "Marie Curie".

    Off by default (ADR-009): the human search covers bare surnames, and on dev the expansion
    fired twice, both times wrongly ("Jordan" -> "Jordan River").
    """
    for m in mentions:
        if m.is_common_noun:
            continue
        words = m.text.lower().split()
        for other in mentions:
            other_words = other.text.lower().split()
            if len(other_words) <= len(words) or other.text in m.queries:
                continue
            n = len(words)
            if any(other_words[i : i + n] == words for i in range(len(other_words) - n + 1)):
                m.queries.append(other.text)
