"""DRIFT-85 review r1 MAJOR-1: the real-resolver egress test sends a `.invalid` lookup that
Docker forwards to the host's (the institution's) DNS, so it runs only with RUN_DNS_TESTS=1.
Without the flag it is NOT_RUN with its reason before any fixture or lookup runs (the root
conftest skip), and the development guide says what the flag sends out."""

from pathlib import Path

from tests.conftest import FLAGS
from tests.integration import test_03b_egress_dns

ROOT = Path(__file__).resolve().parents[3]


def test_03b_real_resolver_test_needs_its_own_flag():
    assert FLAGS["dns"] == "RUN_DNS_TESTS"
    marks = getattr(test_03b_egress_dns, "pytestmark", [])
    marks = {m.name for m in (marks if isinstance(marks, list) else [marks])}
    assert "dns" in marks


def test_03b_dns_flag_is_documented_as_external():
    guide = (ROOT / "docs" / "gelistirme-ortami.md").read_text(encoding="utf-8")
    assert "RUN_DNS_TESTS=1" in guide and "DNS" in guide
