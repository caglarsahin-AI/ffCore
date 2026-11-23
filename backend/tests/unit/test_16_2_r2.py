"""16-2 r2 (R-16-0013, K-16-0027): restricted and internal Jira comments stay out of the
document, mentions are dropped, a weekly full run, downloads fail loud on any non-2xx answer,
pagination cannot loop, a broken Retry-After falls back to the default wait, personal space keys
are quoted, `script`/`style` bodies are dropped, security levels are named per project."""

import asyncio
import json
import math
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

from ffcore.sources import scheduler
from ffcore.sources.atlassian import BACKOFF_CAP_S, AtlassianHttp, _retry_after
from ffcore.sources.base import ItemRef, RawPayload, SourceError, SourceSpec
from ffcore.sources.confluence import ConfluenceDriver
from ffcore.sources.jira import JiraDriver, wiki_to_markdown
from ffcore.sources.storage_format import to_markdown

REPO = Path(__file__).resolve().parents[3]
PAT = "dummy-not-secret-pat-16-2-r2"


def jira(settings, deployment="server", base="https://jira.example.test"):
    secret = (
        {"token": PAT} if deployment == "server" else {"email": "s@example.test", "api_token": PAT}
    )
    spec = SourceSpec(id="j", kind="jira", deployment=deployment, config={"base_url": base})
    return JiraDriver(spec, secret, None, settings)


def confluence(settings, **config):
    spec = SourceSpec(
        id="c",
        kind="confluence",
        deployment="server",
        config={"base_url": "https://wiki.example.test", **config},
    )
    return ConfluenceDriver(spec, {"token": PAT}, None, settings)


def issue_raw(**fields):
    issue = {
        "key": "OPS-1",
        "fields": {"summary": "Zaman aşımı", "project": {"key": "OPS"}, **fields},
    }
    return RawPayload(content=json.dumps(issue).encode(), ext="json")


ITEM = ItemRef(external_id="OPS-1", title="OPS-1", space="OPS")


# -- MAJOR-1 -----------------------------------------------------------------------------


def test_16_2_r2_restricted_and_internal_comments_stay_out(settings):
    raw = issue_raw(
        comment={
            "comments": [
                {"body": "Herkese açık çözüm notu.", "created": "2026-03-01T10:00:00.000+0300"},
                {
                    "body": "Yalnız yöneticiler: müşteri adı X.",
                    "visibility": {"type": "role", "value": "Administrators"},
                },
                {
                    "body": "Yalnız ekip: iç maliyet.",
                    "visibility": {"type": "group", "value": "jira-ops"},
                },
                {"body": "Servis masası iç notu.", "jsdPublic": False},
                {"body": "Servis masası açık yanıtı.", "jsdPublic": True},
            ]
        }
    )
    text = jira(settings).render(ITEM, raw).content.decode()
    assert "Herkese açık çözüm notu." in text and "Servis masası açık yanıtı." in text
    for hidden in ("müşteri adı X", "iç maliyet", "Servis masası iç notu"):
        assert hidden not in text
    # Numbering counts the comments in the document only (no gap that tells one was left out).
    assert (
        "## Comment 1 (2026-03-01)" in text
        and "## Comment 2" in text
        and "## Comment 3" not in text
    )


# -- MINOR-3 -----------------------------------------------------------------------------


def test_16_2_r2_mentions_are_dropped():
    text = wiki_to_markdown("Sorumlu [~akaya] ve [~accountid:557058:0f1e] ile görüşüldü.")
    assert "akaya" not in text and "accountid" not in text and "[~" not in text
    assert text == "Sorumlu ve ile görüşüldü."
    storage = (
        '<p>Sorumlu <ac:link><ri:user ri:userkey="8a7f"/></ac:link> ve '
        '<ac:link><ri:user ri:account-id="557058"/><ac:link-body>Ayse Kaya</ac:link-body></ac:link>'
        ' ile görüşüldü; <ac:link><ri:page ri:content-title="Kurallar"/></ac:link>'
        " sayfasına bakın.</p>"
    )
    md = to_markdown(storage).markdown
    assert "Ayse" not in md and "8a7f" not in md and "557058" not in md
    assert "Kurallar" in md  # a page link keeps its title


# -- NOTE-4 ------------------------------------------------------------------------------


def test_16_2_r2_script_and_style_bodies_are_dropped():
    md = to_markdown(
        "<p>Metin</p><script>alert(1)</script><style>p{color:red}</style><p>Son</p>"
    ).markdown
    assert "alert" not in md and "color" not in md and "Metin" in md and "Son" in md


# -- NOTE-3 ------------------------------------------------------------------------------


def test_16_2_r2_security_level_is_named_per_project(settings):
    acl = asyncio.run(jira(settings).acl(ITEM, issue_raw(security={"name": "Yonetim"})))
    assert acl.groups == ("security:OPS/Yonetim",)


# -- NOTE-7 ------------------------------------------------------------------------------


def test_16_2_r2_space_keys_are_quoted_in_cql(settings):
    driver = confluence(settings, space_keys=["OPS", "~jdoe"])
    assert driver._cql() == 'type=page AND space in ("OPS","~jdoe")'


