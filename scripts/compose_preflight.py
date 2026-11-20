"""Profile and overlay coherence check for an FFCore compose installation (package 12).

Compose cannot derive COMPOSE_PROFILES or COMPOSE_FILE from DEPLOY_PROFILE, and an overlay
file without its profile (or the reverse) either starts nothing or stops on a missing
variable that has nothing to do with the mistake (FOLLOWUP-35). This check names every
incoherent combination and the fix. It runs first in `make smoke`, and on the host before
`docker compose up`:

    python scripts/compose_preflight.py --env-file .env
    python scripts/compose_preflight.py --env-file .env --egress-list   # corporate firewall list

Pure Python, standard library only. Exit 0 and one line per check, or exit 1 and the error.
"""

import argparse
import os
import re
import sys
from pathlib import Path

# Profiles a compose file in this repository defines. An unknown name starts nothing, so it
# is refused instead of silently ignored.
KNOWN_PROFILES = {"qdrant", "ollama", "egress", "tls", "tools", "test", "e2e"}
# Profiles whose services live in their own overlay file (compose interpolates ${VAR:?}
# before it drops inactive profiles, so the overlay is only added when the profile is on).
OVERLAYS = {
    "ollama": "deploy/docker-compose.ollama.yml",
    "egress": "deploy/docker-compose.egress.yml",
    "tls": "deploy/docker-compose.tls.yml",
}
HOST = re.compile(r"^(\*\.)?([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)*[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


class PreflightError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _compose_files(value: str, separator: str | None) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []
    if separator is None:
        # Compose uses the host's path separator: ';' on Windows, ':' elsewhere.
        separator = ";" if ";" in value else ":"
    return [Path(item.strip()).as_posix().removeprefix("./") for item in value.split(separator)]


def _allowlist(value: str) -> list[str]:
    hosts = _split_list(value)
    for host in hosts:
        if not HOST.match(host.lower()):
            raise PreflightError(
                "egress_allowlist_invalid",
                f"{host!r} in EGRESS_ALLOWLIST is not a host name or *.suffix "
                "(no scheme, port, path or inner wildcard)",
            )
    return hosts


def egress_list(value: str, ports: str = "443") -> list[str]:
    """EGRESS_ALLOWLIST x EGRESS_ALLOWED_PORTS as the corporate firewall rule list."""
    hosts = _allowlist(value)
    if not hosts:
        raise PreflightError("egress_allowlist_empty", "EGRESS_ALLOWLIST is empty")
    port_list = (ports or "443").split()
    bad = [port for port in port_list if not port.isdigit()]
    if bad:
        raise PreflightError("egress_ports_invalid", f"EGRESS_ALLOWED_PORTS: {' '.join(bad)}")
    return [f"{host} {port}/tcp" for host in hosts for port in port_list]


def check(env: dict) -> list[str]:
    deploy = env.get("DEPLOY_PROFILE", "")
    backend = env.get("INFERENCE_BACKEND", "")
    profiles = _split_list(env.get("COMPOSE_PROFILES", ""))
    files = _compose_files(env.get("COMPOSE_FILE", ""), env.get("COMPOSE_PATH_SEPARATOR"))
    lines = [f"DEPLOY_PROFILE={deploy} INFERENCE_BACKEND={backend}"]

    unknown = [name for name in profiles if name not in KNOWN_PROFILES]
    if unknown:
        raise PreflightError(
            "unknown_profile",
            f"COMPOSE_PROFILES names {', '.join(unknown)}; known: {', '.join(sorted(KNOWN_PROFILES))}",
        )

    for profile, overlay in OVERLAYS.items():
        active, added = profile in profiles, overlay in files
        if active and not added:
            raise PreflightError(
                "profile_overlay_mismatch",
                f"profile {profile} is in COMPOSE_PROFILES but {overlay} is not in COMPOSE_FILE; "
                f"add it (COMPOSE_FILE=compose.yaml:{overlay}) or drop the profile",
            )
        if added and not active:
            raise PreflightError(
                "profile_overlay_mismatch",
                f"{overlay} is in COMPOSE_FILE but profile {profile} is not in COMPOSE_PROFILES; "
                f"add {profile} to COMPOSE_PROFILES or remove the file",
            )

    if "ollama" in profiles:
        if deploy != "airgap" or backend != "ollama":
            raise PreflightError(
                "profile_backend_mismatch",
                "the ollama profile needs DEPLOY_PROFILE=airgap and INFERENCE_BACKEND=ollama",
            )
        if not env.get("OLLAMA_CONTEXT_LENGTH"):
            raise PreflightError(
                "ollama_context_length_missing",
                "OLLAMA_CONTEXT_LENGTH is empty (Ollama's default 4096 truncates prompts silently)",
            )
        lines.append(f"ollama: compose service, OLLAMA_CONTEXT_LENGTH={env['OLLAMA_CONTEXT_LENGTH']}")
    elif deploy == "airgap" and backend == "ollama":
        lines.append("ollama: external (profile inactive; the address is the ollama provider's)")

    if "egress" in profiles:
        if deploy != "llmaas":
            raise PreflightError(
                "egress_requires_llmaas",
                "the egress profile is for llmaas; airgap has no way out (OFFLINE=true)",
            )
        hosts = _allowlist(env.get("EGRESS_ALLOWLIST", ""))
        if not hosts:
            raise PreflightError(
                "egress_allowlist_empty",
                "the egress profile is on but EGRESS_ALLOWLIST is empty; the proxy would refuse "
                "every provider (docs/kurulum.md, egress)",
            )
        if "tls" not in profiles:
            raise PreflightError(
                "egress_requires_tls",
                "the egress profile makes the app network internal, where published ports do not "
                "reach the host; add the tls profile (the reverse proxy is the way in)",
            )
        lines.append(f"egress: forward proxy, {len(hosts)} hosts in EGRESS_ALLOWLIST")
    if "tls" in profiles:
        lines.append("tls: reverse proxy (internal 8443, public Teams path 9443)")
    return lines


def read_env_file(path: Path) -> dict:
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", type=Path, help="read the settings from this file")
    parser.add_argument(
        "--egress-list", action="store_true", help="print EGRESS_ALLOWLIST as firewall rules"
    )
    args = parser.parse_args(argv)
    env = read_env_file(args.env_file) if args.env_file else dict(os.environ)
    try:
        if args.egress_list:
            lines = egress_list(env.get("EGRESS_ALLOWLIST", ""), env.get("EGRESS_ALLOWED_PORTS", ""))
        else:
            lines = check(env)
    except PreflightError as exc:
        print(f"FAIL  preflight {exc}")
        return 1
    for line in lines:
        print(line if args.egress_list else f"ok    {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
