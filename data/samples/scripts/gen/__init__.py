"""Generators for data/samples (package 13a). Each module exposes generate(rng, out, seed)."""

from pathlib import Path


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 with LF line endings (repo is LF, see .gitattributes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
