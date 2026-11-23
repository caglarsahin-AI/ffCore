"""Jira driver as a data source (16-2): issues become documents (past decisions and solutions).

Server/Data Center `GET /rest/api/2/search` (`startAt`, `total`); Cloud `GET
/rest/api/2/search/jql` (`nextPageToken`; the old search is gone there). Set up with an
address, a credential and an optional JQL (K-16-0003): empty means every issue the service
account sees. The query is always `(<jql>) [AND updated >= "-Nm"] ORDER BY updated ASC`; a JQL
with its own ORDER BY is refused at registration (`jql_order_by`), the order is the driver's.

- **count:** DC: the same JQL with `maxResults=0` → `total`. Cloud only offers an approximate
  count, so the driver counts by a key-only listing (`count_method = "listing"`, K-16-0009 S2:
  two light scans per full run instead of a full run that could never delete).
- **render:** `# KEY: summary`, a metadata block (project, type, status, priority, resolution,
  labels, created, updated), `## Description`, `## Resolution`, each comment `## Comment <n>
  (<date>)` so chunks break at comment boundaries. **No person names** (assignee, reporter,
  comment authors, `[~user]` mentions: K-16-0009 S1, the personal-data boundary). A comment
  the source restricts (`visibility`: a role or a group) or a service desk internal note
  (`jsdPublic: false`) is not in the document (R-16-0013 MAJOR-1): the issue's permission is
  wider than the comment's. Raw keeps the API answer as is. Jira wiki `{code}`/`{noformat}`
  blocks become fenced blocks and `h1.`-`h6.` headings Markdown headings; log, stack trace and
  JSON dumps are left to Kapı 2 (`data_dump`).
- **permissions:** `project:<KEY>`; an issue with a security level is
  `security:<KEY>/<level>` only (the level narrows who sees it; beside `project:` the project
  row would open it; named per project because level names repeat across schemes, NOTE-3).
- **attachments:** `fields.attachment[]` (name, size, created, MIME, content URL on the Jira
  origin only).
- A delta never deletes (no tombstones): deleted or archived issues leave in a full run (D4).
"""

import json
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from pydantic import ConfigDict, Field, field_validator

