"""16-2: the Confluence and Jira drivers against the in-process fake Atlassian (no real address).

Each test loads synthetic data into the fake, drives the driver through SafeOutboundClient
(127.0.0.1 allowed as an internal host, as 06b-2's fake agent) and reads `/_requests` to prove
what was asked: a delta asks only for changed pages, counts are the server's own, links stay on
the configured origin, 429 is waited out, and no person name reaches a rendered issue.
"""

import asyncio
import json
import threading
import urllib.request
from datetime import UTC, datetime, timedelta

import pytest

from ffcore.sources.base import SourceError, SourceSpec
from ffcore.sources.confluence import ConfluenceDriver, window_minutes
from ffcore.sources.jira import JiraDriver
from tests.fakes import fake_atlassian

PAT = "dummy-not-secret-pat-16-2"
OLD = (datetime.now(UTC) - timedelta(days=5)).isoformat()
NEW = (datetime.now(UTC) - timedelta(minutes=3)).isoformat()


@pytest.fixture
def fake():
    server = fake_atlassian.serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def control(base, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method="POST" if data else "GET")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def requests(base):
    return [r["path"] for r in control(base, "/_requests")["requests"]]


@pytest.fixture
def local(settings):
    return settings.model_copy(update={"allowed_internal_hosts": ["127.0.0.1"]})


def confluence(base, settings, deployment="server", **config):
    secret = (
        {"token": PAT}
        if deployment == "server"
        else {"email": "svc@example.test", "api_token": PAT}
    )
    spec = SourceSpec(
        id="c", kind="confluence", deployment=deployment, config={"base_url": base, **config}
    )
    driver = ConfluenceDriver(spec, secret, None, settings)
    driver._http._gaps = {"read": 0, "download": 0}  # no pacing in tests
    return driver


def jira(base, settings, deployment="server", **config):
    secret = (
        {"token": PAT}
        if deployment == "server"
        else {"email": "svc@example.test", "api_token": PAT}
    )
    spec = SourceSpec(
        id="j", kind="jira", deployment=deployment, config={"base_url": base, **config}
    )
    driver = JiraDriver(spec, secret, None, settings)
    driver._http._gaps = {"read": 0, "download": 0}
    return driver


def pages_state(n_old=60, auth=None):
    pages = [
        {
            "id": str(1000 + n),
            "space": "OPS",
            "title": f"Sayfa {n}",
            "body": f"<p>Metin {n}</p>",
            "when": OLD,
            "ancestors": [{"id": "999", "title": "Ana sayfa"}],
        }
        for n in range(n_old)
    ]
    # The ancestor is a page of its own (its read restriction is inherited by every child).
    pages.append(
        {"id": "999", "space": "OPS", "title": "Ana sayfa", "body": "<p>Kök</p>", "when": OLD}
    )
    pages.append(
        {
            "id": "2000",
            "space": "OPS",
            "title": "Yeni sayfa",
            "body": "<h2>Başlık</h2><p>Güncel</p>",
            "when": NEW,
            "ancestors": [{"id": "999", "title": "Ana sayfa"}],
            "restrictions": {"groups": ["Yonetim"], "users": ["kullanici1"]},
            "attachments": [{"title": "rapor.txt", "content": "ek metni", "when": NEW, "size": 8}],
        }
    )
    return {
        "auth": auth or [f"Bearer {PAT}"],
        "confluence": {"spaces": {"OPS": {}}, "pages": pages},
    }


async def collect(gen):
    return [x async for x in gen]


def test_16_2_confluence_full_listing_count_and_pagination(fake, local):
    control(fake, "/_state", pages_state())
    driver = confluence(fake, local, space_keys=["OPS"])

    async def go():
        count = await driver.count()
        items = await collect(driver.list_changes(None))
        raws = [await driver.fetch_raw(i) for i in items]
        await driver.aclose()
        return count, items, raws

    count, items, raws = asyncio.run(go())
    assert count == 62 and len(items) == 62
    paths = requests(fake)
    assert paths.count("/rest/api/content/search") == 2  # 50 + 12, bodies with the listing
    assert not any(p.startswith("/rest/api/content/1") for p in paths)  # no per-page fetch
    page = next(i for i in items if i.external_id == "2000")
    assert page.breadcrumb_parts == ("OPS", "Ana sayfa", "Yeni sayfa") and page.space == "OPS"
    rendered = driver.render(page, raws[items.index(page)])
    assert rendered.filename == "2000.md"
    assert rendered.content.decode().startswith("# Yeni sayfa\n\n## Başlık\n\nGüncel")


