"""Reviewer probe for fix/19-dis-inceleme r1 (154c), run inside the review19r backend container.

docker exec -e OFFLINE=true -e PROBE_EMAIL -e PROBE_PASSWORD review19r-backend-1 python /tmp/probe.py
Prints no secret: the password comes from the environment and is never echoed.
"""

import asyncio
import os

import httpx

from ffcore.core.config import get_settings
from ffcore.core.egress import EgressDenied
from ffcore.knowledge import ingest

BASE = "http://localhost:8000/api/v1"


def setup() -> None:
    with httpx.Client(timeout=30) as c:
        r = c.post(f"{BASE}/auth/login", json={"email": os.environ["PROBE_EMAIL"],
                                               "password": os.environ["PROBE_PASSWORD"]})
        assert r.status_code == 200, r.status_code
        cookie = r.cookies.get("ffcore_session") or r.headers["set-cookie"].split(";")[0].split("=", 1)[1]
        h = {"Cookie": f"ffcore_session={cookie}"}
        r = c.post(f"{BASE}/projects", json={"key": "r19r", "name": "review 19r"}, headers=h)
        print("PROJECT", r.status_code)
        pid = r.json()["id"] if r.status_code == 201 else None
        if pid is None:
            pid = next(p["id"] for p in c.get(f"{BASE}/projects", headers=h).json()["data"] if p["key"] == "r19r")
        r = c.post(f"{BASE}/projects/{pid}/knowledge-bases", json={"key": "paycore-like", "name": "pl"}, headers=h)
        print("KB", r.status_code, r.text[:200] if r.status_code != 201 else "")


async def embed_probe() -> None:
    s = get_settings()
    print("OFFLINE", s.offline, "allowed", sorted(s.allowed_internal_hosts))
    e = await ingest.HttpEmbedClient(s).embed(["deneme metni"])
    print("EMBED_OK dense", len(e.dense[0]), "truncated", e.truncated)
    old = s.model_copy(update={"allowed_internal_hosts": [h for h in s.allowed_internal_hosts if h != "backend"]})
    try:
        await ingest.HttpEmbedClient(old).embed(["deneme"])
        print("OLD_VALUE_UNEXPECTED_OK")
    except EgressDenied as exc:
        print("OLD_VALUE EgressDenied", getattr(exc, "code", type(exc).__name__))


if __name__ == "__main__":
    setup()
    asyncio.run(embed_probe())
