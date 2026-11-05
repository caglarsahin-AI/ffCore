"""08 tam 1b, dilim 0 (K-08T1B-0002 A): the NER model comes in through `make models` only.

`make models` downloads the model card, config, tokenizer and safetensors weights (no pickle,
TF/Flax/ONNX copies) at the measured commit (08 tam 1c-b), `make models-check` lists them
offline, and the ingest worker's startup check stays as it was: it is not a weight the worker
needs.
"""

import socket
import sys
import types

import pytest

from ffcore.knowledge import models

CANDIDATES = ("akdeniz27/bert-base-turkish-cased-ner",)


@pytest.fixture
def empty_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path / "models"))

    def no_network(*args, **kwargs):
        raise AssertionError(f"network request during a model check: {args}")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    return tmp_path


def test_08t_18_ner_candidates_checked(empty_cache, capsys):
    assert models.NER_CANDIDATES == CANDIDATES
    gaps = {gap.name for gap in models.ner_missing()}
    assert gaps == set(CANDIDATES)
    assert models.main(["check"]) == 1
    out = capsys.readouterr().out
    for repo in CANDIDATES:
        assert f"missing  {repo}" in out


def test_08t_18b_worker_startup_check_ignores_candidates(empty_cache):
    names = {gap.name for gap in models.missing("BAAI/bge-m3", "BAAI/bge-reranker-v2-m3")}
    assert names.isdisjoint(CANDIDATES)


def test_08t_18c_download_takes_only_the_allowed_files(empty_cache, monkeypatch):
    calls = []

    def snapshot_download(repo, revision=None, cache_dir=None, **kwargs):
        calls.append((repo, revision, kwargs))
        return str(empty_cache / repo)

    hub = types.ModuleType("huggingface_hub")
    hub.snapshot_download = snapshot_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    paddle = types.ModuleType("paddleocr")
    paddle.PaddleOCR = lambda **kwargs: None
    monkeypatch.setitem(sys.modules, "paddleocr", paddle)

    models.download("BAAI/bge-m3", "BAAI/bge-reranker-v2-m3")

    by_repo = {repo: (revision, kwargs) for repo, revision, kwargs in calls}
    for repo in CANDIDATES:
        revision, kwargs = by_repo[repo]
        assert revision == models.NER_REVISIONS[repo] != "main"
        allowed = kwargs["allow_patterns"]
        for name in ("config.json", "README.md", "tokenizer.json", "model.safetensors"):
            assert any(_match(name, p) for p in allowed), name
        for name in (
            "pytorch_model.bin",
            "tf_model.h5",
            "flax_model.msgpack",
            "onnx/model.onnx",
            "rust_model.ot",
        ):
            assert not any(_match(name, p) for p in allowed), name
    # The 04a weights are downloaded as before (whole snapshot).
    assert "allow_patterns" not in by_repo["BAAI/bge-m3"][1]


def _match(name: str, pattern: str) -> bool:
    from fnmatch import fnmatch

    return fnmatch(name, pattern)
