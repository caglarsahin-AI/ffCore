"""The raw-staging tree `ingest-raw` reads (19): a file plus `<file>.meta.json` beside it.

A consumer maps its own raw layer onto this shape (PayCore: `scripts/ffcore_stage_raw.py` in the
paycoreLLM repository, C14); FFCore never learns the consumer's layout. Meta fields: `source`
(`<kind>:<space>`), `source_item_id` (required), `title`, `breadcrumb`, `source_url`,
`updated_at_source`, `attachments` (file names in the same directory). Any other field is
ignored, never copied: a mapper that leaks an author field still does not reach the index.

Boundary (plan/19 Güvenlik şartları 1-2): every path must resolve inside `--raw-dir` with no
symlink on the way (`path_outside_base`); a file over Kapı 0's size limit is refused before it is
read (`too_large`); PRSIM is refused until 08 full brings name recognition (`prsim_requires_ner`,
KARARLAR karar 5). Nothing is written under the tree. Each refusal is a `Rejected` with a code
and the relative path, never the content.
"""

import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from ffcore.knowledge import scope

META_SUFFIX = ".meta.json"
REQUIRED = ("source", "source_item_id")
PASSED = ("title", "breadcrumb", "source_url", "updated_at_source")


class StagingError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass(frozen=True)
class StagedItem:
    path: Path
    relpath: str
    meta: dict
    attachments: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Rejected:
    relpath: str
    code: str


def _norm(source: str) -> str:
    return source.strip()


def _is_prsim(source: str) -> bool:
    return "prsim" in _norm(source).lower().split(":")


def check_sources(sources: Iterable[str]) -> list[str]:
    """The explicit source list, PRSIM refused (KARARLAR karar 5; plan/19 şart 1)."""
    chosen = [_norm(s) for s in sources if _norm(s)]
    if not chosen:
        raise StagingError("sources_required", "name the sources to ingest (--sources)")
    for source in chosen:
        if _is_prsim(source):
            raise StagingError(
                "prsim_requires_ner",
                f"{source} carries person data; it is ingested once 08 full recognizes names",
            )
    return chosen


def _inside(base: Path, path: Path) -> bool:
    """`path` resolves inside `base` and no component below `base` is a symlink."""
    try:
        rel = path.relative_to(base)
    except ValueError:
        return False
    probe = base
    for part in rel.parts:
        if part in ("..", ""):
            return False
        probe = probe / part
        if probe.is_symlink():
            return False
    return os.path.realpath(path).startswith(str(base) + os.sep)


def _meta(path: Path) -> dict | str:
    meta_path = Path(f"{path}{META_SUFFIX}")
    if not meta_path.is_file() or meta_path.is_symlink():
        return "meta_missing"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "meta_invalid"
    if not isinstance(meta, dict) or any(not str(meta.get(k) or "").strip() for k in REQUIRED):
        return "meta_invalid"
    return meta


def iter_staged(
    raw_dir: Path, sources: Iterable[str], *, limit: int | None = None
) -> Iterator[StagedItem | Rejected]:
    """Documents under `raw_dir` in path order, with every refusal on the way. `limit` counts
    accepted documents only (the first small slice, plan/19 madde 3)."""
    selected = set(check_sources(sources))
    base = Path(os.path.realpath(raw_dir))
    if not base.is_dir():
        raise StagingError("raw_dir_missing", f"{raw_dir} is not a directory")
    accepted = 0
    for directory, dirnames, filenames in os.walk(base, followlinks=False):
        here = Path(directory)
        dirnames.sort()
        for name in list(dirnames):
            if (here / name).is_symlink():
                dirnames.remove(name)
                yield Rejected(str((here / name).relative_to(base)), "path_outside_base")
        files = sorted(filenames)
        documents = [f for f in files if not f.endswith(META_SUFFIX)]
        metas = {f: _meta(here / f) for f in documents if not (here / f).is_symlink()}
        claimed = {
            a
            for m in metas.values()
            if isinstance(m, dict)
            for a in (m.get("attachments") or [])
            if isinstance(a, str)
        }
        for name in documents:
            path = here / name
            rel = str(path.relative_to(base))
            if path.is_symlink() or not _inside(base, path):
                yield Rejected(rel, "path_outside_base")
                continue
            meta = metas[name]
            if isinstance(meta, str):
                if meta == "meta_missing" and name in claimed:
                    continue  # an attachment of a sibling document, not a document itself
                yield Rejected(rel, meta)
                continue
            source = _norm(str(meta["source"]))
            if _is_prsim(source):
                yield Rejected(rel, "prsim_requires_ner")
                continue
            if source not in selected:
                yield Rejected(rel, "source_not_selected")
                continue
            attachments = meta.get("attachments") or []
            if not isinstance(attachments, list) or not all(
                isinstance(a, str)
                and a == Path(a).name
                and _inside(base, here / a)
                and (here / a).is_file()
                for a in attachments
            ):
                yield Rejected(rel, "path_outside_base")
                continue
            if any(
                p.stat().st_size > scope.max_bytes(p.name)
                for p in [path, *(here / a for a in attachments)]
            ):
                yield Rejected(rel, "too_large")
                continue
            if limit is not None and accepted >= limit:
                return
            accepted += 1
            yield StagedItem(
                path=path, relpath=Path(rel).as_posix(), meta=meta, attachments=list(attachments)
            )


def source_of(item: StagedItem) -> str:
    return _norm(str(item.meta["source"]))


def metadata_for(item: StagedItem, *, kb_id: str) -> dict:
    """C6 `metadata` for `ingest_from_raw`: the known fields only (unknown meta never passes)."""
    return {
        "kb_id": kb_id,
        # The record key inside the KB is the file name (04a register_upload): the path relative
        # to the tree keeps two `index.md` of different spaces apart.
        "filename": item.relpath,
        "source": _norm(str(item.meta["source"])),
        "source_item_id": str(item.meta["source_item_id"]),
        **{k: item.meta[k] for k in PASSED if item.meta.get(k) is not None},
        "attachments": list(item.attachments),
    }
