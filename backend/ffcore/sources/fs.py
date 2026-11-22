"""Network-folder driver (both profiles): a directory mounted under FS_SOURCES_BASE (C5).

The external id is the file's path relative to the source root (POSIX). A delta run lists files
whose mtime is at or after the cursor; the engine also compares the content hash, so a touched
file with the same bytes is `unchanged`. Deletions are found only by a full listing (this
listing has no tombstones, R10.3). A symlink anywhere below the base is refused for that entry
(`path_outside_base` when it points out of the base, `symlink_refused` otherwise) and the
others go on. Permissions are folder based: the folder chain is the item's groups
(`acl.folder_groups`, most specific mapping wins).
"""

import asyncio
import fnmatch
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ffcore.core.config import Settings
from ffcore.sources import acl, paths
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

READ_CHUNK = 1024 * 1024


class FsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str = Field(description="Directory relative to FS_SOURCES_BASE.")
    include_globs: list[str] = Field(default_factory=lambda: ["*"])
    exclude_globs: list[str] = Field(default_factory=list)

    @field_validator("root")
    @classmethod
    def _root(cls, value: str) -> str:
        try:
            return paths.check_root(value)
        except SourceError as exc:
            raise ValueError(f"{exc.code}: {exc.detail}") from None

    @field_validator("include_globs", "exclude_globs")
    @classmethod
    def _globs(cls, value: list[str]) -> list[str]:
        cleaned = [g.strip() for g in value if g and g.strip()]
        if any("\\" in g for g in cleaned):
            raise ValueError("glob_invalid: use POSIX '/' separators")
        return cleaned


class FsDriver:
    kind = "fs"
    tombstones = False
    internet_deployments = ()
    deployments = None
    config_model = FsConfig
    secret_model = None

    def __init__(self, spec: SourceSpec, secret: dict | None, http, settings: Settings) -> None:
        self._config = FsConfig.model_validate(spec.config)
        self._base = settings.fs_sources_base

    def _root(self) -> Path:
        return paths.resolve_root(self._base, self._config.root)

    def _selected(self, rel: str) -> bool:
        if not any(fnmatch.fnmatchcase(rel, g) for g in self._config.include_globs):
            return False
        return not any(fnmatch.fnmatchcase(rel, g) for g in self._config.exclude_globs)

    def _walk(self) -> list[tuple[str, Path | None, str | None]]:
        """(relpath, path, refused code) for every selected entry, sorted (stable runs)."""
        root = self._root()
        base = Path(os.path.realpath(self._base))
        found: list[tuple[str, Path | None, str | None]] = []
        for current, dirs, files in os.walk(root, followlinks=False):
            here = Path(current)
            for name in sorted(dirs):
                entry = here / name
                if entry.is_symlink():
                    rel = entry.relative_to(root).as_posix()
                    found.append((rel, None, _symlink_code(base, entry)))
            dirs[:] = sorted(d for d in dirs if not (here / d).is_symlink())
            for name in sorted(files):
                entry = here / name
                rel = entry.relative_to(root).as_posix()
                if not self._selected(rel):
                    continue
                if entry.is_symlink():
                    found.append((rel, None, _symlink_code(base, entry)))
                elif not paths.inside(base, entry):
                    found.append((rel, None, "path_outside_base"))
                elif entry.is_file():
                    found.append((rel, entry, None))
        found.sort(key=lambda row: row[0])
        return found

    async def test_connection(self) -> ConnectionTest:
        try:
            count = await self.count()
        except SourceError as exc:
            return ConnectionTest(reachable=False, error_code=exc.code, detail=exc.detail)
        return ConnectionTest(reachable=True, count=count)

    async def count(self) -> int | None:
        entries = await asyncio.to_thread(self._walk)
        return sum(1 for _, path, refused in entries if refused is None and path is not None)

    async def list_changes(self, since: datetime | None) -> AsyncIterator[ItemRef]:
        for rel, path, refused in await asyncio.to_thread(self._walk):
            if refused is not None or path is None:
                yield ItemRef(external_id=rel, title=Path(rel).name, refused=refused)
                continue
            stat = path.stat()
            updated = datetime.fromtimestamp(stat.st_mtime, UTC)
            if since is not None and updated < since:
                continue
            yield ItemRef(
                external_id=rel,
                title=Path(rel).name,
                updated_at=updated,
                size=stat.st_size,
                breadcrumb_parts=tuple(Path(rel).parts),
            )

    def _file(self, item: ItemRef) -> Path:
        root = self._root()
        path = root / item.external_id
        base = Path(os.path.realpath(self._base))
        if not paths.inside(base, path) or path.is_symlink():
            raise paths.outside(f"{item.external_id} resolves outside FS_SOURCES_BASE")
        if not path.is_file():
            raise SourceError("item_gone", f"{item.external_id} is no longer a file")
        return path

    async def fetch_raw(self, item: ItemRef) -> RawPayload:
        path = self._file(item)
        content = await asyncio.to_thread(path.read_bytes)
        return RawPayload(content=content, ext=path.suffix.lower().lstrip(".") or "bin")

    async def list_attachments(
        self, item: ItemRef, raw: RawPayload
    ) -> AsyncIterator[AttachmentRef]:
        return
        yield  # a file has no attachments

    @asynccontextmanager
    async def fetch_attachment(self, item: ItemRef, attachment: AttachmentRef):
        raise SourceError("attachment_unsupported", "network-folder items have no attachments")
        yield  # pragma: no cover

    async def acl(self, item: ItemRef, raw: RawPayload) -> SourceAcl:
        return SourceAcl(groups=acl.folder_groups(item.external_id))

    def render(self, item: ItemRef, raw: RawPayload) -> Rendered:
        return Rendered(
            content=raw.content,
            filename=Path(item.external_id).name,
            breadcrumb=tuple(Path(item.external_id).parts),
        )

    async def aclose(self) -> None:
        return None


def _symlink_code(base: Path, entry: Path) -> str:
    target = os.path.realpath(entry)
    return "symlink_refused" if target.startswith(str(base) + os.sep) else "path_outside_base"
