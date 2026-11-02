"""19 şart 4: the server health checklist (`scripts/m3_preflight.py`), on a fake env file.

The user runs it on the server against their own `.env`; it prints key names and verdicts only,
never a value. Here only synthetic, non-secret values are used.
"""

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("m3_preflight", REPO / "scripts" / "m3_preflight.py")
pf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pf)

SAFE = {
    "DEPLOY_PROFILE": "airgap",
    "OFFLINE": "true",
    "VECTOR_BACKEND": "qdrant",
    "INFERENCE_BACKEND": "ollama",
    "EGRESS_ALLOWLIST": "",
    "GUARDRAIL_EGRESS_ENABLED": "true",
    "FFCORE_TEST_HOOKS": "0",
    "RETENTION_DRY_RUN": "true",
    "RETENTION_AUDIT_DROP_ENABLED": "false",
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "OLLAMA_CONTEXT_LENGTH": "32768",
    **{key: f"synthetic-value-{i:02d}-0123456789abcdef" for i, key in enumerate(pf.SECRETS)},
}


def _write(tmp_path, values: dict) -> Path:
    path = tmp_path / "env"
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")
    return path


def test_19_s4_preflight_passes_a_safe_file(tmp_path):
    verdicts = pf.check(pf.read_env(_write(tmp_path, SAFE)))
    assert all(ok for _, ok, _ in verdicts), [v for v in verdicts if not v[1]]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("GUARDRAIL_EGRESS_ENABLED", "false"),
        ("OFFLINE", "false"),
        ("EGRESS_ALLOWLIST", "api.example.test"),
        ("FFCORE_TEST_HOOKS", "1"),
        ("RETENTION_DRY_RUN", "false"),
        ("RETENTION_AUDIT_DROP_ENABLED", "true"),
        ("JIRA_SUGGESTIONS_ENABLED", "true"),
        ("DEPLOY_PROFILE", "llmaas"),
        ("HF_HUB_OFFLINE", "0"),
    ],
)
def test_19_s4_preflight_rejects_unsafe_flags(tmp_path, key, value):
    verdicts = dict(
        (k, ok) for k, ok, _ in pf.check(pf.read_env(_write(tmp_path, SAFE | {key: value})))
    )
    assert verdicts[key] is False


def test_19_s4_preflight_rejects_missing_and_placeholder_secrets(tmp_path):
    values = dict(SAFE)
    del values["SERVICE_TOKEN"]
    values["SECRET_KEY"] = "CHANGE_ME"
    verdicts = {k: (ok, why) for k, ok, why in pf.check(pf.read_env(_write(tmp_path, values)))}
    assert verdicts["SERVICE_TOKEN"] == (False, "missing")
    assert verdicts["SECRET_KEY"] == (False, "placeholder")


def test_19_s4_guardrail_egress_must_be_set(tmp_path):
    values = dict(SAFE)
    del values["GUARDRAIL_EGRESS_ENABLED"]
    verdicts = {k: ok for k, ok, _ in pf.check(pf.read_env(_write(tmp_path, values)))}
    assert verdicts["GUARDRAIL_EGRESS_ENABLED"] is False


def test_19_s4_preflight_prints_no_values(tmp_path, capsys):
    values = SAFE | {"SECRET_KEY": "CHANGE_ME", "EGRESS_ALLOWLIST": "api.example.test"}
    code = pf.main(["--env-file", str(_write(tmp_path, values))])
    out = capsys.readouterr()
    assert code == 1
    printed = out.out + out.err
    for value in values.values():
        if value and len(value) > 5:
            assert value not in printed, value
    assert "FAIL SECRET_KEY" in printed and "OK SERVICE_TOKEN" in printed


def test_19_s4_preflight_paycore_stack_names(tmp_path):
    values = dict(SAFE)
    for name in (
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "LITELLM_MASTER_KEY",
        "LITELLM_INTERNAL_KEY",
        "LITELLM_SALT_KEY",
    ):
        values[f"FFCORE_{name}"] = values.pop(name)
    for name in ("OFFLINE", "EGRESS_ALLOWLIST", "FFCORE_TEST_HOOKS"):  # fixed by the compose file
        del values[name]
    values["FFCORE_LANGFUSE_PUBLIC_KEY"] = "synthetic-value-90-0123456789abcdef"
    values["FFCORE_LANGFUSE_SECRET_KEY"] = "synthetic-value-91-0123456789abcdef"
    verdicts = {k: ok for k, ok, _ in pf.check(pf.read_env(_write(tmp_path, values)), "paycore")}
    assert all(verdicts.values()), [k for k, ok in verdicts.items() if not ok]
    assert "POSTGRES_PASSWORD" not in verdicts and verdicts["FFCORE_LANGFUSE_SECRET_KEY"]
    assert pf.main(["--env-file", str(_write(tmp_path, values)), "--stack", "paycore"]) == 0
    unsafe = values | {"OFFLINE": "false"}  # absent is fine, a wrong value is not
    assert pf.main(["--env-file", str(_write(tmp_path, unsafe)), "--stack", "paycore"]) == 1
    del values["FFCORE_LANGFUSE_PUBLIC_KEY"]
    assert pf.main(["--env-file", str(_write(tmp_path, values)), "--stack", "paycore"]) == 1


def test_19_r1_preflight_internal_hosts_match_the_compose_constant(tmp_path):
    ok = SAFE | {"ALLOWED_INTERNAL_HOSTS": "langfuse-web,litellm,mcp-sql,mcp-search"}
    assert dict((k, v) for k, v, _ in pf.check(pf.read_env(_write(tmp_path, ok))))[
        "ALLOWED_INTERNAL_HOSTS"
    ]
    wide = SAFE | {"ALLOWED_INTERNAL_HOSTS": "litellm,langfuse-web,mcp-search,mcp-sql,10.0.0.5"}
    verdicts = {k: (v, why) for k, v, why in pf.check(pf.read_env(_write(tmp_path, wide)))}
    assert verdicts["ALLOWED_INTERNAL_HOSTS"] == (False, "not the M3 value")
    paycore = {k: v for k, v, _ in pf.check(pf.read_env(_write(tmp_path, SAFE)), "paycore")}
    assert paycore["ALLOWED_INTERNAL_HOSTS"] is True  # fixed by compose.ffcore.yml there
    other = SAFE | {"ALLOWED_INTERNAL_HOSTS": "litellm"}
    paycore = {k: v for k, v, _ in pf.check(pf.read_env(_write(tmp_path, other)), "paycore")}
    assert paycore["ALLOWED_INTERNAL_HOSTS"] is False
