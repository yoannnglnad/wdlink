"""End-to-end check on the assignment example (needs the Wikidata API or a warm cache)."""

import pytest

from wdlink.pipeline import Linker

pytestmark = pytest.mark.network


@pytest.fixture(scope="module")
def linker():
    return Linker()


def test_assignment_example(linker):
    text = (
        "Marie Curie conducted research on radioactivity in Paris "
        "and won the Nobel Prize in Physics."
    )
    result, graph = linker.link(text)
    got = {m["mention"]: (m["selected"] or {}).get("qid") for m in result["mentions"]}
    assert got == {
        "Marie Curie": "Q7186",
        "radioactivity": "Q11448",  # the assignment's illustrative Q11452 is general relativity
        "Paris": "Q90",
        "Nobel Prize in Physics": "Q38104",
    }
    assert len(graph) > 100


def test_popular_reading_is_overridden_by_context(linker):
    result, _ = linker.link("Paris, son of Priam, abducted Helen and started the Trojan War.")
    paris = next(m for m in result["mentions"] if m["mention"] == "Paris")
    assert paris["selected"]["qid"] == "Q167646"