def test_16_2_confluence_delta_asks_only_for_the_changed_page(fake, local):
    control(fake, "/_state", pages_state())
    driver = confluence(fake, local)
    since = datetime.now(UTC) - timedelta(minutes=20)

    async def go():
        items = await collect(driver.list_changes(since))
        raw = await driver.fetch_raw(items[0])
        attachments = await collect(driver.list_attachments(items[0], raw))
        acl = await driver.acl(items[0], raw)
        await driver.aclose()
        return items, attachments, acl

    items, attachments, acl = asyncio.run(go())
    assert [i.external_id for i in items] == ["2000"]
    seen = control(fake, "/_requests")["requests"]
    assert seen[0]["query"]["cql"] == [
        f'type=page AND lastmodified >= now("-{window_minutes(since)}m")'
    ]
    assert [r["path"] for r in seen] == [
        "/rest/api/content/search",
        "/rest/api/content/2000/child/attachment",
        "/rest/api/content/2000/restriction/byOperation/read",
        "/rest/api/content/999/restriction/byOperation/read",
    ]
    assert [(a.name, a.size) for a in attachments] == [("rapor.txt", 8)]
    # A restricted page is its restriction only: `space:OPS` would open it to whoever the
    # space is mapped to (mappings are a union).
    assert acl.groups == ("group:Yonetim", "user:kullanici1")


@pytest.mark.parametrize(
    ("parent", "child", "groups"),
    [
        ({}, {}, ("space:OPS",)),
        ({"groups": ["A", "B"]}, {}, ("group:A", "group:B")),
        (
            {"groups": ["A", "B"], "users": ["u1"]},
            {"groups": ["B", "C"], "users": ["u1"]},
            ("group:B", "user:u1"),
        ),
        ({"groups": ["A"]}, {"groups": ["C"]}, ()),
    ],
    ids=["open", "inherited", "intersection", "disjoint-admin-only"],
)
def test_16_2_confluence_restrictions_are_inherited(fake, local, parent, child, groups):
    pages = [
        {
            "id": "10",
            "space": "OPS",
            "title": "Üst",
            "body": "<p>a</p>",
            "when": OLD,
            "restrictions": parent,
        },
        {
            "id": "11",
            "space": "OPS",
            "title": "Alt",
            "body": "<p>b</p>",
            "when": OLD,
            "ancestors": [{"id": "10", "title": "Üst"}],
            "restrictions": child,
        },
    ]
    control(
        fake,
        "/_state",
        {"auth": [f"Bearer {PAT}"], "confluence": {"spaces": {"OPS": {}}, "pages": pages}},
    )
    driver = confluence(fake, local)

    async def go():
        items = await collect(driver.list_changes(None))
        page = next(i for i in items if i.external_id == "11")
        acl = await driver.acl(page, await driver.fetch_raw(page))
        await driver.aclose()
        return acl

    # A page both levels restrict is readable only by who passes both (no group: admins only).
    assert asyncio.run(go()).groups == groups


def test_16_2_confluence_cloud_basic_auth_v1_search_v2_body(fake, local):
    import base64

    basic = "Basic " + base64.b64encode(f"svc@example.test:{PAT}".encode()).decode()
    control(fake, "/_state", pages_state(n_old=2, auth=[basic]))
    driver = confluence(fake, local, deployment="cloud")

    async def go():
        items = await collect(driver.list_changes(None))
        raw = await driver.fetch_raw(next(i for i in items if i.external_id == "2000"))
        await driver.aclose()
        return items, raw

    items, raw = asyncio.run(go())
    paths = requests(fake)
    assert paths[0] == "/wiki/rest/api/search" and "/wiki/api/v2/pages/2000" in paths
    rendered = driver.render(next(i for i in items if i.external_id == "2000"), raw)
    assert b"G\xc3\xbcncel" in rendered.content and rendered.breadcrumb[0] == "OPS"


def test_16_2_wrong_credentials_and_foreign_links(fake, local):
    control(fake, "/_state", pages_state(n_old=1, auth=["Bearer something-else"]))
    driver = confluence(fake, local)
    result = asyncio.run(driver.test_connection())
    assert not result.reachable and result.error_code == "source_auth_failed"
    with pytest.raises(SourceError) as error:
        driver._http.url("https://elsewhere.example.test/download/x")
    assert error.value.code == "foreign_url"
    asyncio.run(driver.aclose())