from ffcore.core.config import Settings
from ffcore.sources.atlassian import (
    AtlassianHttp,
    AtlassianSecret,
    BaseUrl,
    PageGuard,
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
from ffcore.sources.confluence import window_minutes

PAGE_SIZE = 100
FIELDS = (
    "summary,description,comment,resolution,status,labels,issuetype,priority,project,"
    "updated,created,attachment,security"
)
_ORDER_BY = re.compile(r"\border\s+by\b", re.I)
_CODE = re.compile(r"\{(code|noformat)(?::([^}]*))?\}(.*?)\{\1\}", re.S)
_HEADING = re.compile(r"^h([1-6])\.\s+", re.M)
_MENTION = re.compile(r" ?\[~[^\]\n]*\]")


class JiraConfig(BaseUrl):
    model_config = ConfigDict(extra="forbid")

    jql: str | None = Field(
        default=None, max_length=2000, description="Empty: every visible issue."
    )
    attachments_enabled: bool = True

    @field_validator("jql")
    @classmethod
    def _jql(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        if _ORDER_BY.search(value):
            raise ValueError("jql_order_by: leave ORDER BY out; the sync orders by updated")
        return value.strip()


class JiraDriver:
    kind = "jira"
    tombstones = False
    deployments = ("server", "cloud")
    internet_deployments = ("cloud",)
    config_model = JiraConfig
    secret_model = AtlassianSecret

    @staticmethod
    def check(deployment: str | None, config: dict, secret: dict | None) -> None:
        check_secret(deployment, secret)

    def __init__(self, spec: SourceSpec, secret: dict | None, http, settings: Settings) -> None:
        self._config = JiraConfig.model_validate(spec.config)
        check_secret(spec.deployment, secret)
        self._cloud = spec.deployment == "cloud"
        self.count_method = "listing" if self._cloud else "server"
        self._http = AtlassianHttp(
            self._config.base_url, auth_header(spec.deployment, secret), settings, client=http
        )
        self._issues: dict[str, dict] = {}

    def _jql(self, since: datetime | None = None) -> str:
        parts = []
        if self._config.jql:
            parts.append(f"({self._config.jql})")
        if since is not None:
            parts.append(f'updated >= "-{window_minutes(since)}m"')
        where = " AND ".join(parts)
        return f"{where} ORDER BY updated ASC" if where else "ORDER BY updated ASC"

    async def test_connection(self) -> ConnectionTest:
        try:
            count = await self.count()
        except SourceError as exc:
            return ConnectionTest(reachable=False, error_code=exc.code, detail=exc.detail)
        return ConnectionTest(reachable=True, count=count)

    async def count(self) -> int | None:
        if not self._cloud:
            body = await self._http.get_json(
                "/rest/api/2/search", {"jql": self._jql(), "maxResults": "0", "fields": "key"}
            )
            total = body.get("total")
            return total if isinstance(total, int) else None
        keys = set()
        async for issue in self._search(self._jql(), fields="key"):
            keys.add(issue["key"])
        return len(keys)

    async def _search(self, jql: str, *, fields: str) -> AsyncIterator[dict]:
        if self._cloud:
            token = None
            guard = PageGuard()
            while True:
                params = {"jql": jql, "maxResults": str(PAGE_SIZE), "fields": fields}
                if token:
                    params["nextPageToken"] = token
                body = await self._http.get_json("/rest/api/2/search/jql", params)
                for issue in body.get("issues", []):
                    yield issue
                token = body.get("nextPageToken")
                if not token:
                    return
                guard.next(token)
        start = 0
        while True:
            params = {
                "jql": jql,
                "startAt": str(start),
                "maxResults": str(PAGE_SIZE),
                "fields": fields,
            }
            body = await self._http.get_json("/rest/api/2/search", params)
            issues = body.get("issues", [])
            for issue in issues:
                yield issue
            start += len(issues)
            if not issues or start >= int(body.get("total", 0)):
                return

    async def list_changes(self, since: datetime | None) -> AsyncIterator[ItemRef]:
        async for issue in self._search(self._jql(since), fields=FIELDS):
            self._issues[issue["key"]] = issue
            fields = issue.get("fields") or {}
            project = (fields.get("project") or {}).get("key") or issue["key"].split("-")[0]
            yield ItemRef(
                external_id=issue["key"],
                title=f"{issue['key']}: {fields.get('summary') or ''}".strip(),
                url=f"{self._config.base_url}/browse/{issue['key']}",
                updated_at=_when(fields.get("updated")),
                space=project,
                breadcrumb_parts=(project, issue["key"]),
            )

    async def fetch_raw(self, item: ItemRef) -> RawPayload:
        issue = self._issues.pop(item.external_id, None)
        if issue is None:
            raise SourceError("item_not_listed", f"issue {item.external_id} was not in the listing")
        return RawPayload(
            content=json.dumps(issue, ensure_ascii=False, sort_keys=True).encode(), ext="json"
        )

    async def list_attachments(
        self, item: ItemRef, raw: RawPayload
    ) -> AsyncIterator[AttachmentRef]:
        if not self._config.attachments_enabled:
            return
        fields = json.loads(raw.content).get("fields") or {}
        for att in fields.get("attachment") or []:
            yield AttachmentRef(
                name=att.get("filename", ""),
                size=att.get("size"),
                modified_at=_when(att.get("created")),
                mime=att.get("mimeType"),
                ref=att.get("content", ""),
            )

    @asynccontextmanager
    async def fetch_attachment(self, item: ItemRef, attachment: AttachmentRef):
        if not attachment.ref:
            raise SourceError("attachment_gone", "the issue gave no download link")
        # Cloud answers an attachment URL with a redirect to its media host; `redirect=false`
        # asks for the bytes (R-16-0013 MINOR-2). Server/Data Center ignores the parameter.
        joiner = "&" if "?" in attachment.ref else "?"
        async with self._http.stream(f"{attachment.ref}{joiner}redirect=false") as chunks:
            yield chunks

    async def acl(self, item: ItemRef, raw: RawPayload) -> SourceAcl:
        fields = json.loads(raw.content).get("fields") or {}
        level = (fields.get("security") or {}).get("name")
        if level:
            return SourceAcl(groups=(f"security:{item.space}/{level}",))
        return SourceAcl(groups=(f"project:{item.space}",))

    def render(self, item: ItemRef, raw: RawPayload) -> Rendered:
        issue = json.loads(raw.content)
        key, fields = issue["key"], issue.get("fields") or {}
        lines = [f"# {key}: {fields.get('summary') or ''}".rstrip(), ""]
        meta = [
            ("Project", (fields.get("project") or {}).get("key")),
            ("Type", (fields.get("issuetype") or {}).get("name")),
            ("Status", (fields.get("status") or {}).get("name")),
            ("Priority", (fields.get("priority") or {}).get("name")),
            ("Resolution", (fields.get("resolution") or {}).get("name")),
            ("Labels", ", ".join(fields.get("labels") or []) or None),
            ("Created", _date(fields.get("created"))),
            ("Updated", _date(fields.get("updated"))),
        ]
        lines += [f"- {name}: {value}" for name, value in meta if value]
        if fields.get("description"):
            lines += ["", "## Description", "", wiki_to_markdown(fields["description"])]
        resolution = (fields.get("resolution") or {}).get("description")
        if resolution:
            lines += ["", "## Resolution", "", wiki_to_markdown(resolution)]
        comments = [
            c
            for c in (fields.get("comment") or {}).get("comments") or []
            if not c.get("visibility")
            and c.get("jsdPublic") is not False
            and (c.get("body") or "").strip()
        ]
        for n, comment in enumerate(comments, 1):
            body = comment["body"]
            when = _date(comment.get("created"))
            heading = f"## Comment {n}" + (f" ({when})" if when else "")
            lines += ["", heading, "", wiki_to_markdown(body)]
        text = "\n".join(lines).rstrip() + "\n"
        return Rendered(
            content=text.encode("utf-8"), filename=f"{key}.md", breadcrumb=(item.space, key)
        )

    async def aclose(self) -> None:
        await self._http.aclose()


def wiki_to_markdown(text: str) -> str:
    """The Jira wiki markup that changes meaning in Markdown: code blocks and headings."""

    def fence(match: re.Match) -> str:
        language = (match.group(2) or "").split("|")[0].strip() if match.group(1) == "code" else ""
        return f"\n```{language}\n{match.group(3).strip(chr(10))}\n```\n"

    text = _MENTION.sub("", text.replace("\r\n", "\n"))
    text = _CODE.sub(fence, text)
    return _HEADING.sub(lambda m: "#" * (int(m.group(1)) + 2) + " ", text).strip()


def _when(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    # Jira: 2026-03-01T10:15:30.000+0300 → +03:00
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _date(value: str | None) -> str | None:
    parsed = _when(value)
    return parsed.date().isoformat() if parsed else None
