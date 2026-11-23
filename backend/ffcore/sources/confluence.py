"""Confluence driver (16-2): Server/Data Center (REST v1) and Cloud (v1 CQL search, v2 bodies).

Set up with an address, a credential and an optional scope (K-16-0003): `space_keys` empty means
every space the service account sees. The external id is the page id, the space its key.

- **count:** `GET /rest/api/search?cql=<scope>&limit=1` → `totalSize` (the source's own count,
  taken before and after the listing; the safe delete rule compares them, D4).
- **listing:** DC `GET /rest/api/content/search` with the body expanded (one request per 50
  pages, no second fetch per page); Cloud `GET /rest/api/search` (ids, versions, ancestors)
  then `GET /api/v2/pages/{id}?body-format=storage` per changed page (K-16-0009 S3). Pages
  follow `_links.next` until it is gone. A delta asks only for pages modified in a relative
  window, `lastmodified >= now("-Nm")` with N = minutes since the cursor + 10 (no time zone
  in the query; the 10 minutes cover clock skew between FFCore and Confluence).
- **attachments:** DC `child/attachment` (newest version per title), Cloud v2 `attachments`;
  metadata only, Kapı 0 decides before any download (engine).
- **permissions:** `restriction/byOperation/read` of the page and of each ancestor (a read
  restriction is inherited by every child page). No restriction anywhere: `space:<KEY>` (space
  permissions are mapped on the screen, K-16-0009 S5). Restricted: only the restriction's
  groups (`group:<name>`) and users (`user:<name>`), never `space:<KEY>` beside them (mappings
  are a union: the space row would open a restricted page). Restricted on several levels: who
  is named on every level (intersection); nobody → no group → admins only (engine).
- **render:** storage format → Markdown (`storage_format`), breadcrumb `space › ancestors ›
  page` (D5). No network.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from math import ceil

from pydantic import ConfigDict, Field, field_validator

from ffcore.core.config import Settings
from ffcore.sources import storage_format
from ffcore.sources.atlassian import (
    AtlassianHttp,
    AtlassianSecret,
    BaseUrl,
    auth_header,
    check_secret,
)
from ffcore.sources.base import (
    AttachmentRef,
    ConnectionTest,
    ItemRef,
    RawPayload,
    Rendered,
    SourceAcl,
    SourceError,
    SourceSpec,
)

PAGE_LIMIT = 50
ATTACHMENT_LIMIT = 200
OVERLAP_MIN = 10
EXPAND = "body.storage,version,ancestors,space,metadata.labels"
SEARCH_EXPAND = "content.version,content.ancestors,content.space"


class ConfluenceConfig(BaseUrl):
    model_config = ConfigDict(extra="forbid")

    space_keys: list[str] = Field(default_factory=list, description="Empty: every visible space.")
    attachments_enabled: bool = True

    @field_validator("space_keys")
    @classmethod
    def _keys(cls, value: list[str]) -> list[str]:
        keys = [k.strip() for k in value if k and k.strip()]
        for key in keys:
            if not key.replace("_", "").replace("~", "").isalnum():
                raise ValueError(f"space key {key!r} is not a Confluence space key")
        return sorted(dict.fromkeys(keys))


def window_minutes(since: datetime, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    return max(OVERLAP_MIN, ceil((now - since).total_seconds() / 60) + OVERLAP_MIN)


class ConfluenceDriver:
    kind = "confluence"
    tombstones = False
    deployments = ("server", "cloud")
    internet_deployments = ("cloud",)
    config_model = ConfluenceConfig
    secret_model = AtlassianSecret
    count_method = "server"

    @staticmethod
    def check(deployment: str | None, config: dict, secret: dict | None) -> None:
        check_secret(deployment, secret)

    def __init__(self, spec: SourceSpec, secret: dict | None, http, settings: Settings) -> None:
        self._config = ConfluenceConfig.model_validate(spec.config)
        check_secret(spec.deployment, secret)
        self._cloud = spec.deployment == "cloud"
        base = self._config.base_url + ("/wiki" if self._cloud else "")
        self._http = AtlassianHttp(
            base, auth_header(spec.deployment, secret), settings, client=http
        )
        self._pages: dict[str, dict] = {}
        self._restrictions: dict[str, tuple[frozenset, frozenset] | None] = {}

    # -- query ---------------------------------------------------------------------------

    def _cql(self, since: datetime | None = None) -> str:
        parts = ["type=page"]
        if self._config.space_keys:
            parts.append(f"space in ({','.join(self._config.space_keys)})")
        if since is not None:
            parts.append(f'lastmodified >= now("-{window_minutes(since)}m")')
        return " AND ".join(parts)

    async def test_connection(self) -> ConnectionTest:
        try:
            count = await self.count()
        except SourceError as exc:
            return ConnectionTest(reachable=False, error_code=exc.code, detail=exc.detail)
        return ConnectionTest(reachable=True, count=count)

    async def count(self) -> int | None:
        body = await self._http.get_json("/rest/api/search", {"cql": self._cql(), "limit": "1"})
        total = body.get("totalSize")
        return total if isinstance(total, int) else None

    async def _follow(self, link: str, params: dict | None) -> AsyncIterator[dict]:
        while link:
            body = await self._http.get_json(link, params)
            yield body
            link = (body.get("_links") or {}).get("next")
            params = None  # the next link carries its query

    async def list_changes(self, since: datetime | None) -> AsyncIterator[ItemRef]:
        if self._cloud:
            pages = self._follow(
                "/rest/api/search",
                {"cql": self._cql(since), "expand": SEARCH_EXPAND, "limit": str(PAGE_LIMIT)},
            )
            async for body in pages:
                for result in body.get("results", []):
                    content = result.get("content") or result
                    yield self._item(content)
            return
        pages = self._follow(
            "/rest/api/content/search",
            {"cql": self._cql(since), "expand": EXPAND, "limit": str(PAGE_LIMIT)},
        )
        async for body in pages:
            for page in body.get("results", []):
                self._pages[str(page["id"])] = page  # the body came with the listing
                yield self._item(page)

    def _item(self, page: dict) -> ItemRef:
        space = (page.get("space") or {}).get("key") or "default"
        ancestors = tuple(a.get("title", "") for a in page.get("ancestors") or [])
        when = (page.get("version") or {}).get("when")
        ancestor_ids = [str(a["id"]) for a in page.get("ancestors") or [] if a.get("id")]
        webui = (page.get("_links") or {}).get("webui")
        return ItemRef(
            external_id=str(page["id"]),
            title=page.get("title") or str(page["id"]),
            url=self._http.base + webui if webui else None,
            updated_at=datetime.fromisoformat(when.replace("Z", "+00:00")) if when else None,
            space=space,
            breadcrumb_parts=(space, *ancestors, page.get("title") or ""),
            extra={"ancestors": list(ancestors), "ancestor_ids": ancestor_ids},
        )

    async def fetch_raw(self, item: ItemRef) -> RawPayload:
        page = self._pages.pop(item.external_id, None)
        if page is None and self._cloud:
            body = await self._http.get_json(
                f"/api/v2/pages/{item.external_id}", {"body-format": "storage"}
            )
            # The v2 page has no space key or ancestor titles: they come from the search hit.
            page = {
                "v2": body,
                "space": {"key": item.space},
                "ancestors": [{"title": t} for t in item.extra.get("ancestors", [])],
            }
        elif page is None:
            # DC pages arrive with the listing; fetching one that was not listed is a bug.
            raise SourceError("item_not_listed", f"page {item.external_id} was not in the listing")
        return RawPayload(
            content=json.dumps(page, ensure_ascii=False, sort_keys=True).encode(), ext="json"
        )

    async def list_attachments(
        self, item: ItemRef, raw: RawPayload
    ) -> AsyncIterator[AttachmentRef]:
        if not self._config.attachments_enabled:
            return
        if self._cloud:
            link = f"/api/v2/pages/{item.external_id}/attachments"
            async for body in self._follow(link, {"limit": str(ATTACHMENT_LIMIT)}):
                for att in body.get("results", []):
                    yield AttachmentRef(
                        name=att.get("title", ""),
                        size=att.get("fileSize"),
                        modified_at=_when(
                            (att.get("version") or {}).get("when")
                            or (att.get("version") or {}).get("createdAt")
                        ),
                        mime=att.get("mediaType"),
                        ref=att.get("downloadLink", ""),
                    )
            return
        newest: dict[str, dict] = {}
        link = f"/rest/api/content/{item.external_id}/child/attachment"
        params = {"expand": "extensions,version", "limit": str(ATTACHMENT_LIMIT)}
        async for body in self._follow(link, params):
            for att in body.get("results", []):
                title = att.get("title", "")
                number = (att.get("version") or {}).get("number", 0)
                if title not in newest or number > (newest[title].get("version") or {}).get(
                    "number", 0
                ):
                    newest[title] = att
        for title, att in sorted(newest.items()):
            extensions = att.get("extensions") or {}
            yield AttachmentRef(
                name=title,
                size=extensions.get("fileSize"),
                modified_at=_when((att.get("version") or {}).get("when")),
                mime=extensions.get("mediaType"),
                ref=(att.get("_links") or {}).get("download", ""),
            )

    @asynccontextmanager
    async def fetch_attachment(self, item: ItemRef, attachment: AttachmentRef):
        if not attachment.ref:
            raise SourceError("attachment_gone", "the listing gave no download link")
        async with self._http.stream(attachment.ref) as chunks:
            yield chunks

    async def _restriction(self, page_id: str) -> tuple[frozenset, frozenset] | None:
        """(groups, users) a page's own read restriction names; None when it has none.
        Cached per run: an ancestor is asked once for all its children."""
        if page_id not in self._restrictions:
            body = await self._http.get_json(
                f"/rest/api/content/{page_id}/restriction/byOperation/read"
            )
            restrictions = body.get("restrictions") or {}
            groups = frozenset(
                f"group:{g['name']}"
                for g in (restrictions.get("group") or {}).get("results", [])
                if g.get("name")
            )
            users = frozenset(
                f"user:{u.get('username') or u.get('accountId')}"
                for u in (restrictions.get("user") or {}).get("results", [])
                if u.get("username") or u.get("accountId")
            )
            self._restrictions[page_id] = (groups, users) if groups or users else None
        return self._restrictions[page_id]

    async def acl(self, item: ItemRef, raw: RawPayload) -> SourceAcl:
        levels = []
        for page_id in (item.external_id, *item.extra.get("ancestor_ids", [])):
            restriction = await self._restriction(page_id)
            if restriction is not None:
                levels.append(restriction)
        if not levels:
            return SourceAcl(groups=(f"space:{item.space}",))
        groups = frozenset.intersection(*(g for g, _ in levels))
        users = frozenset.intersection(*(u for _, u in levels))
        return SourceAcl(groups=(*sorted(groups), *sorted(users)))

    def render(self, item: ItemRef, raw: RawPayload) -> Rendered:
        page = json.loads(raw.content)
        v2 = page.get("v2")
        source = v2 if v2 is not None else page
        storage = ((source.get("body") or {}).get("storage") or {}).get("value") or ""
        title = source.get("title") or item.title
        converted = storage_format.to_markdown(storage, title=title)
        space = (page.get("space") or {}).get("key") or item.space
        ancestors = tuple(a.get("title", "") for a in page.get("ancestors") or [])
        return Rendered(
            content=converted.markdown.encode("utf-8"),
            filename=f"{item.external_id}.md",
            breadcrumb=(space, *ancestors, title),
        )

    async def aclose(self) -> None:
        await self._http.aclose()


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
