"""Stage 3 — knowledge-graph enrichment into a local RDF graph using SKOS.

Every candidate (and every neighbour we keep) becomes a local skos:Concept mapped to its
Wikidata item with skos:exactMatch. Hierarchical Wikidata properties use SKOS-Primer §4.7
specialisations of skos:broader (generic / instantive / partitive) so that instance-of and
subclass-of chains are never mixed; other relations keep their wdt: predicate and, when the
pair is not hierarchical (SKOS integrity condition S27), a skos:related link.
Mentions are NIF phrases; links use the ITS 2.0 RDF vocabulary (taIdentRef, taConfidence).
The ranker reads a NetworkX view derived from this RDF graph with a SPARQL query.
"""

import hashlib
from datetime import UTC, datetime

import networkx as nx
from rdflib import RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import PROV, SKOS

from wdlink import config
from wdlink.models import Candidate, LinkedMention, Mention
from wdlink.wikidata import WikidataClient

EX = Namespace("http://example.org/wdlink/")
CONCEPT = Namespace("http://example.org/wdlink/concept/")
WD = Namespace("http://www.wikidata.org/entity/")
WDT = Namespace("http://www.wikidata.org/prop/direct/")
SCHEMA = Namespace("http://schema.org/")
NIF = Namespace("http://persistence.uni-leipzig.org/nlp2rdf/ontologies/nif-core#")
ITSRDF = Namespace("http://www.w3.org/2005/11/its/rdf#")

HIERARCHY = {
    "P279": EX.broaderGeneric,  # subclass of
    "P31": EX.broaderInstantive,  # instance of
    "P361": EX.broaderPartitive,  # part of
    "P527": EX.narrowerPartitive,  # has part(s)
}
CARD_PROPERTIES = {**config.TYPE_PROPERTIES, **config.RELATION_PROPERTIES}


def concept(qid: str) -> URIRef:
    return CONCEPT[qid]


def qid_of(uri) -> str:
    return str(uri).rsplit("/", 1)[-1]


def enrich(per_mention: list[list[Candidate]], client: WikidataClient) -> dict[str, str]:
    """Fetch types, sitelinks and relations; drop housekeeping items. Returns neighbour labels."""
    qids = list(dict.fromkeys(c.qid for cands in per_mention for c in cands))
    types = client.get_types(qids)
    relations = client.get_relations(qids)
    for cands in per_mention:
        for c in cands:
            t = types.get(c.qid, {})
            c.p31, c.types, c.sitelinks = (
                t.get("p31", []),
                set(t.get("types", [])),
                t.get("sitelinks", 0),
            )
            c.relations = [(p, v) for p, v in relations.get(c.qid, [])]
        cands[:] = [c for c in cands if not set(c.p31) & config.EXCLUDED_CLASSES]
    candidate_set = {c.qid for cands in per_mention for c in cands}
    neighbours = {
        v
        for cands in per_mention
        for c in cands
        for p, v in c.relations
        if p in CARD_PROPERTIES or v in candidate_set
    }
    return client.get_labels(sorted(neighbours - candidate_set))


def doc_uri(text: str) -> str:
    return EX[f"doc/{hashlib.sha1(text.encode()).hexdigest()[:12]}"]


def build_graph(
    text: str,
    mentions: list[Mention],
    per_mention: list[list[Candidate]],
    neighbour_labels: dict[str, str],
) -> Graph:
    g = Graph()
    for prefix, ns in [
        ("skos", SKOS),
        ("ex", EX),
        ("c", CONCEPT),
        ("wd", WD),
        ("wdt", WDT),
        ("schema", SCHEMA),
        ("nif", NIF),
        ("itsrdf", ITSRDF),
        ("prov", PROV),
    ]:
        g.bind(prefix, ns)
    for prop, parent in [
        (EX.broaderGeneric, SKOS.broader),
        (EX.broaderInstantive, SKOS.broader),
        (EX.broaderPartitive, SKOS.broader),
        (EX.narrowerPartitive, SKOS.narrower),
    ]:
        g.add((prop, RDFS.subPropertyOf, parent))

    doc = doc_uri(text)
    scheme = URIRef(f"{doc}/scheme")
    context = URIRef(f"{doc}#char=0,{len(text)}")
    g.add((scheme, RDF.type, SKOS.ConceptScheme))
    g.add((context, RDF.type, NIF.Context))
    g.add((context, NIF.isString, Literal(text)))

    candidate_set = {c.qid for cands in per_mention for c in cands}

    def add_concept(qid: str, label: str) -> URIRef:
        node = concept(qid)
        if (node, RDF.type, SKOS.Concept) not in g:
            g.add((node, RDF.type, SKOS.Concept))
            g.add((node, SKOS.inScheme, scheme))
            g.add((node, SKOS.exactMatch, WD[qid]))
            g.add((node, SKOS.prefLabel, Literal(label or qid, lang="en")))
        return node

    related_pairs = set()
    for cands in per_mention:
        for c in cands:
            node = add_concept(c.qid, c.label)
            for alias in c.aliases:
                g.add((node, SKOS.altLabel, Literal(alias, lang="en")))
            if c.description:
                g.add((node, SCHEMA.description, Literal(c.description, lang="en")))
            g.add((node, EX.sitelinks, Literal(c.sitelinks, datatype=XSD.integer)))
            for p, v in c.relations:
                if p in config.NEGATIVE_PROPERTIES:
                    continue
                if v not in candidate_set and p not in CARD_PROPERTIES:
                    continue
                if v not in candidate_set:
                    add_concept(v, neighbour_labels.get(v, v))
                g.add((node, WDT[p], concept(v)))
                if p in HIERARCHY:
                    g.add((node, HIERARCHY[p], concept(v)))
                elif p not in config.TYPE_PROPERTIES:
                    related_pairs.add((node, concept(v)))

    hierarchical = {(s, o) for p in HIERARCHY.values() for s, o in g.subject_objects(p)}
    for a, b in related_pairs:
        if (a, b) not in hierarchical and (b, a) not in hierarchical:
            g.add((a, SKOS.related, b))

    for m, cands in zip(mentions, per_mention, strict=True):
        node = mention_uri(text, m)
        g.add((node, RDF.type, NIF.Phrase))
        g.add((node, NIF.anchorOf, Literal(m.text)))
        g.add((node, NIF.beginIndex, Literal(m.start, datatype=XSD.nonNegativeInteger)))
        g.add((node, NIF.endIndex, Literal(m.end, datatype=XSD.nonNegativeInteger)))
        g.add((node, NIF.referenceContext, context))
        for c in cands:
            g.add((node, EX.hasCandidate, concept(c.qid)))
    return g


