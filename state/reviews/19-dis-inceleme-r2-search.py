"""Reviewer probe r2: search the paycore-like KB for 1002's text (old version must stay)."""
import os, sys
import httpx
BASE = "http://localhost:8000/api/v1"
with httpx.Client(timeout=120) as c:
    r = c.post(f"{BASE}/auth/login", json={"email": os.environ["PROBE_EMAIL"], "password": os.environ["PROBE_PASSWORD"]})
    h = {"Cookie": "ffcore_session=" + r.cookies.get("ffcore_session")}
    pid = next(p["id"] for p in c.get(f"{BASE}/projects", headers=h).json()["data"] if p["key"] == "r19r")
    kb = next(k for k in c.get(f"{BASE}/projects/{pid}/knowledge-bases", headers=h).json()["data"] if k["key"] == "paycore-like")
    r = c.post(f"{BASE}/projects/{pid}/knowledge-bases/{kb['id']}/search", json={"query": sys.argv[1], "top_k": 10}, headers=h)
    print("SEARCH", r.status_code, sorted(r.json()) if isinstance(r.json(), dict) else type(r.json()))
    body = r.json(); items = body.get("data") or body.get("results") or body.get("hits") or []
    print(" keys", sorted(items[0]) if items else None)
    for hit in items:
        print(" hit", hit.get("document_name"), hit.get("document_id"), round(hit.get("rerank_score") or hit.get("embed_score") or 0, 3), " ".join((hit.get("text") or "")[:60].split()))
