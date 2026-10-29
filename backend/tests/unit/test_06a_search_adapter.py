"""06a knowledge adapter (S4): the backend search API with the service account, a fresh
X-On-Behalf-Of for the run's user and X-Run-Id (C12). The HTTP client is replaced here; the live
stack run in the PR shows the real call."""

import asyncio
import uuid
from types import SimpleNamespace

from ffcore.core.auth import OBO_HEADER, verify_on_behalf_of
from ffcore.core.config import Settings
from ffcore.runtime import adapters
from tests.dummy import OBO_SECRET, SERVICE_TOKEN, SETTINGS_03A

SENT: list[dict] = []


class FakeClient:
    def __init__(self, *, timeout, settings):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def request(self, method, url, *, headers, json):
        SENT.append({"method": method, "url": url, "headers": headers, "json": json})
        hit = {
            "chunk_id": str(uuid.uuid4()),
            "document_id": str(uuid.uuid4()),
            "document_name": "d.txt",
            "page": None,
            "breadcrumb": "Madde 9",
            "text": "30 gün",
            "updated_at_source": None,
            "rerank_score": 0.7,
        }
        body = {"query_id": str(uuid.uuid4()), "hits": [hit], "threshold_mode": "rerank"}
        return SimpleNamespace(status_code=200, json=lambda: body)


def test_06a_5e_search_adapter_sends_service_obo_and_run_id(monkeypatch):
    settings = Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token=SERVICE_TOKEN,
        obo_jwt_secret=OBO_SECRET,
        internal_api_url="http://backend:8000",
        **SETTINGS_03A,
    )
    monkeypatch.setattr(adapters, "SafeOutboundClient", FakeClient)
    run_id, project_id, user_id, kb_id = (str(uuid.uuid4()) for _ in range(4))
    retriever = adapters.HttpRetriever(
        settings, None, run_id=run_id, project_id=project_id, user_id=user_id
    )
    retriever._kb_ids["sozlesmeler"] = kb_id
    hits, info = asyncio.run(retriever.search("sozlesmeler", "fesih", 4, []))
    sent = SENT[-1]
    assert sent["url"].endswith(f"/projects/{project_id}/knowledge-bases/{kb_id}/search")
    assert sent["json"] == {"query": "fesih", "top_k": 4}
    assert sent["headers"]["X-Run-Id"] == run_id
    assert sent["headers"]["Authorization"] == f"Bearer {SERVICE_TOKEN}"
    claims = verify_on_behalf_of(
        sent["headers"][OBO_HEADER], audience=settings.obo_audience, settings=settings
    )
    assert (claims.sub, claims.project_id) == (user_id, project_id)
    assert hits[0].document_name == "d.txt" and info["threshold_mode"] == "rerank"
