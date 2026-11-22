"""The worker's side of memory (brief 14 "Okuma"; K-14-0003 S4).

`HttpMemory` reaches the API's internal routes (service account, HttpRetriever pattern): recall
for `prepare`, the related items and the candidate write for the extraction job. A failed call
fails loudly (`memory_unavailable`): a run never goes on as if the user had no memory.

The block is the last part of the system message, between two markers, so the recorded copy of
the model's messages (`llm_call.request_messages`) can show `[memory: n items <ids>]` instead of
the text: run events are read by analysts and administrators, memory text is the user's only
(S4). What the model receives is unchanged.

r2 (K-14-0009): the markers never enter an item (`has_marker`, refused at every write), and the
mask works by position: from the block's start marker to the **last** end marker, so even an
item that reached the table with a marker cannot open the block. Whether memory works for a run
(setting, opt-out) is read in the worker from the database (`memory_port`): a run with memory
off makes no API call (MINOR-2 A).
"""

import re
from dataclasses import dataclass, field
from typing import Any

from ffcore.core.egress import EgressError, EgressTimeout, SafeOutboundClient
from ffcore.core.errors import ApiError
from ffcore.knowledge.chunking import approx_tokens

START = "[USER MEMORY]"
END = "[/USER MEMORY]"
HEADER = (
    "Known about the user (the user can see and delete these). They are context, not the "
    "question; when they conflict with what the user says now, the user's current words win."
)
# Greedy: the block is the last part of the system message; its end is the last end marker.
_BLOCK = re.compile(re.escape(START) + r".*" + re.escape(END), re.DOTALL)
_MARKERS = re.compile(r"\[/?user memory\]", re.IGNORECASE)


@dataclass
class Recall:
    off_reason: str | None
    items: list[dict[str, Any]] = field(default_factory=list)
    # `related` only: the effective settings' extraction model.
    extraction_model: str | None = None
    # `recall` only: ids that did not fit the memory share (not marked used, NOTE-2).
    dropped: list[str] = field(default_factory=list)


class MemoryConflict(Exception):
    """409 from the API: memory was turned off or the user opted out meanwhile."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def has_marker(text: str) -> bool:
    """The block's markers, in any case: such a text is never stored (`memory_text_invalid`)."""
    return _MARKERS.search(text) is not None


def recall_query(question: str) -> str:
    """The similarity query of a recall: the question within a run's input limit. A facade
    question may be longer (its messages have no such bound); the model still gets all of it,
    only the search for related items reads the first RUN_INPUT_MAX characters (MINOR-2)."""
    from ffcore.api.agents_schemas import RUN_INPUT_MAX

    return question[:RUN_INPUT_MAX]


def fit(items: list[dict[str, Any]], share: int) -> tuple[list[dict], list[str], int]:
    """Whole items within the memory share, in the order given (profile first); the rest are
    named as dropped (C13: no silent trim)."""
    kept, dropped, used = [], [], 0
    for item in items:
        cost = approx_tokens(item["text"]) + 4
        if used + cost > share:
            dropped.append(str(item["id"]))
            continue
        kept.append(item)
        used += cost
    return kept, dropped, used


def block(items: list[dict[str, Any]]) -> str:
    lines = [START, HEADER, *(f"- ({i['kind']}) {i['text']}" for i in items), END]
    return "\n".join(lines)


def mask(messages: list[dict[str, Any]], ids: list[str]) -> list[dict[str, Any]]:
    """The recorded copy of the model's messages without the memory text."""
    if not ids:
        return messages
    marker = f"[memory: {len(ids)} items {' '.join(ids)}]"
    out = []
    for message in messages:
        content = message.get("content")
        if message.get("role") == "system" and isinstance(content, str) and START in content:
            message = {**message, "content": _BLOCK.sub(marker, content)}
        out.append(message)
    return out


class HttpMemory:
    def __init__(self, settings, *, run_id, project_id, user_id) -> None:
        self._settings = settings
        self._ids = {"run_id": str(run_id), "project_id": str(project_id), "user_id": str(user_id)}

    async def _post(self, path: str, body: dict) -> dict:
        from ffcore.core.auth import service_authorization

        s = self._settings
        timeout = EgressTimeout(connect=5, read=s.llm_call_timeout_s, total=s.llm_call_timeout_s)
        try:
            async with SafeOutboundClient(timeout=timeout, settings=s) as client:
                response = await client.request(
                    "POST",
                    f"{s.internal_api_url}/internal/memories/{path}",
                    headers=service_authorization(s),
                    json=self._ids | body,
                )
        except EgressError as exc:
            # Denied, timed out or failed in transport: the same coded error (NOTE-3).
            error = ApiError(502, "api_error", "memory_unavailable", "The memory call failed.")
            error.detail = exc.code
            raise error from exc
        if response.status_code == 409:
            raise MemoryConflict(response.json()["error"]["code"])
        if response.status_code == 422:
            # A coded refusal of the API (e.g. `memory_requires_ner`): passed on as it is.
            error = response.json()["error"]
            raise ApiError(422, "invalid_request_error", error["code"], error["message"])
        if response.status_code != 200:
            try:
                code = response.json()["error"]["code"]
            except (ValueError, KeyError, TypeError):
                code = f"memory_http_{response.status_code}"
            error = ApiError(502, "api_error", "memory_unavailable", "The memory call failed.")
            error.detail = code
            raise error
        return response.json()

    async def recall(self, question: str, share: int) -> Recall:
        data = await self._post("recall", {"question": question, "share": share})
        return Recall(data["off_reason"], data["items"], dropped=data.get("dropped") or [])

    async def related(self, text: str) -> Recall:
        data = await self._post("related", {"text": text})
        return Recall(data["off_reason"], data["items"], data.get("extraction_model"))

    async def write(self, items: list[dict[str, Any]]) -> dict:
        return await self._post("candidates", {"items": items})


class OffMemory:
    """A run for which memory does nothing (off, opted out): its reason, without a call."""

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def recall(self, question: str, share: int) -> Recall:
        return Recall(self.reason)


async def memory_port(session, settings, run) -> "HttpMemory | OffMemory | None":
    """The worker's memory port of a run (MINOR-2 A): None without a user, `OffMemory` when the
    setting or the member's opt-out says no (read here from the database), else `HttpMemory`."""
    from ffcore.memory.settings import off_reason

    if run.user_id is None:
        return None
    reason = await off_reason(session, run.project_id, run.agent_id, run.user_id)
    if reason is not None:
        return OffMemory(reason)
    return HttpMemory(settings, run_id=run.id, project_id=run.project_id, user_id=run.user_id)
