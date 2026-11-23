"""The data source driver interface (16, C14 entry point group `ffcore.sources`).

A driver knows one kind of source system and nothing about knowledge bases: it counts, lists,
fetches the source's own bytes (the API answer as is, never Markdown) and reports who may read an
item. The sync engine (`engine.py`) owns raw/silver/gold, Kapı 0, the safe delete rule and ACL
mapping; conversion is 04's pipeline (`ingest_from_raw`, C6). `render` turns raw into the input
04's converter reads (a cleaned XHTML page, an issue as Markdown sections, or the file itself),
deterministically and from raw only, so a silver run never asks the source.

Every refusal is a `SourceError` with a code (fail-loud, ARCH-06); the engine records it per
item and goes on with the others.
"""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, Protocol, runtime_checkable


class SourceError(Exception):
    """A coded refusal or failure of a source (code, detail; never credentials or content)."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class SourceSpec:
    """What a driver is given about its source: no knowledge base, no database row."""

    id: str
    kind: str
    deployment: str | None
    config: dict[str, Any]


@dataclass(frozen=True)
class ItemRef:
    """One listed item. `deleted` only from a driver whose listing carries tombstones.
    `refused` is a code the driver met while listing (a symlink out of the root): the engine
    records it on the item and fetches nothing; such an item is not counted as seen."""

    external_id: str
    title: str
    url: str | None = None
    updated_at: datetime | None = None
    size: int | None = None
    deleted: bool = False
    refused: str | None = None
    breadcrumb_parts: tuple[str, ...] = ()
    space: str = "default"
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawPayload:
    """The source's own bytes for an item and the extension they are stored with."""

    content: bytes
    ext: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AttachmentRef:
    """An attachment as the listing describes it, before anything is downloaded (Kapı 0)."""

    name: str
    size: int | None
    modified_at: datetime | None
    mime: str | None = None
    ref: str = ""


@dataclass(frozen=True)
class SourceAcl:
    """Who may read an item in the source: group names and member e-mail addresses."""

    groups: tuple[str, ...] = ()
    user_emails: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rendered:
    """The converter's input: bytes, the file name 04's router dispatches on (its extension),
    and the breadcrumb parts the source gives (space › ancestors › page, folder › file; D5)."""

    content: bytes
    filename: str
    breadcrumb: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConnectionTest:
    reachable: bool
    count: int | None = None
    error_code: str | None = None
    detail: str | None = None


@runtime_checkable
class SourceDriver(Protocol):
    kind: ClassVar[str]
    # Only a listing that reports deletions may delete in a delta run (R10.3).
    tombstones: ClassVar[bool]
    # Deployments that reach the internet (Atlassian Cloud, Graph): with OFFLINE=true their
    # registration is 422 (the profile difference is the OFFLINE value). Server/Data Center
    # sit on internal hosts (ALLOWED_INTERNAL_HOSTS) and work in airgap. None = no deployment.
    internet_deployments: ClassVar[tuple[str | None, ...]]
    # The deployments this driver serves (None: the kind has no deployment choice).
    deployments: ClassVar[tuple[str, ...] | None]

    async def test_connection(self) -> ConnectionTest: ...

    async def count(self) -> int | None:
        """The source's own count of the items in scope; None when it cannot say (then the
        engine deletes nothing)."""
        ...

    def list_changes(self, since: datetime | None) -> AsyncIterator[ItemRef]:
        """Every item in scope (since=None) or those changed since the cursor."""
        ...

    async def fetch_raw(self, item: ItemRef) -> RawPayload: ...

    def list_attachments(self, item: ItemRef, raw: RawPayload) -> AsyncIterator[AttachmentRef]: ...

    def fetch_attachment(
        self, item: ItemRef, attachment: AttachmentRef
    ) -> AbstractAsyncContextManager[AsyncIterator[bytes]]: ...

    async def acl(self, item: ItemRef, raw: RawPayload) -> SourceAcl: ...

    def render(self, item: ItemRef, raw: RawPayload) -> Rendered: ...

    async def aclose(self) -> None: ...
