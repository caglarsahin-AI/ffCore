"""16-2: the fake Atlassian server answers the queries the drivers send and refuses others, so
a driver bug shows as a failing test (the fake never guesses)."""

import json
import threading
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest

from tests.fakes import fake_atlassian

OLD = (datetime.now(UTC) - timedelta(days=3)).isoformat()
NEW = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()
STATE = {
    "auth": ["Bearer dummy-not-secret-pat"],
    "confluence": {
        "spaces": {"OPS": {}, "GIZ": {"permitted": False}},
        "pages": [
            {"id": "11", "space": "OPS", "title": "Eski", "body": "<p>a</p>", "when": OLD},
            {
                "id": "12",
                "space": "OPS",
                "title": "Yeni",
                "body": "<p>b</p>",
                "when": NEW,
                "attachments": [{"title": "rapor.txt", "content": "metin", "when": NEW}],
            },
            {"id": "13", "space": "GIZ", "title": "Gizli", "body": "<p>c</p>", "when": NEW},
        ],
    },
    "jira": {
        "projects": {"OPS": {}},
        "issues": [
            {"key": "OPS-1", "fields": {"summary": "s1", "updated": OLD}},
            {"key": "OPS-2", "fields": {"summary": "s2", "updated": NEW}},
        ],
    },
}


@pytest.fixture
def fake():
    server = fake_atlassian.serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    call(base, "/_state", STATE)
    yield base
    server.shutdown()


def call(base, path, body=None, token="dummy-not-secret-pat"):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method="POST" if data else "GET")
    request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw[:1] in (b"{", b"[") else raw
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def test_16_2_fake_confluence_listing_count_delta_and_permissions(fake):
    cql = quote("type=page AND space in (OPS,GIZ)")
    status, body = call(fake, f"/rest/api/search?cql={cql}&limit=1")
    assert status == 200 and body["totalSize"] == 2  # GIZ is not permitted
    delta = quote('type=page AND lastmodified >= now("-10m")')
    _, listed = call(fake, f"/rest/api/content/search?cql={delta}&expand=body.storage&limit=50")
    assert [p["id"] for p in listed["results"]] == ["12"]
    assert listed["results"][0]["body"]["storage"]["value"] == "<p>b</p>"
    _, cloud = call(fake, "/wiki/api/v2/pages/12?body-format=storage")
    assert cloud["body"]["storage"]["value"] == "<p>b</p>"
    _, att = call(fake, "/rest/api/content/12/child/attachment")
    status, raw = call(fake, att["results"][0]["_links"]["download"])
    assert status == 200 and raw == b"metin"
    assert call(fake, "/rest/api/content/13/child/attachment")[0] == 404


def test_16_2_fake_jira_dc_and_cloud(fake):
    jql = quote('project in (OPS) AND updated >= "-10m" ORDER BY updated ASC')
    _, dc = call(fake, f"/rest/api/2/search?jql={jql}&maxResults=100")
    assert dc["total"] == 1 and dc["issues"][0]["key"] == "OPS-2"
    everything = quote("ORDER BY updated ASC")
    _, page1 = call(fake, f"/rest/api/2/search/jql?jql={everything}&maxResults=1")
    assert page1["issues"][0]["key"] == "OPS-1" and page1["nextPageToken"] == "1"
    _, page2 = call(fake, f"/rest/api/2/search/jql?jql={everything}&maxResults=1&nextPageToken=1")
    assert page2["issues"][0]["key"] == "OPS-2" and "nextPageToken" not in page2


def test_16_2_fake_refuses_and_records(fake):
    assert call(fake, "/rest/api/search?cql=" + quote("text ~ x"))[0] == 400
    assert call(fake, "/rest/api/2/search?jql=" + quote("assignee = me"))[0] == 400
    assert call(fake, "/rest/api/search?cql=type%3Dpage", token="wrong")[0] == 401
    call(fake, "/_fault", {"rate_limit": 1, "retry_after": 2})
    status, _ = call(fake, "/rest/api/search?cql=type%3Dpage&limit=1")
    assert status == 429
    _, seen = call(fake, "/_requests")
    assert [r["path"] for r in seen["requests"]][-1] == "/rest/api/search"
    call(fake, "/_reset", {})
    assert call(fake, "/_requests")[1]["requests"] == []
