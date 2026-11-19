"""04b-2 slice 2, D6 / FOLLOWUP-89: a metadata filter with a list value is an IN filter on both
vector drivers and in the lexical leg; the internal key search takes the same filters (an
unknown field there was ignored, so a scope would have been dropped silently; that test is in
test_04b_2_scope_key_search.py, on 04a's fixtures)."""

from tests.integration import test_04a_review_r1_acl as r1
from tests.integration.test_04a_api import PROSE
from tests.integration.test_04a_review_r1_acl import drain, kb_url
from tests.integration.test_04a_review_r1_acl import upload as r1_upload

# 04a r1's fixtures on pgvector and Qdrant.
backend = r1.backend
world = r1.world

SOURCES = {"ocr.md": "confluence:OCR", "pay.md": "jira:PAY", "hr.md": "confluence:HR"}
BODY = "# Bakım\n\n" + PROSE * 6


def _set_sources(pg, kb_id):
    for name, source in SOURCES.items():
        pg.execute(
            "UPDATE documents SET metadata = jsonb_build_object('source', %s::text)"
            " WHERE kb_id = %s AND filename = %s",
            (source, kb_id, name),
        )


def _names(response):
    assert response.status_code == 200, response.text
    return {h["document_name"] for h in response.json()["hits"]}


def test_04b_2_89_search_in_filter_on_both_drivers(world, pg):
    for name in SOURCES:
        assert r1_upload(world, world["admin"], name, BODY + name).status_code == 202
    _set_sources(pg, world["kb"])  # before indexing: Qdrant payloads carry the metadata
    drain(world)
    url = kb_url(world, f"/{world['kb']}/search")

    def search(metadata):
        body = {"query": "bakım hizmeti rapor", "filters": {"metadata": metadata}}
        return _names(world["admin"].post(url, json=body))

    assert search({"source": ["confluence:OCR", "jira:PAY"]}) == {"ocr.md", "pay.md"}
    assert search({"source": ["confluence:HR"]}) == {"hr.md"}
    assert search({"source": "confluence:HR"}) == {"hr.md"}  # scalar equality as before
    assert search({"source": ["confluence:"]}) == set()  # exact match, no prefix
    empty = world["admin"].post(url, json={"query": "x", "filters": {"metadata": {"source": []}}})
    assert empty.status_code == 422
