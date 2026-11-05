"""Langfuse public REST API for exams (09): datasets, items, dataset runs, scores.

Measured on the pinned server 3.120.0 (state/pr/09.md, L1-L16, K-09-0006):
- The SDK (`langfuse==4.15.1`) cannot parse this server's dataset item responses (missing
  `media_references`), so datasets go through REST with SafeOutboundClient (C5); the SDK stays
  for traces only (02).
- Items and scores are upserted by id (L3, L10): seeding and re-scoring are idempotent.
- A dataset run opens with its first run item, linked to an existing trace (L5): the 06a run's
  own trace becomes the exam item's trace; no second trace is made.
- Neither v1 nor v2 `GET /scores` honors a trace filter (`traceId`, `traceIds`): both return
  every score silently (L12, re-measured on the stack). Scores are read by their deterministic
  ids (`scoreIds`), and every returned row is checked; a foreign row is a loud error (ARCH-06).
"""

import base64
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

from ffcore.core.config import Settings
from ffcore.core.egress import EgressError, EgressTimeout, SafeOutboundClient

TIMEOUT = EgressTimeout(connect=5, read=30, total=60)
PAGE = 100
# Score ids per v2 call (ids are ~45 characters; keeps the query string short).
SCORE_IDS_PER_CALL = 50


class LangfuseApiError(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class Transport(Protocol):
    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: Any = None,
    ) -> Any: ...


@dataclass(frozen=True)
class RunItem:
    item_id: str
    trace_id: str


