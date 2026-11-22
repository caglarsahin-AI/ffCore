"""Paths of network-folder sources (C5) and of the raw layer (C6 layout).

A network-folder source names a directory *relative to* the one fixed root `FS_SOURCES_BASE`:
an absolute path, `..` or a symlink on the way out is refused when the source is registered
(400 `path_outside_base`) and again at run time for every file (the item is skipped and listed
with that code). So `.env`, the application directory and the storage tree cannot be indexed by
pointing a source at them.

Raw layout (plan/16 D3, under KNOWLEDGE_STORAGE_DIR as 04's own trees):
`raw/{project}/{kb}/{kind}/{space}/{item}/` with `payload.<ext>` (the source's bytes as given),
`render.<ext>` (the converter's input, derived from payload) and `attachments/<safe name>`.
"""

import hashlib
import os
import re
from pathlib import Path, PurePosixPath

from ffcore.sources.base import SourceError

# A name kept for a directory or file under raw: safe characters only; long names keep their
# extension (PayCore D1 measurement: 150 characters, extension up to 16).
_UNSAFE = re.compile(r"[^\w.\- ]+", re.UNICODE)
SAFE_NAME_MAX = 150
SAFE_EXT_MAX = 16


def outside(detail: str) -> SourceError:
    return SourceError("path_outside_base", detail)


def check_root(root: str) -> str:
    """The registered `config.root`: relative, POSIX separators, no `..`, no empty part. `""`
    and `"."` mean the base itself. Returns the normalized relative path."""
    text = (root or "").strip()
    if "\\" in text or "\x00" in text:
        raise outside("root must be a relative POSIX path under FS_SOURCES_BASE")
    path = PurePosixPath(text or ".")
    if path.is_absolute() or text.startswith("~"):
        raise outside("root must be relative to FS_SOURCES_BASE, not an absolute path")
    if any(part == ".." for part in path.parts):
        raise outside("root must not leave FS_SOURCES_BASE ('..')")
    return "." if str(path) == "." else str(path)


def resolve_root(base: str, root: str) -> Path:
    """The real directory of a source: `base/root`, a directory, with no symlink from the base
    down to it, and inside the base after resolution."""
    base_path = Path(os.path.realpath(base))
    if not base_path.is_dir():
        raise SourceError("fs_base_missing", "FS_SOURCES_BASE is not a directory")
    relative = check_root(root)
    target = base_path if relative == "." else base_path / relative
    if not inside(base_path, target, allow_equal=True):
        raise outside("root resolves outside FS_SOURCES_BASE (symlink or '..')")
    if not target.is_dir():
        raise SourceError("fs_root_missing", f"root '{relative}' is not a directory")
    return target


def inside(base: Path, path: Path, *, allow_equal: bool = False) -> bool:
    """`path` lies in `base` (already real) and no component below `base` is a symlink."""
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
    real = os.path.realpath(path)
    if allow_equal and real == str(base):
        return True
    return real.startswith(str(base) + os.sep)


def safe_name(name: str) -> str:
    """A file name kept under raw: unsafe characters become `_`; a long name is cut in its stem,
    never in its extension. Empty or dot-only names are refused (they would collide)."""
    cleaned = _UNSAFE.sub("_", name).strip().strip(".")
    if not cleaned:
        raise SourceError("name_invalid", "an attachment has no usable file name")
    if len(cleaned) <= SAFE_NAME_MAX:
        return cleaned
    stem, dot, ext = cleaned.rpartition(".")
    if not dot or len(ext) > SAFE_EXT_MAX:
        return cleaned[:SAFE_NAME_MAX]
    return f"{stem[: SAFE_NAME_MAX - len(ext) - 1]}.{ext}"


def item_dir_name(external_id: str) -> str:
    """A directory per item that cannot escape its parent whatever the external id holds (a
    network-folder id is a relative path): a readable prefix and a short hash."""
    readable = _UNSAFE.sub("_", external_id.replace("/", "__"))[:80].strip("._") or "item"
    digest = hashlib.sha256(external_id.encode("utf-8")).hexdigest()[:12]
    return f"{readable}-{digest}"


def raw_item_dir(
    storage_dir: str, project_id: str, kb_id: str, kind: str, space: str, external_id: str
) -> Path:
    return (
        Path(storage_dir)
        / "raw"
        / str(project_id)
        / str(kb_id)
        / kind
        / (_UNSAFE.sub("_", space) or "default")
        / item_dir_name(external_id)
    )
