"""Review 04a r1 MAJOR-6 (K-04a-0016, K-04a-0020): with an empty model cache every runtime loader
fails with ModelMissing naming the model and the path, before any network request; PaddleOCR is
never constructed without its directories; images and Compose are offline by default.
The same check runs in a `--network none` container with an empty cache (PR evidence)."""

import asyncio
import socket
import sys
import threading
import types
from pathlib import Path

import pytest
import yaml

from ffcore.knowledge.models import ModelMissing

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def empty_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path / "models"))

    def no_network(*args, **kwargs):
        raise AssertionError(f"network request during a model load: {args}")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)  # no DNS lookup either
    return tmp_path


def raises_missing(fn, name):
    with pytest.raises(ModelMissing) as raised:
        fn()
    assert raised.value.name == name and raised.value.code == "model_missing"
    assert str(raised.value.path) in str(raised.value) and "make models" in str(raised.value)
    return raised.value


def test_04a_r1_6_embedding_model_and_tokenizer_need_the_cache(empty_cache):
    from ffcore.knowledge import embed

    raises_missing(lambda: embed.BgeM3Embedder("BAAI/bge-m3", 1024).load(), "BAAI/bge-m3")
    raises_missing(lambda: embed._tokenizer("BAAI/bge-m3"), "BAAI/bge-m3")


def test_04a_r1_6_reranker_needs_the_cache(empty_cache):
    from ffcore.knowledge import rerank

    model = "BAAI/bge-reranker-v2-m3"
    raises_missing(lambda: rerank.BgeReranker(model).load(), model)


def test_04a_r1_6_docling_reports_missing_weights(empty_cache):
    from ffcore.knowledge.convert import office

    out = {}
    # A fresh thread: the converter is cached per thread.
    worker = threading.Thread(
        target=lambda: out.update(r=office.convert_with_docling(Path("x.docx")))
    )
    worker.start()
    worker.join()
    assert out["r"].error_code == "model_missing", out["r"]
    assert "docling-project/docling-models" in out["r"].warnings[0]


def test_04a_r1_6_paddleocr_is_never_constructed_without_its_dirs(empty_cache, monkeypatch):
    import fitz

    from ffcore.knowledge.convert import ocr

    trap = types.ModuleType("paddleocr")

    def constructed(*args, **kwargs):
        raise AssertionError("PaddleOCR constructed without model directories (it would download)")

    trap.PaddleOCR = constructed
    monkeypatch.setitem(sys.modules, "paddleocr", trap)
    monkeypatch.setattr(ocr._local, "paddle", None, raising=False)
    path = empty_cache / "scan.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.save(path)
    result = ocr.ocr_pdf(path)
    assert result.error_code == "model_missing", result
    assert str(empty_cache / "models" / "paddleocr" / "det") in result.warnings[0]


def test_04a_r1_6_readyz_reports_the_missing_model(empty_cache, monkeypatch):
    from ffcore.core import readiness

    def load(settings):
        raise ModelMissing("BAAI/bge-m3", empty_cache / "hf" / "hub")

    monkeypatch.setattr(readiness, "_load_models", load)
    readiness.reset()
    asyncio.run(readiness.warmup(object()))
    try:
        assert readiness._state["code"] == "model_missing"
        assert "BAAI/bge-m3" in readiness._state["error"]
    finally:
        readiness.reset()


def test_04a_r1_6_offline_is_the_default_everywhere():
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert "HF_HUB_OFFLINE=1" in dockerfile and "TRANSFORMERS_OFFLINE=1" in dockerfile
    compose = yaml.safe_load((ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8"))
    for service in ("backend", "worker", "tools"):
        env = compose["services"][service]["environment"]
        assert env["HF_HUB_OFFLINE"] == "${HF_HUB_OFFLINE:-1}", service
        assert env["TRANSFORMERS_OFFLINE"] == "${TRANSFORMERS_OFFLINE:-1}", service
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    # Downloading is the separate `make models` step, nowhere else.
    assert makefile.count("HF_HUB_OFFLINE=0") == 1
    assert "models:\n\tcd backend && HF_HUB_OFFLINE=0" in makefile
