"""Model weights: read only from the model cache at run time, downloaded only by `make models`.

Review r1 MAJOR-6 / K-04a-0016 / K-04a-0020: both profiles run offline by default. Runtime
loaders take a local path from here and never a hub name, so a missing file is a ModelMissing
error naming the model and the path it was looked for in, never a download; the images and
Compose also set HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1 for what Docling loads itself.
PaddleOCR gets explicit model directories under MODEL_CACHE_DIR (its default ~/.paddleocr
downloads on first use) and is not constructed when they are missing.

`python -m ffcore.knowledge.models check` lists every weight and where it is;
`python -m ffcore.knowledge.models download` is the one step that connects out (`make models`,
run by the user; airgap points HF_ENDPOINT at the internal mirror, PLAN 12).
"""

import os
import sys
from collections.abc import Callable
from pathlib import Path

# Docling's own weights (table structure, layout) at the revisions Docling 2.125.0 pins itself
# (table_structure_model.py, layout_model_specs.py). After a Docling upgrade `make models-check`
# fails loud until these follow.
DOCLING_REPOS = {
    "docling-project/docling-models": "v2.3.0",
    "docling-project/docling-layout-heron": "main",
}
# PaddleOCR `tr`: multilingual detection, Latin recognition, angle classifier.
PADDLE_PARTS = ("det", "rec", "cls")
# 08 tam 1b (K-08T1B-0002): the Turkish NER model, at the commit measured on data/samples/pii in
# 08 tam 1c-b (docs/guardrail.md; the other candidate, savasy/bert-base-turkish-ner-cased, had
# no licence on its card and left the list). Downloaded at that commit, not `main`, so the
# volume always holds the snapshot NER_REVISION names. Only the model card (licence, labels),
# config, tokenizer and safetensors weights: no pickle, TF/Flax/ONNX copies. The worker never
# needs it (the model lives in the API process only).
NER_REVISIONS = {
    "akdeniz27/bert-base-turkish-cased-ner": "99995f7d2be4b3a28c74f0d36ee97f8c04ee0571",
}
NER_CANDIDATES = tuple(NER_REVISIONS)
NER_ALLOW_PATTERNS = (
    "README.md",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.txt",
    "*.safetensors",
)


class ModelMissing(RuntimeError):
    code = "model_missing"

    def __init__(self, name: str, path: Path):
        super().__init__(f"{name} is not in {path}; run `make models` (offline by default)")
        self.name = name
        self.path = path


def hub_cache() -> Path:
    home = os.environ.get("HF_HOME") or str(Path.home() / ".cache" / "huggingface")
    return Path(home) / "hub"


def model_cache() -> Path:
    return Path(os.environ.get("MODEL_CACHE_DIR", "/models"))


def hf_path(repo: str, revision: str = "main") -> Path:
    """The local snapshot of `repo`; ModelMissing without any network request."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    cache = hub_cache()
    try:
        return Path(
            snapshot_download(repo, revision=revision, cache_dir=cache, local_files_only=True)
        )
    except LocalEntryNotFoundError:
        raise ModelMissing(repo, cache) from None


def paddle_dirs() -> dict[str, str]:
    base = model_cache() / "paddleocr"
    dirs = {part: base / part for part in PADDLE_PARTS}
    for part, path in dirs.items():
        if not (path / "inference.pdiparams").is_file():
            raise ModelMissing(f"PaddleOCR tr {part}", path)
    return {f"{part}_model_dir": str(path) for part, path in dirs.items()}


def required(embed_model: str, rerank_model: str) -> list[tuple[str, Callable]]:
    checks = [(repo, lambda r=repo: hf_path(r)) for repo in (embed_model, rerank_model)]
    checks += [(repo, lambda r=repo, v=rev: hf_path(r, v)) for repo, rev in DOCLING_REPOS.items()]
    checks.append(("PaddleOCR tr", paddle_dirs))
    return checks


def missing(embed_model: str, rerank_model: str) -> list[ModelMissing]:
    out = []
    for _, probe in required(embed_model, rerank_model):
        try:
            probe()
        except ModelMissing as exc:
            out.append(exc)
    return out


def ner_missing() -> list[ModelMissing]:
    """The NER model not in the cache (models-check only; not the worker's startup)."""
    out = []
    for repo, revision in NER_REVISIONS.items():
        try:
            hf_path(repo, revision)
        except ModelMissing as exc:
            out.append(exc)
    return out


def download(embed_model: str, rerank_model: str) -> None:
    """The preparation step (connects out). Not called by any runtime path."""
    from huggingface_hub import snapshot_download

    revisions = {embed_model: "main", rerank_model: "main", **DOCLING_REPOS}
    for repo, revision in revisions.items():
        print(f"download {repo}@{revision} -> {hub_cache()}", flush=True)
        snapshot_download(repo, revision=revision, cache_dir=hub_cache())
    for repo, revision in NER_REVISIONS.items():
        print(f"download {repo}@{revision} (NER) -> {hub_cache()}", flush=True)
        snapshot_download(
            repo, revision=revision, cache_dir=hub_cache(), allow_patterns=list(NER_ALLOW_PATTERNS)
        )
    from paddleocr import PaddleOCR

    base = model_cache() / "paddleocr"
    print(f"download PaddleOCR tr -> {base}", flush=True)
    # With explicit, still empty directories PaddleOCR downloads into them (maybe_download).
    PaddleOCR(
        lang="tr",
        use_angle_cls=True,
        show_log=False,
        **{f"{part}_model_dir": str(base / part) for part in PADDLE_PARTS},
    )


def main(argv: list[str]) -> int:
    from ffcore.core.config import Settings

    # Only the model names: the check needs no database or secrets (Settings' own defaults).
    fields = Settings.model_fields
    embed_model = os.environ.get("EMBED_MODEL") or fields["embed_model"].default
    rerank_model = os.environ.get("RERANK_MODEL") or fields["rerank_model"].default
    if argv[:1] == ["download"]:
        download(embed_model, rerank_model)
    gaps = missing(embed_model, rerank_model) + ner_missing()
    for gap in gaps:
        print(f"missing  {gap.name}  ({gap.path})")
    if not gaps:
        print("ok       all model weights are in the cache")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
