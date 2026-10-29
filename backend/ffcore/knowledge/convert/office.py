"""Docling: DOCX, PPTX, HTML, Markdown and text-layer PDFs → Markdown (headings and tables kept).

Adapted from PayCore `convert/docling_convert.py`: one converter per worker thread (loading the
layout and table models costs ~1,4 GB and many seconds, so never per file), loading serialized,
`do_ocr` off (scans go to ocr.py with the approved engine), TableFormer ACCURATE.
"""

import importlib.metadata
import threading
from pathlib import Path
from typing import Any

from ffcore.knowledge.convert.types import MIN_TEXT_CHARS, ConversionResult, empty, failed
from ffcore.knowledge.models import ModelMissing

_local = threading.local()
_load_lock = threading.Lock()


def _version() -> str:
    try:
        return importlib.metadata.version("docling")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _converter() -> Any:
    cached = getattr(_local, "converter", None)
    if cached is not None:
        return cached
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    from ffcore.knowledge.models import DOCLING_REPOS, hf_path

    # Docling loads its weights from the hub cache itself (offline by the image's
    # HF_HUB_OFFLINE=1); checking them first gives the model name and path (r1 MAJOR-6).
    for repo, revision in DOCLING_REPOS.items():
        hf_path(repo, revision)
    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    options.table_structure_options.mode = TableFormerMode.ACCURATE
    with _load_lock:
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        )
    _local.converter = converter
    return converter


def convert_with_docling(path: Path) -> ConversionResult:
    method = f"docling@{_version()}"
    try:
        text = _converter().convert(str(path)).document.export_to_markdown()
    except ModelMissing as exc:
        return failed(method, exc.code, str(exc))
    except Exception as exc:  # noqa: BLE001 - recorded with its message; callers fall back
        return failed(method, "docling_failed", str(exc)[:500])
    text = (text or "").strip()
    if len(text) < MIN_TEXT_CHARS:
        return empty(text, method)
    return ConversionResult(text, method)
