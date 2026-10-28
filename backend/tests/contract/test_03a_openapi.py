"""03a acceptance 16: the committed OpenAPI draft equals what the application serves."""

import re
from pathlib import Path

from ffcore.api import API_PREFIX
from ffcore.api.openapi_export import render
from ffcore.main import app

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "03a.yaml"
REGENERATE = "python -m ffcore.api.openapi_export > openapi/03a.yaml"


def test_03a_16_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render(), f"draft drifted; run: {REGENERATE}"


def test_03a_16_app_serves_every_draft_path():
    served = set(app.openapi()["paths"])
    drafted = {line.strip().rstrip(":") for line in render().splitlines() if line[:3] == "  /"}
    assert drafted, "the draft has no paths"
    assert all(path.startswith(API_PREFIX) for path in drafted)
    assert drafted <= served


def test_03a_16_draft_text_is_english():
    # Application surface is English (K-INIT-0007): no Turkish letters in the contract.
    assert not re.search("[çğıöşüÇĞİÖŞÜ]", render())
