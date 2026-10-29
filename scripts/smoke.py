"""Smoke check for a running FFCore compose stack.

Runs inside the tools container (docker compose run --rm tools make smoke) and reaches
services by compose service name. Every check prints one line; any failure exits 1.
Ollama checks run only when the ollama compose profile is active; otherwise the line
says so explicitly (no silent skip).
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_S = 10

BACKEND_URL = os.environ.get("SMOKE_BACKEND_URL", "http://backend:8000")
LITELLM_URL = os.environ.get("SMOKE_LITELLM_URL", "http://litellm:4000")
LANGFUSE_URL = os.environ.get("SMOKE_LANGFUSE_URL", "http://langfuse-web:3000")
OLLAMA_URL = os.environ.get("SMOKE_OLLAMA_URL", "http://ollama:11434")
# 05a: the built-in MCP tool servers (internal network only).
MCP_URLS = {
    "mcp-search": os.environ.get("SMOKE_MCP_SEARCH_URL", "http://mcp-search:8000"),
    "mcp-sql": os.environ.get("SMOKE_MCP_SQL_URL", "http://mcp-sql:8000"),
}


class SmokeError(Exception):
    pass


def _request(
    url: str, payload: dict | None = None, headers: dict | None = None
) -> tuple[int, bytes]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url, data=data, method="POST" if data else "GET", headers=headers or {}
    )
    if data:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SmokeError(f"unreachable: {url} ({exc})") from exc


def check_backend() -> str:
    status, body = _request(f"{BACKEND_URL}/healthz")
    if status != 200 or json.loads(body) != {"status": "ok"}:
        raise SmokeError(f"backend /healthz returned {status}")
    return "backend /healthz 200"


def check_litellm() -> str:
    status, _ = _request(f"{LITELLM_URL}/health/liveliness")
    if status != 200:
        raise SmokeError(f"litellm /health/liveliness returned {status}")
    return "litellm /health/liveliness 200"


def check_langfuse() -> str:
    status, _ = _request(f"{LANGFUSE_URL}/api/public/health")
    if status != 200:
        raise SmokeError(f"langfuse /api/public/health returned {status}")
    # 02: the project keys must exist and work (Langfuse init, LiteLLM callback, backend).
    missing = [n for n in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY") if not os.environ.get(n)]
    if missing:
        raise SmokeError(f"not set: {', '.join(missing)} (make langfuse-init, then .env)")
    token = f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}"
    auth = {"Authorization": "Basic " + base64.b64encode(token.encode()).decode("ascii")}
    status, _ = _request(f"{LANGFUSE_URL}/api/public/projects", headers=auth)
    if status != 200:
        raise SmokeError(f"langfuse /api/public/projects with the project keys returned {status}")
    return "langfuse /api/public/health 200, /api/public/projects 200"


def _ollama_profile_active() -> bool:
    profiles = os.environ.get("COMPOSE_PROFILES", "")
    return "ollama" in [p.strip() for p in profiles.split(",")]


def _model_list() -> list[str]:
    profile = os.environ.get("DEPLOY_PROFILE")
    if not profile:
        raise SmokeError("DEPLOY_PROFILE is not set")
    path = ROOT / "deploy" / "ollama" / f"models.{profile}.txt"
    if not path.exists():
        raise SmokeError(f"model list missing: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def check_ollama() -> list[str]:
    if not _ollama_profile_active():
        return ["skipped: ollama profile inactive"]
    context_length = os.environ.get("OLLAMA_CONTEXT_LENGTH", "")
    if not context_length.isdigit():
        raise SmokeError("OLLAMA_CONTEXT_LENGTH is not set to an integer")
    status, body = _request(f"{OLLAMA_URL}/api/tags")
    if status != 200:
        raise SmokeError(f"ollama /api/tags returned {status}")
    pulled = {model["name"] for model in json.loads(body).get("models", [])}
    lines = [f"ollama /api/tags 200, OLLAMA_CONTEXT_LENGTH={context_length}"]
    for name in _model_list():
        if name not in pulled and f"{name}:latest" not in pulled:
            raise SmokeError(f"model_not_pulled: {name}; make pull")
        status, body = _request(f"{OLLAMA_URL}/api/show", {"model": name})
        if status != 200:
            raise SmokeError(f"ollama /api/show {name} returned {status}")
        info = json.loads(body).get("model_info", {})
        trained = next((v for k, v in info.items() if k.endswith(".context_length")), None)
        if trained is None:
            raise SmokeError(f"ollama /api/show {name}: context_length missing")
        if int(context_length) > int(trained):
            raise SmokeError(
                f"OLLAMA_CONTEXT_LENGTH={context_length} exceeds {name} context_length={trained}"
            )
        lines.append(f"ollama {name} context_length={trained} >= {context_length}")
    return lines


def check_mcp() -> list[str]:
    lines = []
    for name, base in MCP_URLS.items():
        status, _ = _request(f"{base}/healthz")
        if status != 200:
            raise SmokeError(f"{name} /healthz returned {status}")
        lines.append(f"{name} /healthz 200")
    return lines


CHECKS = (check_backend, check_litellm, check_langfuse, check_mcp, check_ollama)


def main() -> int:
    failed = False
    for check in CHECKS:
        try:
            result = check()
            for line in result if isinstance(result, list) else [result]:
                print(f"ok    {line}")
        except SmokeError as exc:
            failed = True
            print(f"FAIL  {check.__name__}: {exc}")
    print("smoke: FAILED" if failed else "smoke: passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
