"""The worker's side of memory (brief 14 "Okuma"; K-14-0003 S4).

`HttpMemory` reaches the API's internal routes (service account, HttpRetriever pattern): recall
for `prepare`, the related items and the candidate write for the extraction job. A failed call
fails loudly (`memory_unavailable`): a run never goes on as if the user had no memory.

The block is the last part of the system message, between two markers, so the recorded copy of
the model's messages (`llm_call.request_messages`) can show `[memory: n items <ids>]` instead of
the text: run events are read by analysts and administrators, memory text is the user's only
(S4). What the model receives is unchanged.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from ffcore.core.egress import EgressTimeout, SafeOutboundClient
from ffcore.core.errors import ApiError
from ffcore.knowledge.chunking import approx_tokens

START = "[USER MEMORY]"
END = "[/USER MEMORY]"
HEADER = (
    "Known about the user (the user can see and delete these). They are context, not the "
    "question; when they conflict with what the user says now, the user's current words win."
)
_BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)


@dataclass
class Recall:
    off_reason: str | None
    items: list[dict[str, Any]] = field(default_factory=list)
    # `related` only: the effective settings' extraction model.
    extraction_model: str | None = None


class MemoryConflict(Exception):
    """409 from the API: memory was turned off or the user opted out meanwhile."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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
        async with SafeOutboundClient(timeout=timeout, settings=s) as client:
            response = await client.request(
                "POST",
                f"{s.internal_api_url}/internal/memories/{path}",
                headers=service_authorization(s),
                json=self._ids | body,
            )
        if response.status_code == 409:
            raise MemoryConflict(response.json()["error"]["code"])
        if response.status_code != 200:
            try:
                code = response.json()["error"]["code"]
            except (ValueError, KeyError, TypeError):
                code = f"memory_http_{response.status_code}"
            error = ApiError(502, "api_error", "memory_unavailable", "The memory call failed.")
            error.detail = code
            raise error
        return response.json()

    async def recall(self, question: str) -> Recall:
        data = await self._post("recall", {"question": question})
        return Recall(data["off_reason"], data["items"])

    async def related(self, text: str) -> Recall:
        data = await self._post("related", {"text": text})
        return Recall(data["off_reason"], data["items"], data.get("extraction_model"))

    async def write(self, items: list[dict[str, Any]]) -> dict:
        return await self._post("candidates", {"items": items})