def test_16_2_rate_limit_is_waited_out(fake, local):
    control(fake, "/_state", pages_state(n_old=1))
    control(fake, "/_fault", {"rate_limit": 2, "retry_after": 7})
    driver = confluence(fake, local)
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    driver._http._sleep = fake_sleep
    assert asyncio.run(driver.count()) == 3
    assert [w for w in waits if w >= 1] == [7.0, 7.0]  # Retry-After honoured, then success
    control(fake, "/_fault", {"rate_limit": 10, "retry_after": 1})
    with pytest.raises(SourceError) as error:
        asyncio.run(driver.count())
    assert error.value.code == "rate_limited"
    asyncio.run(driver.aclose())


def issues_state():
    issues = [
        {
            "key": f"OPS-{n}",
            "fields": {
                "summary": f"Konu {n}",
                "updated": OLD,
                "created": OLD,
                "project": {"key": "OPS"},
                "status": {"name": "Done"},
                "assignee": {"displayName": "Ayşe Kaya"},
                "reporter": {"displayName": "Mehmet Demir"},
                "description": "h2. Kök neden\n{code:java}\nthrow new TimeoutException();\n{code}",
                "resolution": {"name": "Fixed", "description": "Zaman aşımı 30 sn yapıldı."},
                "comment": {
                    "comments": [
                        {
                            "author": {"displayName": "Ayşe Kaya"},
                            "body": "Yeniden denendi.",
                            "created": OLD,
                        },
                    ]
                },
                "security": {"name": "Yonetim"} if n == 0 else None,
                "attachment": [
                    {
                        "filename": "log.txt",
                        "size": 3,
                        "created": OLD,
                        "mimeType": "text/plain",
                        "content": "BASE/secure/attachment/1/log.txt",
                    }
                ]
                if n == 1
                else [],
            },
        }
        for n in range(150)
    ]
    issues[-1]["fields"]["updated"] = NEW
    return {"auth": [f"Bearer {PAT}"], "jira": {"projects": {"OPS": {}}, "issues": issues}}


def test_16_2_jira_dc_listing_count_render_without_names(fake, local):
    state = issues_state()
    for issue in state["jira"]["issues"]:
        for att in issue["fields"]["attachment"]:
            att["content"] = att["content"].replace("BASE", fake)
    control(fake, "/_state", state)
    driver = jira(fake, local, jql="project = OPS")

    async def go():
        count = await driver.count()
        items = await collect(driver.list_changes(None))
        raw = await driver.fetch_raw(items[0])
        second = await driver.fetch_raw(items[1])
        attachments = await collect(driver.list_attachments(items[1], second))
        acl = (await driver.acl(items[0], raw), await driver.acl(items[1], second))
        await driver.aclose()
        return count, items, raw, attachments, acl

    count, items, raw, attachments, (acl, acl_open) = asyncio.run(go())
    assert count == 150 and len(items) == 150
    seen = control(fake, "/_requests")["requests"]
    assert seen[0]["query"]["maxResults"] == ["0"]
    assert seen[1]["query"]["jql"] == ["(project = OPS) ORDER BY updated ASC"]
    text = driver.render(items[0], raw).content.decode()
    assert text.startswith("# OPS-0: Konu 0\n")
    assert "#### Kök neden" in text and "```java\nthrow new TimeoutException();\n```" in text
    assert "## Resolution\n\nZaman aşımı 30 sn yapıldı." in text
    assert "## Comment 1 (" in text and "Yeniden denendi." in text
    assert "Ayşe" not in text and "Mehmet" not in text  # K-16-0009 S1
    assert acl.groups == ("security:Yonetim",)  # the level narrows the project, not adds to it
    assert acl_open.groups == ("project:OPS",)
    assert [a.name for a in attachments] == ["log.txt"]


def test_16_2_jira_cloud_counts_by_listing_and_delta(fake, local):
    import base64

    state = issues_state()
    state["auth"] = ["Basic " + base64.b64encode(f"svc@example.test:{PAT}".encode()).decode()]
    control(fake, "/_state", state)
    driver = jira(fake, local, deployment="cloud")

    async def go():
        count = await driver.count()
        since = datetime.now(UTC) - timedelta(minutes=30)
        changed = await collect(driver.list_changes(since))
        await driver.aclose()
        return count, changed

    count, changed = asyncio.run(go())
    assert count == 150 and driver.count_method == "listing"
    assert [i.external_id for i in changed] == ["OPS-149"]
    paths = requests(fake)
    assert set(paths) == {"/rest/api/2/search/jql"}  # Cloud never calls the removed /search


def test_16_2_jira_refuses_order_by():
    from ffcore.sources.jira import JiraConfig

    with pytest.raises(ValueError, match="jql_order_by"):
        JiraConfig(base_url="https://jira.example.test", jql="project = OPS ORDER BY created")
