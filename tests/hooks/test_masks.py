"""Log mask: `-u user:pass` and JSON credential fields (fix/ajan-hooklari-2 D3,
FOLLOWUP-189 d; review r2 MINOR-3 M10/M12)."""

from __future__ import annotations

import pytest
from conftest import bash, run_hook


@pytest.mark.parametrize(
    ("raw", "secret", "kept"),
    [
        ("curl -u probe:S3cr3tPass https://x", "S3cr3tPass", "-u ***"),
        ("curl --user probe:S3cr3tPass https://x", "S3cr3tPass", "--user ***"),
        ("curl -s -u probe:S3cr3tPass", "probe:", "curl -s -u ***"),
        ("""curl -d '{"token":"TOK123"}' x""", "TOK123", '"token":"***"'),
        ('{"api_key": "AK-99"}', "AK-99", '"api_key":"***"'),
        ('{"password":"pw1","user":"u"}', "pw1", '"user":"u"'),
        ('{"secret":"s3"}', "s3", '"secret":"***"'),
        ('{"key":"k1"}', "k1", '"key":"***"'),
        ('{"Token":"T2"}', "T2", '"Token":"***"'),
    ],
)
def test_mask_hides_value(guard, raw, secret, kept):
    masked = guard.mask_secrets(raw)
    assert secret not in masked, masked
    assert kept in masked, masked


@pytest.mark.parametrize(
    "raw",
    [
        "docker compose run -u 1000 tools make seed",
        '{"name":"ok","count":"3"}',
        "git log -u main",
    ],
)
def test_mask_leaves_harmless_text(guard, raw):
    assert guard.mask_secrets(raw) == raw


def test_log_line_has_no_credentials(main_root):
    cmd = """cat .env; curl -u a:SECRETPW -d '{"token":"TOK123"}' http://h"""
    proc = run_hook(bash(cmd), main_root)
    assert proc.returncode == 2
    log = (main_root / "state" / "evidence" / "hook-guard.log").read_text(encoding="utf-8")
    assert "SECRETPW" not in log and "TOK123" not in log, log
    assert "ENV" in log


# --- r2 (K-HOOK2-0007 MINOR-4): remaining variants M04-M08 --------------------


@pytest.mark.parametrize(
    ("raw", "secret"),
    [
        ('curl -d "{\\"token\\":\\"TOK4\\"}" x', "TOK4"),  # M04 escaped JSON
        ("curl -uuser:PW5 https://x", "PW5"),  # M05 attached
        ("curl --user=user:PW6 https://x", "PW6"),  # M06
        ('{"access_token":"AT7"}', "AT7"),  # M07
        ('{"apiKey":"AK8"}', "AK8"),  # M08
        ('{"x-api-key": "AK9"}', "AK9"),
        ('{"client_secret":"CS1"}', "CS1"),
    ],
)
def test_r2_mask_variants(guard, raw, secret):
    masked = guard.mask_secrets(raw)
    assert secret not in masked, masked
    assert "***" in masked, masked
