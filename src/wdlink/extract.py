"""Stage 1 — term extraction: named entities and specific noun phrases, with character offsets."""

from functools import lru_cache

import spacy
from spacy.tokens import Doc, Span
from wordfreq import zipf_frequency

from wdlink import config
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


def _context(span: Span) -> str:
    sents = list(span.doc.sents)
    idx = next(i for i, s in enumerate(sents) if s.start <= span.start < s.end)
    w = config.CONTEXT_WINDOW_SENTENCES
    return " ".join(s.text for s in sents[max(0, idx - w) : idx + w + 1])


def _is_specific(span: Span) -> bool:
    """Keep proper nouns, compounds and rare nouns; drop generic words like "research"."""
    if any(t.pos_ == "PROPN" for t in span):
        return True
    if span.root.pos_ not in {"NOUN", "PROPN"}:
        return False
    if len(span) > 1 and any(t.dep_ == "compound" for t in span):
        return True
    content = [t for t in span if t.pos_ in {"NOUN", "ADJ"} and not t.is_stop]
    return any(
        zipf_frequency(t.text.lower(), config.LANGUAGE) < config.GENERIC_NOUN_MAX_ZIPF
        for t in content
    )


def _mention(span: Span, source: str, ner_label: str | None) -> Mention:
    is_common = ner_label is None and not any(
        t.pos_ == "PROPN" or t.text[:1].isupper() for t in span
    )
    return Mention(
        text=span.text,
        start=span.start_char,
        end=span.end_char,
        source=source,
        ner_label=ner_label,
        context=_context(span),
        is_common_noun=is_common,
        queries=[span.text],
    )


def extract_mentions(text: str, nlp=None) -> tuple[Doc, list[Mention]]:
    """Named entities first; noun chunks only where they do not overlap an entity."""
    nlp = nlp or load_nlp()
    doc = nlp(text)
    mentions: list[Mention] = []
    taken = set()
    for ent in doc.ents:
        if ent.label_ in config.SKIPPED_NER_LABELS:
            continue
        span = _trim(ent)
        if span is None:
            continue
        mentions.append(_mention(span, "ner", ent.label_))
        taken.update(range(ent.start, ent.end))
    for chunk in doc.noun_chunks:
        span = _trim(chunk)
        if span is None or taken.intersection(range(span.start, span.end)):
            continue
        if _is_specific(span):
            mentions.append(_mention(span, "noun_chunk", None))
            taken.update(range(span.start, span.end))
    mentions.sort(key=lambda m: m.start)
    expand_short_mentions(mentions)
    return doc, mentions


def mentions_from_spans(text: str, spans: list[tuple[int, int]], nlp=None) -> list[Mention]:
    """Build mentions for given (gold) spans, reusing spaCy for context and NER type."""
    nlp = nlp or load_nlp()
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
        m = _mention(span, "gold", ner_label)
        m.text, m.start, m.end, m.queries = text[start:end], start, end, [text[start:end]]
        m.is_common_noun = ner_label is None and not any(c.isupper() for c in m.text)
        mentions.append(m)
    expand_short_mentions(mentions)
    return mentions


def expand_short_mentions(mentions: list[Mention]) -> None:
    """In-document expansion: "Curie" after "Marie Curie" also searches "Marie Curie".

    Wikidata search often misses a person given only by surname (Q7186 is not in the top 20
    for "Curie"); the longer mention elsewhere in the document is the best query.
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