# -- NOTE-6 ------------------------------------------------------------------------------


class _Answer:
    def __init__(self, value):
        self.headers = {} if value is None else {"Retry-After": value}


@pytest.mark.parametrize("value", ["nan", "inf", "-5", "abc", "Wed, 21 Oct 2026 07:28:00 GMT"])
def test_16_2_r2_broken_retry_after_falls_back_to_the_default_wait(value):
    for attempt in (1, 2, 3):
        wait = _retry_after(_Answer(value), attempt)
        assert math.isfinite(wait) and wait == min(2.0 ** (attempt - 1), BACKOFF_CAP_S)


def test_16_2_r2_retry_after_is_capped():
    assert _retry_after(_Answer("1e9"), 1) == BACKOFF_CAP_S
    assert _retry_after(_Answer("7"), 1) == 7.0


# -- NOTE-1 ------------------------------------------------------------------------------


def test_16_2_r2_a_self_pointing_next_link_is_a_pagination_loop(settings):
    driver = confluence(settings)

    async def same_page(link, params=None):
        return {"results": [], "_links": {"next": "/rest/api/content/search?start=50"}}

    driver._http.get_json = same_page

    async def go():
        return [x async for x in driver.list_changes(None)]

    with pytest.raises(SourceError) as error:
        asyncio.run(go())
    assert error.value.code == "pagination_loop"


def test_16_2_r2_a_repeated_jira_page_token_is_a_pagination_loop(settings):
    driver = jira(settings, deployment="cloud")

    async def same_token(link, params=None):
        return {"issues": [{"key": "OPS-1"}], "nextPageToken": "abc"}

    driver._http.get_json = same_token
    with pytest.raises(SourceError) as error:
        asyncio.run(driver.count())
    assert error.value.code == "pagination_loop"


# -- MINOR-2 -----------------------------------------------------------------------------


class _Odd(BaseHTTPRequestHandler):
    seen: list[str] = []

    def log_message(self, *args):
        pass

    def do_GET(self):  # noqa: N802
        _Odd.seen.append(self.path)
        status = int(self.path.split("/")[2].split("?")[0])
        body = b"<html>not the file</html>"
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def odd():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Odd)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _Odd.seen = []
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.mark.parametrize("status", [302, 304, 401, 500])
def test_16_2_r2_a_download_answer_other_than_2xx_fails_loud(settings, odd, status):
    local = settings.model_copy(update={"allowed_internal_hosts": ["127.0.0.1"]})
    http = AtlassianHttp(odd, f"Bearer {PAT}", local, read_gap=0, download_gap=0)

    async def go():
        async with http.stream(f"/status/{status}") as chunks:
            return b"".join([c async for c in chunks])

    try:
        # A 3xx without Location used to stream its body as the attachment (R-16-0013 MINOR-2).
        with pytest.raises(SourceError) as error:
            asyncio.run(go())
        assert error.value.code == "attachment_download_failed"
    finally:
        asyncio.run(http.aclose())


def test_16_2_r2_jira_attachment_download_asks_without_redirect(settings, odd):
    local = settings.model_copy(update={"allowed_internal_hosts": ["127.0.0.1"]})
    driver = jira(local, base=odd)
    driver._http._gaps = {"read": 0, "download": 0}
    from ffcore.sources.base import AttachmentRef

    attachment = AttachmentRef(name="log.txt", size=3, modified_at=None, ref=f"{odd}/status/200")

    async def go():
        async with driver.fetch_attachment(ITEM, attachment) as chunks:
            return b"".join([c async for c in chunks])

    assert asyncio.run(go()) == b"<html>not the file</html>"
    assert _Odd.seen == ["/status/200?redirect=false"]
    asyncio.run(driver.aclose())


# -- MINOR-1 -----------------------------------------------------------------------------

NOW = datetime(2026, 11, 23, 2, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("last_full", "every_days", "mode"),
    [
        (NOW - timedelta(days=8), 7, "full"),
        (NOW - timedelta(days=7), 7, "full"),
        (NOW - timedelta(days=6, hours=23), 7, "delta"),
        (None, 7, "full"),  # no completed full run yet
        (NOW - timedelta(days=30), 0, "delta"),  # 0 turns the weekly full off
        (None, 0, "delta"),
    ],
)
def test_16_2_r2_scheduled_mode(last_full, every_days, mode):
    assert scheduler.scheduled_mode(last_full, NOW, every_days) == mode


def test_16_2_r2_full_sync_every_days_setting(settings):
    assert settings.full_sync_every_days == 7
    with pytest.raises(ValueError):
        settings.model_validate({**settings.model_dump(), "full_sync_every_days": -1})
    assert "\nFULL_SYNC_EVERY_DAYS=7" in (REPO / ".env.example").read_text(encoding="utf-8")
    compose = yaml.safe_load((REPO / "deploy" / "docker-compose.yml").read_text(encoding="utf-8"))
    assert compose["services"]["sync-worker"]["environment"]["FULL_SYNC_EVERY_DAYS"] == (
        "${FULL_SYNC_EVERY_DAYS:-7}"
    )