class LangfuseApi:
    def __init__(self, settings: Settings, transport: Transport | None = None) -> None:
        if not (
            settings.langfuse_host and settings.langfuse_public_key and settings.langfuse_secret_key
        ):
            raise LangfuseApiError(
                "langfuse_not_configured", "exams need LANGFUSE_HOST and the project key pair"
            )
        self._base = settings.langfuse_host.rstrip("/")
        pair = (
            f"{settings.langfuse_public_key.get_secret_value()}:"
            f"{settings.langfuse_secret_key.get_secret_value()}"
        )
        self._auth = "Basic " + base64.b64encode(pair.encode()).decode()
        self._settings = settings
        self._transport = transport

    async def _call(self, method: str, path: str, *, params=None, json=None) -> Any:
        headers = {"Authorization": self._auth, "Content-Type": "application/json"}
        try:
            if self._transport is not None:
                response = await self._transport.request(
                    method, self._base + path, headers=headers, params=params, json=json
                )
            else:
                async with SafeOutboundClient(timeout=TIMEOUT, settings=self._settings) as client:
                    response = await client.request(
                        method, self._base + path, headers=headers, params=params, json=json
                    )
        except EgressError as exc:
            # Connection refused, timeout, denied host: a Langfuse failure with its own code,
            # counted per item like any other (r1 MINOR-8). The type only, no message.
            raise LangfuseApiError(
                "langfuse_unreachable", f"{method} {path}: {type(exc).__name__}"
            ) from None
        if response.status_code == 404:
            raise LangfuseApiError("langfuse_not_found", f"{method} {path}")
        if not 200 <= response.status_code < 300:
            # The body is not echoed: it may carry item text (secret-free error, 03b).
            raise LangfuseApiError(
                "langfuse_request_failed", f"{method} {path} -> {response.status_code}"
            )
        return response.json() if response.content else None

    # --- datasets and items -----------------------------------------------------------------

    async def upsert_dataset(self, name: str, *, description: str, metadata: dict) -> dict:
        return await self._call(
            "POST",
            "/api/public/v2/datasets",
            json={"name": name, "description": description, "metadata": metadata},
        )

    async def upsert_item(
        self,
        dataset: str,
        item_id: str,
        *,
        input: dict,
        expected_output: dict,
        metadata: dict,
        status: str = "ACTIVE",
    ) -> dict:
        return await self._call(
            "POST",
            "/api/public/dataset-items",
            json={
                "datasetName": dataset,
                "id": item_id,
                "input": input,
                "expectedOutput": expected_output,
                "metadata": metadata,
                "status": status,
            },
        )

    async def items(self, dataset: str) -> list[dict]:
        out: list[dict] = []
        page = 1
        while True:
            body = await self._call(
                "GET",
                "/api/public/dataset-items",
                params={"datasetName": dataset, "page": str(page), "limit": str(PAGE)},
            )
            rows = body.get("data", [])
            foreign = [r.get("id") for r in rows if r.get("datasetName") not in (None, dataset)]
            if foreign:
                raise LangfuseApiError(
                    "langfuse_filter_ignored", f"items of another dataset: {foreign[:3]}"
                )
            out.extend(rows)
            if page >= int(body.get("meta", {}).get("totalPages", 1) or 1):
                return out
            page += 1

    # --- dataset runs -----------------------------------------------------------------------

    async def link_run_item(
        self, run_name: str, item_id: str, trace_id: str, *, description: str, metadata: dict
    ) -> dict:
        return await self._call(
            "POST",
            "/api/public/dataset-run-items",
            json={
                "runName": run_name,
                "runDescription": description,
                "datasetItemId": item_id,
                "traceId": trace_id,
                "metadata": metadata,
            },
        )

    async def run_items(self, dataset: str, run_name: str) -> list[RunItem]:
        body = await self._call(
            "GET", f"/api/public/datasets/{_seg(dataset)}/runs/{_seg(run_name)}"
        )
        return [
            RunItem(r["datasetItemId"], r["traceId"])
            for r in body.get("datasetRunItems", [])
            if r.get("traceId")
        ]

    async def delete_run(self, dataset: str, run_name: str) -> None:
        await self._call("DELETE", f"/api/public/datasets/{_seg(dataset)}/runs/{_seg(run_name)}")

    # --- scores -----------------------------------------------------------------------------

    async def upsert_score(
        self,
        score_id: str,
        *,
        name: str,
        value: float | str,
        data_type: str,
        trace_id: str | None = None,
        dataset_run_id: str | None = None,
        comment: str = "",
        metadata: dict | None = None,
    ) -> dict:
        if (trace_id is None) == (dataset_run_id is None):
            raise ValueError("a score belongs to exactly one trace or one dataset run")
        body: dict[str, Any] = {
            "id": score_id,
            "name": name,
            "value": value,
            "dataType": data_type,
            "comment": comment,
            "metadata": metadata or {},
        }
        body["traceId" if trace_id else "datasetRunId"] = trace_id or dataset_run_id
        return await self._call("POST", "/api/public/scores", json=body)

    async def scores_by_ids(self, ids: list[str]) -> list[dict]:
        """Scores by their ids (v2 `scoreIds`, the one score filter this server honors; L12).
        Our ids are deterministic (`score_id`), so a reader asks for exactly what it wrote.
        A returned row that was not asked for is a loud error (a filter ignored silently)."""
        wanted = set(ids)
        out: list[dict] = []
        for start in range(0, len(ids), SCORE_IDS_PER_CALL):
            chunk = ids[start : start + SCORE_IDS_PER_CALL]
            body = await self._call(
                "GET",
                "/api/public/v2/scores",
                params={"scoreIds": ",".join(chunk), "limit": str(PAGE)},
            )
            rows = body.get("data", [])
            foreign = [r.get("id") for r in rows if r.get("id") not in wanted]
            if foreign:
                raise LangfuseApiError(
                    "langfuse_filter_ignored", f"scores not asked for: {len(foreign)}"
                )
            out.extend(rows)
        return out

    async def trace_scores(self, trace_id: str, names: list[str]) -> list[dict]:
        """The named scores of one trace, read by id; rows of another trace are a loud error."""
        rows = await self.scores_by_ids([score_id(trace_id, n) for n in names])
        foreign = [r.get("id") for r in rows if r.get("traceId") != trace_id]
        if foreign:
            raise LangfuseApiError(
                "langfuse_filter_ignored", f"scores of other traces for {trace_id}: {len(foreign)}"
            )
        return rows


def _seg(value: str) -> str:
    """One URL path segment: `/` and `..` cannot leave it (r1 MINOR-11)."""
    return quote(value, safe="")


def score_id(trace_id: str, scorer: str) -> str:
    """Deterministic: re-scoring an item replaces its score (L10)."""
    return f"{trace_id}-{scorer}"
