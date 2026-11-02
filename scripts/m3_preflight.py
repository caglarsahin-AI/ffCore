"""19 şart 4: the PayCore server health checklist, before the first `up` and before each
measurement window. The user runs it on the server against the `.env` they filled in:

    python3 scripts/m3_preflight.py --env-file /path/to/.env

It prints `OK <KEY>` or `FAIL <KEY> (<reason>)` and nothing else: no value, ever, not even a
masked one. Exit 1 if any check fails. The values are the M3 contract (plan/19): airgap, no egress,
the built-in egress PII guardrail on (never turned off for latency: an A/B decision instead),
test hooks off, retention dry-run and no audit DROP, Jira write gate closed, model weights
offline, and every secret present and not a placeholder (secrets are made on the server by the
user; this package ships none).
"""

import argparse
import sys
from pathlib import Path

# key -> (accepted values, reason when not), "" allowed only where listed. None: key may be
# absent (the compose default is the safe one).
EXPECTED: dict[str, tuple[set[str], bool]] = {
    "DEPLOY_PROFILE": ({"airgap"}, False),
    "OFFLINE": ({"true"}, False),
    "VECTOR_BACKEND": ({"qdrant"}, False),
    "INFERENCE_BACKEND": ({"ollama"}, False),
    "EGRESS_ALLOWLIST": ({""}, True),
    "GUARDRAIL_EGRESS_ENABLED": ({"true"}, False),
    "FFCORE_TEST_HOOKS": ({"0"}, True),
    "RETENTION_DRY_RUN": ({"true"}, True),
    "RETENTION_AUDIT_DROP_ENABLED": ({"false"}, True),
    "JIRA_SUGGESTIONS_ENABLED": ({"false"}, True),
    "HF_HUB_OFFLINE": ({"1"}, False),
    "TRANSFORMERS_OFFLINE": ({"1"}, False),
}
PRESENT = ("OLLAMA_CONTEXT_LENGTH",)
SECRETS = (
    "SERVICE_TOKEN",
    "OBO_JWT_SECRET",
    "SECRET_KEY",
    "FERNET_KEY",
    "LITELLM_MASTER_KEY",
    "LITELLM_INTERNAL_KEY",
    "LITELLM_SALT_KEY",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "AGENT_DEMO_DB_PASSWORD",
)
# On the PayCore server one .env serves both stacks: PayCore owns POSTGRES_*, so FFCore's database,
# Redis and LiteLLM secrets are FFCORE_* there, plus the Langfuse project keys FFCore uses in
# PayCore's Langfuse (paycoreLLM compose.ffcore.yml). The M3 flags compose.ffcore.yml fixes
# itself may be absent from that .env; present, they must still hold the M3 value.
STACK_RENAMES = {
    "paycore": {
        "POSTGRES_PASSWORD": "FFCORE_POSTGRES_PASSWORD",
        "REDIS_PASSWORD": "FFCORE_REDIS_PASSWORD",
        "LITELLM_MASTER_KEY": "FFCORE_LITELLM_MASTER_KEY",
        "LITELLM_INTERNAL_KEY": "FFCORE_LITELLM_INTERNAL_KEY",
        "LITELLM_SALT_KEY": "FFCORE_LITELLM_SALT_KEY",
    }
}
STACK_SECRETS = {"paycore": ("FFCORE_LANGFUSE_PUBLIC_KEY", "FFCORE_LANGFUSE_SECRET_KEY")}
STACK_FIXED = {
    "paycore": {
        "OFFLINE",
        "EGRESS_ALLOWLIST",
        "FFCORE_TEST_HOOKS",
        "RETENTION_DRY_RUN",
        "RETENTION_AUDIT_DROP_ENABLED",
        "TRANSFORMERS_OFFLINE",
    }
}
PLACEHOLDERS = ("change_me", "changeme", "dummy", "example", "placeholder", "secret", "xxx")


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip().removeprefix("export ").strip()] = value.strip().strip("'\"")
    return values


# Hosts exempt from the OFFLINE and private-address egress checks (EgressPolicy.check_host): the
# M3 list is fixed (r1 MINOR-2). FFCore's .env.example list; on the PayCore server
# compose.ffcore.yml sets it itself. Absent means no exemption (safe); present, it must be the
# same set, never a wider one.
INTERNAL_HOSTS = {
    "ffcore": {"litellm", "langfuse-web", "mcp-search", "mcp-sql"},
    "paycore": {
        "litellm",
        "langfuse-web",
        "mcp-search",
        "mcp-sql",
        "ffcore-qdrant",
        "host.docker.internal",
    },
}


def _hosts(value: str) -> set[str]:
    return {h.strip() for h in value.split(",") if h.strip()}


def check(env: dict[str, str], stack: str = "ffcore") -> list[tuple[str, bool, str]]:
    renames = STACK_RENAMES.get(stack, {})
    fixed = STACK_FIXED.get(stack, set())
    out = []
    for key, (accepted, may_be_absent) in EXPECTED.items():
        may_be_absent = may_be_absent or key in fixed
        if key not in env:
            out.append(
                (key, may_be_absent, "absent, compose default" if may_be_absent else "missing")
            )
        else:
            ok = env[key].strip().lower() in accepted
            out.append((key, ok, "" if ok else "not the M3 value"))
    if "ALLOWED_INTERNAL_HOSTS" in env:
        same = _hosts(env["ALLOWED_INTERNAL_HOSTS"]) == INTERNAL_HOSTS[stack]
        out.append(("ALLOWED_INTERNAL_HOSTS", same, "" if same else "not the M3 value"))
    else:
        out.append(("ALLOWED_INTERNAL_HOSTS", True, "absent, no exemption"))
    for key in PRESENT:
        out.append((key, bool(env.get(key)), "" if env.get(key) else "missing"))
    for key in [*(renames.get(k, k) for k in SECRETS), *STACK_SECRETS.get(stack, ())]:
        value = env.get(key, "")
        if not value:
            out.append((key, False, "missing"))
        elif any(p in value.lower() for p in PLACEHOLDERS) or len(value) < 16:
            out.append((key, False, "placeholder"))
        else:
            out.append((key, True, ""))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument(
        "--stack",
        choices=("ffcore", "paycore"),
        default="ffcore",
        help="paycore: the shared PayCore server .env (FFCORE_POSTGRES_* names)",
    )
    args = parser.parse_args(argv)
    verdicts = check(read_env(args.env_file), args.stack)
    for key, ok, why in verdicts:
        print(f"OK {key}" + (f" ({why})" if why else "") if ok else f"FAIL {key} ({why})")
    failed = sum(1 for _, ok, _ in verdicts if not ok)
    print(f"m3 preflight: {'FAIL' if failed else 'OK'} ({failed} failed)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
