"""09 madde 1, ek 2: skor okuma yollari (filtre), iz uzerinden skor, dataset run silme sonrasi skorlar."""

import base64
import json
import os
import urllib.request

HOST = "http://langfuse-web:3000"
AUTH = "Basic " + base64.b64encode(
    f"{os.environ['LANGFUSE_INIT_PROJECT_PUBLIC_KEY']}:{os.environ['LANGFUSE_INIT_PROJECT_SECRET_KEY']}".encode()
).decode()


def get(path):
    req = urllib.request.Request(HOST + path)
    req.add_header("Authorization", AUTH)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def out(name, val):
    print(json.dumps({"check": name, "note": val}, ensure_ascii=False, default=str), flush=True)


s, allv2 = get("/api/public/v2/scores?limit=100")
rows = allv2["data"]
out("R0 all v2 scores", [(r["name"], r.get("traceId"), r.get("datasetRunId")) for r in rows])
tid = next(r["traceId"] for r in rows if r.get("traceId"))
for q in ["name=contains", "dataType=CATEGORICAL", "scoreIds=" + rows[0]["id"], "traceIds=" + tid,
          "traceId=" + tid, "datasetRunId=x", "fields=score"]:
    s, b = get("/api/public/v2/scores?" + q)
    out("R1 v2 ?" + q.split("=")[0], (s, b["meta"]["totalItems"] if isinstance(b, dict) else b))
for q in ["name=contains", "traceId=" + tid]:
    s, b = get("/api/public/scores?" + q)
    out("R2 v1 ?" + q.split("=")[0], (s, b["meta"]["totalItems"] if isinstance(b, dict) else b))
s, b = get(f"/api/public/traces/{tid}")
out("R3 trace has scores", (s, [(x["name"], x.get("value")) for x in b.get("scores", [])] if isinstance(b, dict) else b))
