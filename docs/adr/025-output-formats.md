# ADR-025 — Outputs: structured JSON for people and programs, Turtle for Linked Data

**Status:** accepted · **Evidence:** assignment requirements and interoperability (no benchmark).

## Context

The assignment asks for "the original terms, selected Wikidata concepts, QIDs, ranking scores, alternative candidates, and supporting evidence in a structured JSON format", and for the RDF/SKOS basis to be explicit.

## Decision

`wdlink link` produces three outputs:

**1. A table on screen,** with the same columns as the assignment's example (mention, concept, QID, confidence), plus the raw score and the decision.

**2. A JSON file (`--json`).** For each mention it gives:

- the surface form, character offsets, source (NER or noun chunk) and spaCy label;
- the decision: `linked`, or a NIL reason (`nil_low_score`, `nil_ambiguous`, `nil_no_candidate`);
- the selected item: QID, URI, label, description, score and calibrated confidence;
- the evidence: every feature value, the card that was embedded (label, description and the retrieved graph facts), the graph links that supported the choice (property, direction, shared neighbours, the other mention's candidate and its weight), and the search queries used;
- up to five alternatives, each with its features.

**3. A Turtle file (`--ttl`)** containing the document's SKOS graph (ADR-014) with the decisions written back as ITS 2.0 annotations and provenance.

## Why no benchmark

These are interface choices, constrained by the assignment and by standards (NIF, ITS 2.0, SKOS). Nothing about them can be measured as better or worse.

## Consequences

- Each decision can be audited from the JSON: a reviewer can see *why* Paris is Q90 here (Marie Curie's residence) and Q167646 in the Trojan text.
- The Turtle file can be loaded into any triple store or GERBIL-style tool.
