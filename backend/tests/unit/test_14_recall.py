"""14: the memory block, its budget fit (C13) and the recorded copy's mask (K-14-0003 S4), and
the worker's HTTP client (fail-loud, 409 as a conflict)."""

import asyncio

import pytest

from ffcore.core.errors import ApiError
from ffcore.memory import recall

ITEMS = [
    {"id": "p1", "kind": "profile", "text": "Kardiyoloji bölüm sorumlusu."},
    {"id": "f1", "kind": "preference", "text": "Tabloları TL cinsinden ister."},
    {"id": "f2", "kind": "fact", "text": "x " * 400},
]


def test_14_fit_keeps_whole_items_in_order_and_names_the_dropped():
    kept, dropped, used = recall.fit(ITEMS, 40)
    assert [i["id"] for i in kept] == ["p1", "f1"]
    assert dropped == ["f2"]
    assert 0 < used <= 40


def test_14_fit_with_no_share_drops_everything():
    kept, dropped, used = recall.fit(ITEMS, 0)
    assert (kept, dropped, used) == ([], ["p1", "f1", "f2"], 0)


def test_14_block_says_the_user_can_see_and_delete_and_that_current_words_win():
    text = recall.block(ITEMS[:2])
    assert text.startswith(recall.START) and text.endswith(recall.END)
    assert "the user can see and delete these" in text
    assert "the user's current words win" in text
    assert "- (profile) Kardiyoloji bölüm sorumlusu." in text


def test_14_mask_replaces_only_the_block_of_the_system_message():
    system = "RULES\n\n" + recall.block(ITEMS[:2])
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "Soru [USER MEMORY] kalsın [/USER MEMORY]"},
    ]
    masked = recall.mask(messages, ["p1", "f1"])
    assert masked[0]["content"] == "RULES\n\n[memory: 2 items p1 f1]"
    assert masked[1] == messages[1]
    assert messages[0]["content"] == system  # the model's copy is not changed
    assert recall.mask(messages, []) is messages


class _Response:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def _client(status, body, seen):
    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, method, url, headers, json):
            seen.append((method, url, headers, json))
            return _Response(status, body)

    return Client


class _Settings:
    internal_api_url = "http://backend:8000"
    llm_call_timeout_s = 5
    service_token = None


@pytest.fixture
def auth(monkeypatch):
    import ffcore.core.auth as core_auth

    monkeypatch.setattr(core_auth, "service_authorization", lambda s: {"Authorization": "x"})


def _memory():
    return recall.HttpMemory(_Settings(), run_id="r", project_id="p", user_id="u")


def test_14_http_recall_posts_the_run_ids(monkeypatch, auth):
    seen = []
    monkeypatch.setattr(
        recall, "SafeOutboundClient", _client(200, {"off_reason": None, "items": ITEMS[:1]}, seen)
    )
    found = asyncio.run(_memory().recall("Soru"))
    assert (found.off_reason, found.items) == (None, ITEMS[:1])
    ((method, url, _, body),) = seen
    assert (method, url) == ("POST", "http://backend:8000/internal/memories/recall")
    assert body == {"run_id": "r", "project_id": "p", "user_id": "u", "question": "Soru"}


def test_14_http_failure_is_loud(monkeypatch, auth):
    monkeypatch.setattr(recall, "SafeOutboundClient", _client(500, {"nope": 1}, []))
    with pytest.raises(ApiError) as raised:
        asyncio.run(_memory().recall("Soru"))
    assert raised.value.code == "memory_unavailable"
    assert raised.value.detail == "memory_http_500"


def test_14_http_conflict_is_its_own_error(monkeypatch, auth):
    body = {"error": {"code": "memory_opted_out"}}
    monkeypatch.setattr(recall, "SafeOutboundClient", _client(409, body, []))
    with pytest.raises(recall.MemoryConflict) as raised:
        asyncio.run(_memory().write([]))
    assert raised.value.code == "memory_opted_out"
