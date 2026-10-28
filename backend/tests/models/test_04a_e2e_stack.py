"""04a acceptance 1, 2 and 14 against the running compose stack with the real models.

Needs: `docker compose up -d --wait` (backend, worker, migrate, postgres, redis), a superadmin
created with `python -m ffcore.cli create-superadmin` and E2E_EMAIL / E2E_PASSWORD (test values,
never real credentials), RUN_MODEL_TESTS=1. Runs from the tools container on the compose network.
This is also the end-to-end proof of the worker → POST /internal/embed path (C10).
"""

import concurrent.futures
import os
import time
import uuid
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.models

BACKEND = os.environ.get("E2E_BACKEND_URL", "http://backend:8000")
API = f"{BACKEND}/api/v1"
CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "samples"
    / "contracts"
    / "SZL-2024-011_cihaz-bakim.pdf"
)
ORIGIN = os.environ.get("E2E_ORIGIN", "http://localhost:3000")  # in CONSOLE_ORIGINS (C6)
INDEX_LIMIT_S = 120  # brief 04 acceptance 1: 10-page contract indexed within 2 minutes (CPU)


@pytest.fixture(scope="module")
def session():
    email, password = os.environ.get("E2E_EMAIL"), os.environ.get("E2E_PASSWORD")
    if not email or not password:
        pytest.fail("E2E_EMAIL / E2E_PASSWORD not set (create-superadmin first)")
    # Search runs the CPU reranker; its duration is FOLLOWUP-77, not this acceptance.
    client = httpx.Client(timeout=900, headers={"Origin": ORIGIN})
    deadline = time.time() + 900
    while time.time() < deadline:  # the backend warms the models first
        ready = client.get(f"{BACKEND}/readyz")
        if ready.status_code == 200:
            break
        time.sleep(5)
    assert ready.status_code == 200, ready.text
    login = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    # The session cookie is Secure; over the plain compose network it is sent explicitly.
    client.headers["Cookie"] = f"ffcore_session={login.cookies['ffcore_session']}"
    yield client
    client.close()


@pytest.fixture(scope="module")
def indexed(session):
    project = session.post(
        f"{API}/projects", json={"key": f"e2e-{uuid.uuid4().hex[:6]}", "name": "E2E"}
    ).json()
    kb = session.post(
        f"{API}/projects/{project['id']}/knowledge-bases",
        json={"key": "sozlesmeler", "name": "Sözleşmeler"},
    ).json()
    url = f"{API}/projects/{project['id']}/knowledge-bases/{kb['id']}"
    started = time.time()
    upload = session.post(
        f"{url}/documents",
        files={"files": (CONTRACT.name, CONTRACT.read_bytes(), "application/pdf")},
        data={"acl_roles": "analyst"},
    )
    assert upload.status_code == 202, upload.text
    document_id = upload.json()["data"][0]["document"]["id"]
    while True:
        document = session.get(f"{url}/documents/{document_id}").json()
        if document["status"] in ("indexed", "failed", "timeout", "skipped"):
            break
        assert time.time() - started < 900, document
        time.sleep(2)
    elapsed = time.time() - started
    print(
        f"\n10-page contract: {document['status']} in {elapsed:.1f} s, "
        f"{document['chunk_count']} chunks, converter {document['convert_engine']} "
        f"({document['convert_seconds']} s)"
    )
    return url, document, elapsed


def test_04a_1_ten_page_contract_indexed_within_two_minutes(indexed):
    _, document, elapsed = indexed
    assert document["status"] == "indexed", document
    assert document["page_count"] == 10
    assert elapsed <= INDEX_LIMIT_S, f"{elapsed:.1f} s"


def test_04a_2_termination_notice_in_top3(session, indexed):
    url, _, _ = indexed
    response = session.post(f"{url}/search", json={"query": "fesih bildirim süresi", "top_k": 3})
    assert response.status_code == 200, response.text
    hits = response.json()["hits"]
    print("\n" + "\n".join(f"{h['rerank_score']:.3f} {h['breadcrumb']}" for h in hits))
    assert any("10.1" in h["text"] or "Fesih" in h["breadcrumb"] for h in hits[:3]), hits


def test_04a_14_health_responsive_under_search_load(session, indexed):
    """D6: while 10 searches run (the reranker busy, CPU-bound in worker threads), /healthz
    keeps answering under 1 s. Search duration is a separate measurement (FOLLOWUP-77)."""
    url, _, _ = indexed
    headers = {"Origin": ORIGIN, "Cookie": session.headers["Cookie"]}

    def one_search(_):
        with httpx.Client(timeout=1800, headers=headers) as c:
            started = time.time()
            status = c.post(f"{url}/search", json={"query": "bakım ziyareti raporu"}).status_code
            return status, time.time() - started

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        searches = [pool.submit(one_search, i) for i in range(10)]
        time.sleep(2.0)  # the reranker is busy now
        latencies = []
        while not all(f.done() for f in searches) and len(latencies) < 60:
            started = time.time()
            assert httpx.get(f"{BACKEND}/healthz", timeout=5).status_code == 200
            latencies.append(time.time() - started)
            time.sleep(1.0)
        results = [f.result() for f in searches]
    worst = max(latencies)
    print(
        f"\n/healthz worst {worst * 1000:.0f} ms over {len(latencies)} probes during 10 "
        f"concurrent searches; search seconds: {sorted(round(s) for _, s in results)}"
    )
    assert [status for status, _ in results] == [200] * 10
    assert latencies and worst < 1.0