def mention_uri(text: str, m: Mention) -> URIRef:
    return URIRef(f"{doc_uri(text)}#char={m.start},{m.end}")


CONCEPT_EDGES = f"""
SELECT ?s ?p ?o WHERE {{
  ?s ?p ?o .
  ?s a <{SKOS.Concept}> .
  ?o a <{SKOS.Concept}> .
  FILTER(STRSTARTS(STR(?p), "{WDT}"))
}}"""


def to_networkx(g: Graph) -> nx.MultiDiGraph:
    """Concept-to-concept relations of the RDF graph as a NetworkX multigraph (edge attr: prop)."""
    view = nx.MultiDiGraph()
    for s, p, o in g.query(CONCEPT_EDGES):
        view.add_edge(qid_of(s), qid_of(o), prop=qid_of(p))
    for node, label in g.subject_objects(SKOS.prefLabel):
        if isinstance(node, URIRef) and str(node).startswith(str(CONCEPT)):
            view.add_node(qid_of(node), label=str(label))
    return view


def verbalise(view: nx.MultiDiGraph, qid: str) -> list[tuple[str, str]]:
    """(property label, value label) facts of a concept, read from the graph view.

    Values are ordered by QID number (older items are the more central ones) and capped,
    so the card stays short enough for the embedding model and deterministic.
    """
    by_prop: dict[str, list[str]] = {}
    if qid in view:
        for _, v, data in view.out_edges(qid, data=True):
            if data["prop"] in CARD_PROPERTIES:
                by_prop.setdefault(data["prop"], []).append(v)
    facts = []
    for prop in CARD_PROPERTIES:
        values = sorted(set(by_prop.get(prop, [])), key=lambda q: int(q[1:]))
        for v in values[: config.MAX_VALUES_PER_PROPERTY_IN_CARD]:
            facts.append((CARD_PROPERTIES[prop], view.nodes[v].get("label", v)))
    return facts[: config.MAX_FACTS_IN_CARD]


def graph_card(c: Candidate, view: nx.MultiDiGraph) -> str:
    """Label + description + verbalised neighbourhood: the "augmented" text used by GraphRAG."""
    grouped: dict[str, list[str]] = {}
    for prop_label, value in verbalise(view, c.qid):
        grouped.setdefault(prop_label, []).append(value)
    facts = "; ".join(f"{p}: {', '.join(vs)}" for p, vs in grouped.items())
    head = f"{c.label}, {c.description}" if c.description else c.label
    return f"{head}. {facts}" if facts else head


def annotate_links(g: Graph, text: str, linked: list[LinkedMention], run_params: dict) -> None:
    """Write the final decisions back into the RDF graph (ITS 2.0 + PROV-O)."""
    activity = URIRef(f"{doc_uri(text)}/run")
    g.add((activity, RDF.type, PROV.Activity))
    g.add((activity, PROV.endedAtTime, Literal(datetime.now(UTC), datatype=XSD.dateTime)))
    for key, value in run_params.items():
        g.add((activity, EX[key], Literal(value)))
    for lm in linked:
        node = mention_uri(text, lm.mention)
        g.add((node, PROV.wasGeneratedBy, activity))
        if lm.selected is None:
            g.add((node, EX.decision, Literal(lm.decision)))
            continue
        g.add((node, ITSRDF.taIdentRef, WD[lm.selected.qid]))
        g.add((node, ITSRDF.taConfidence, Literal(round(lm.confidence, 4), datatype=XSD.double)))
        for t in lm.selected.p31:
            g.add((node, ITSRDF.taClassRef, WD[t]))
