"""04b-2 slice 2, D6 / FOLLOWUP-89 (K-04B-0002 S5 A, K-04B-0021).

`knowledge[].filter.scope` is a list of `documents.metadata.source` values (exact match, IN).
C5 additive: a metadata filter value may be a list (pg `= ANY`, Qdrant `match.any`). The agent
definition no longer refuses a scope (06a 422 removed) and the runtime's search sends it.
"""

import asyncio
import uuid

import pytest
from pydantic import ValidationError

from ffcore.core.config import Settings
from ffcore.knowledge.vectorstore.base import VectorFilters
from ffcore.knowledge.vectorstore.qdrant import qdrant_filter
from ffcore.runtime import adapters
from ffcore.runtime.definition import parse_definition
from tests.dummy import OBO_SECRET, SERVICE_TOKEN, SETTINGS_03A
from tests.unit import test_06a_search_adapter as search_adapter
from tests.unit.test_06a_definition import MINIMAL

SCOPE = ["confluence:OCR", "jira:PAY"]


def test_04b_2_89_list_value_is_kept_as_a_tuple():
    filters = VectorFilters.from_mapping({"metadata": {"source": SCOPE, "lang": "tr"}})
    assert filters.metadata == (("lang", "tr"), ("source", tuple(SCOPE)))
    hash(filters)  # still a frozen, hashable value


def test_04b_2_89_qdrant_list_value_is_match_any():
    filters = VectorFilters.from_mapping({"metadata": {"source": SCOPE}})
    must = qdrant_filter(uuid.uuid4(), filters)["must"]
    assert {"key": "metadata.source", "match": {"any": SCOPE}} in must


def test_04b_2_89_empty_list_is_refused():
    with pytest.raises(ValueError):
        VectorFilters.from_mapping({"metadata": {"source": []}})


def test_04b_2_89_definition_accepts_scope():
    knowledge = [{"kb_key": "k", "mode": "always", "filter": {"scope": SCOPE}}]
    parsed = parse_definition({**MINIMAL, "knowledge": knowledge})  # no 422 any more
    assert parsed.knowledge[0].filter.scope == SCOPE


def test_04b_2_89_blank_scope_value_is_refused():
    knowledge = [{"kb_key": "k", "mode": "always", "filter": {"scope": [" "]}}]
    with pytest.raises(ValidationError):
        parse_definition({**MINIMAL, "knowledge": knowledge})


def test_04b_2_89_adapter_sends_scope_as_source_filter(monkeypatch):
    settings = Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token=SERVICE_TOKEN,
        obo_jwt_secret=OBO_SECRET,
        internal_api_url="http://backend:8000",
        **SETTINGS_03A,
    )
    monkeypatch.setattr(adapters, "SafeOutboundClient", search_adapter.FakeClient)
    run_id, project_id, user_id, kb_id = (str(uuid.uuid4()) for _ in range(4))
    retriever = adapters.HttpRetriever(
        settings, None, run_id=run_id, project_id=project_id, user_id=user_id
    )
    retriever._kb_ids["sozlesmeler"] = kb_id
    asyncio.run(retriever.search("sozlesmeler", "fesih", 4, SCOPE))
    assert search_adapter.SENT[-1]["json"] == {
        "query": "fesih",
        "top_k": 4,
        "filters": {"metadata": {"source": SCOPE}},
    }
    asyncio.run(retriever.search("sozlesmeler", "fesih", 4, []))
    assert "filters" not in search_adapter.SENT[-1]["json"]  # no scope: no filter at all
