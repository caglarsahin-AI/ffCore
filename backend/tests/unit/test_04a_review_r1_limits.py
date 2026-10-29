"""Review 04a r1 MAJOR-5: small inputs that expand without bound are refused with a code before
a converter opens them, converter processes run under memory and CPU limits, and the next file
converts normally after each refusal. Synthetic inputs only; no large bomb is ever inflated."""

import base64
import struct
import time
import zipfile
import zlib
from pathlib import Path

import pytest
import yaml

from ffcore.knowledge.convert import pipeline
from ffcore.knowledge.convert.types import CONVERTED, ERROR, ConversionResult
from ffcore.knowledge.convert.workers import Limits, PersistentPool

ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DOCX = ROOT / "data" / "samples" / "contracts" / "SZL-2025-003_temizlik-hizmet.docx"
TARGET = "tests.unit.test_04a_review_r1_limits:worker_target"


def convert(path: Path) -> ConversionResult:
    return pipeline.convert_one(path, time.time() + 60)


def vsdx_bomb(path: Path) -> Path:
    # The reviewer's shape: a few KB that expand to 8 MB of page XML.
    page = "<PageContents>" + "<Shape><Text>x</Text></Shape>" * 280_000 + "</PageContents>"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("visio/pages/page1.xml", page)
    return path


def test_04a_r1_5_vsdx_expansion_is_refused_before_reading(tmp_path):
    path = vsdx_bomb(tmp_path / "bomb.vsdx")
    assert path.stat().st_size < 64 * 1024
    result = convert(path)
    assert result.status == ERROR and result.error_code == "archive_ratio", result
    assert "Shape" not in " ".join(result.warnings)  # no content in the message


def test_04a_r1_5_ooxml_with_too_many_members_is_refused(tmp_path):
    path = tmp_path / "many.docx"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
        for i in range(10_001):
            archive.writestr(f"word/media/p{i}.xml", "")
    result = convert(path)
    assert result.status == ERROR and result.error_code == "archive_too_many_members", result


def test_04a_r1_5_drawio_inflation_is_bounded(tmp_path):
    deflater = zlib.compressobj(9, zlib.DEFLATED, -15)
    payload = deflater.compress(b"a" * (80 * 1024 * 1024)) + deflater.flush()
    path = tmp_path / "bomb.drawio"
    path.write_text(f"<mxfile><diagram>{base64.b64encode(payload).decode()}</diagram></mxfile>")
    assert path.stat().st_size < 1024 * 1024
    result = convert(path)
    assert result.status == ERROR and result.error_code == "diagram_too_large", result


def test_04a_r1_5_huge_pdf_page_is_refused_before_rendering(tmp_path):
    import fitz

    path = tmp_path / "huge.pdf"
    with fitz.open() as doc:
        doc.new_page(width=14_400, height=14_400).insert_text((72, 72), "Fesih bildirimi " * 4)
        doc.save(path)
    result = convert(path)
    assert result.status == ERROR and result.error_code == "pdf_page_too_large", result


def test_04a_r1_5_next_file_converts_after_refusals(tmp_path):
    assert convert(vsdx_bomb(tmp_path / "b.vsdx")).status == ERROR
    assert convert(SAMPLE_DOCX).status == CONVERTED


def test_04a_r1_5_zip_never_inflates_past_the_declared_size(tmp_path):
    """The basis of check_zip: a member that lies about its size is not read past it."""
    path = tmp_path / "liar.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("a.xml", b"a" * (4 * 1024 * 1024))
    data = bytearray(path.read_bytes())
    declared = 1024
    local = data.find(b"PK\x03\x04")
    struct.pack_into("<I", data, local + 22, declared)
    central = data.find(b"PK\x01\x02")
    struct.pack_into("<I", data, central + 24, declared)
    path.write_bytes(bytes(data))
    with zipfile.ZipFile(path) as archive:
        assert archive.infolist()[0].file_size == declared
        try:
            out = archive.read("a.xml")
        except zipfile.BadZipFile:
            return
    assert len(out) <= declared


def worker_target(path: Path, deadline: float) -> ConversionResult:
    if path.name == "hog":
        block = bytearray(4 * 1024 * 1024 * 1024)
        return ConversionResult(str(len(block)), "hog")
    if path.name == "spin":
        while True:
            pass
    return ConversionResult("ok " * 10, "fine")


def test_04a_r1_5_converter_memory_limit_is_a_coded_result():
    pool = PersistentPool(60, "r1-mem", TARGET, Limits(memory_mb=1024))
    try:
        result = pool.convert(Path("hog"))
        assert result.status == ERROR and result.error_code == "convert_memory_limit", result
        assert pool.convert(Path("next")).status == CONVERTED  # the same worker goes on
    finally:
        pool.close()


def test_04a_r1_5_converter_cpu_limit_is_a_coded_result():
    pool = PersistentPool(60, "r1-cpu", TARGET, Limits(cpu_seconds=1))
    try:
        started = time.time()
        result = pool.convert(Path("spin"))
        assert result.status == ERROR and result.error_code == "convert_cpu_limit", result
        assert time.time() - started < 30  # the CPU limit, not the 60 s timeout
        assert pool.convert(Path("next")).status == CONVERTED  # a fresh worker
    finally:
        pool.close()


def test_04a_r1_5_compose_sets_worker_and_converter_limits():
    compose = yaml.safe_load((ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8"))
    worker = compose["services"]["worker"]
    assert worker["mem_limit"].startswith("${WORKER_MEM_LIMIT:-")
    for name in (
        "CONVERT_MEMORY_LIMIT_MB",
        "CONVERT_CPU_LIMIT_SECONDS",
        "UPLOAD_MAX_REQUEST_BYTES",
    ):
        assert name in worker["environment"], name


@pytest.mark.parametrize("chunked", [False, True])
def test_04a_r1_5_upload_middleware_stops_reading_past_the_limit(chunked):
    import asyncio

    from ffcore.api.upload_limit import UploadSizeLimit
    from ffcore.core.config import get_settings

    class Settings:
        upload_max_request_bytes = 1000

    class App:
        dependency_overrides = {get_settings: Settings}

    seen = {"read": 0, "answered": None}

    async def inner(scope, receive, send):
        while True:
            message = await receive()
            seen["read"] += len(message.get("body", b""))
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 202, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    pieces = [b"x" * 400] * 10
    headers = [] if chunked else [(b"content-length", b"4000")]
    scope = {
        "type": "http",
        "method": "POST",
        "headers": headers,
        "app": App(),
        "path": "/api/v1/projects/p/knowledge-bases/k/documents",
    }

    async def receive():
        body = pieces.pop(0) if pieces else b""
        return {"type": "http.request", "body": body, "more_body": bool(pieces)}

    sent = []

    async def send(message):
        sent.append(message)

    asyncio.run(UploadSizeLimit(inner)(scope, receive, send))
    assert sent[0]["status"] == 413
    assert b"request_too_large" in sent[1]["body"]
    assert seen["read"] <= 1200  # stopped at the limit, not after all 4000 bytes
