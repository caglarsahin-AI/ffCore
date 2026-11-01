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
# On the PayCore server one .env serves both stacks: PayCore's own Postgres owns POSTGRES_*, so
# FFCore's database user and password are FFCORE_POSTGRES_* there (paycoreLLM compose.ffcore.yml).
STACK_RENAMES = {"paycore": {"POSTGRES_PASSWORD": "FFCORE_POSTGRES_PASSWORD"}}
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


def check(env: dict[str, str], stack: str = "ffcore") -> list[tuple[str, bool, str]]:
    renames = STACK_RENAMES.get(stack, {})
    out = []
    for key, (accepted, may_be_absent) in EXPECTED.items():
        if key not in env:
            out.append(
                (key, may_be_absent, "absent, compose default" if may_be_absent else "missing")
            )
        else:
            ok = env[key].strip().lower() in accepted
            out.append((key, ok, "" if ok else "not the M3 value"))
    for key in PRESENT:
        out.append((key, bool(env.get(key)), "" if env.get(key) else "missing"))
    for key in (renames.get(k, k) for k in SECRETS):
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
