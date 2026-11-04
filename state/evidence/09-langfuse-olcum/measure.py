"""09 madde 1: Langfuse 3.120.0 OSS datasets / dataset runs / scores / judge olcumu.

Ic agda (internal: true) backend imajinda kosar; yalniz .env.test sahte anahtarlari.
Cikti: her kontrol icin bir satir JSON (ad, yontem, http durumu, ozet).
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

HOST = "http://langfuse-web:3000"
PK = os.environ["LANGFUSE_INIT_PROJECT_PUBLIC_KEY"]
SK = os.environ["LANGFUSE_INIT_PROJECT_SECRET_KEY"]
AUTH = "Basic " + base64.b64encode(f"{PK}:{SK}".encode()).decode()
TAG = uuid.uuid4().hex[:6]
DS = f"m09-{TAG}"
RESULTS = []


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(HOST + path, data=data, method=method)
    req.add_header("Authorization", AUTH)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw[:200]


def rec(name, status, note):
    line = {"check": name, "status": status, "note": note}
    RESULTS.append(line)
    print(json.dumps(line, ensure_ascii=False), flush=True)


def short(obj, keys):
    if not isinstance(obj, dict):
        return str(obj)[:160]
    return {k: obj.get(k) for k in keys if k in obj}


# --- M1 datasets (REST) ---
s, b = call("POST", "/api/public/v2/datasets", {"name": DS, "description": "m09", "metadata": {"suite": "x"}})
if s == 404 or s == 405:
    s, b = call("POST", "/api/public/datasets", {"name": DS, "description": "m09", "metadata": {"suite": "x"}})
rec("M1a create dataset", s, short(b, ["id", "name", "metadata"]))
s, b = call("GET", f"/api/public/v2/datasets/{DS}")
rec("M1b get dataset v2", s, short(b, ["id", "name"]))
item_id = f"{DS}-q01"
item = {
    "datasetName": DS,
    "id": item_id,
    "input": {"message": "What is the notice period?", "variables": {}},
    "expectedOutput": {"must_contain": ["30 days"], "must_cite": ["contract-a.pdf"]},
    "metadata": {"tags": ["sql"], "answerable": True, "style": "dogrudan", "expected_docs": ["contract-a.pdf"]},
}
s, b = call("POST", "/api/public/dataset-items", item)
rec("M1c create item (our schema mapping)", s, short(b, ["id", "input", "expectedOutput", "metadata", "status"]))
item2 = dict(item, expectedOutput={"must_contain": ["thirty days"]})
s, b = call("POST", "/api/public/dataset-items", item2)
s2, b2 = call("GET", f"/api/public/dataset-items?datasetName={DS}")
n = len(b2.get("data", [])) if isinstance(b2, dict) else None
eo = b2["data"][0]["expectedOutput"] if n else None
rec("M1d upsert same id (idempotent seed)", s, {"items_after": n, "expectedOutput_now": eo})
s, b = call("POST", "/api/public/dataset-items", dict(item, status="ARCHIVED"))
rec("M1e archive item via status", s, short(b, ["id", "status"]))
call("POST", "/api/public/dataset-items", dict(item, status="ACTIVE"))

# --- M2 dataset run linked to an externally produced trace (06a run -> trace) ---
trace_id = uuid.uuid4().hex
ev = {
    "batch": [
        {
            "id": uuid.uuid4().hex,
            "timestamp": "2026-11-04T19:00:00.000Z",
            "type": "trace-create",
            "body": {"id": trace_id, "name": "agent-run", "input": {"q": "x"}, "output": {"a": "30 days"}},
        }
    ]
}
s, b = call("POST", "/api/public/ingestion", ev)
rec("M2a ingest trace (stands in for 06a run trace)", s, short(b, ["successes", "errors"]))
run_name = f"{DS}-run-a"
body = {"runName": run_name, "runDescription": "agent_version x", "datasetItemId": item_id, "traceId": trace_id,
        "metadata": {"agent_version_id": "v1", "run_id": "r1"}}
s, b = call("POST", "/api/public/dataset-run-items", body)
rec("M2b create dataset-run-item with traceId", s, short(b, ["id", "datasetRunId", "datasetRunName", "traceId"]))
run_id = b.get("datasetRunId") if isinstance(b, dict) else None
time.sleep(8)
s, b = call("GET", f"/api/public/datasets/{DS}/runs")
names = [r.get("name") for r in b.get("data", [])] if isinstance(b, dict) else b
rec("M2c list dataset runs", s, names)
s, b = call("GET", f"/api/public/datasets/{DS}/runs/{run_name}")
rec("M2d get dataset run (items)", s, short(b, ["id", "name", "metadata", "datasetRunItems"]))
s, b = call("GET", f"/api/public/dataset-run-items?datasetId={b.get('datasetId') if isinstance(b, dict) else ''}&runName={run_name}")
rec("M2e list dataset-run-items", s, (len(b.get("data", [])) if isinstance(b, dict) else b))

# --- M3 scores ---
sc = {"traceId": trace_id, "name": "contains", "value": 1, "dataType": "NUMERIC", "comment": "ok",
      "metadata": {"outcome": "answered", "confidence": 0.7, "run_id": "r1", "passed": True}}
s, b = call("POST", "/api/public/scores", sc)
rec("M3a numeric score on trace + metadata", s, b)
s, b = call("POST", "/api/public/scores", {"traceId": trace_id, "name": "passed", "value": 1, "dataType": "BOOLEAN"})
rec("M3b boolean score", s, b)
s, b = call("POST", "/api/public/scores", {"traceId": trace_id, "name": "outcome", "value": "not_retrieved", "dataType": "CATEGORICAL"})
rec("M3c categorical score (outcome)", s, b)
if run_id:
    s, b = call("POST", "/api/public/scores", {"datasetRunId": run_id, "name": "run_pass_rate", "value": 0.8, "dataType": "NUMERIC"})
    rec("M3d run-level score (datasetRunId)", s, b)
fixed = f"{trace_id}-contains"
s, b = call("POST", "/api/public/scores", dict(sc, id=fixed, value=0))
s2, b2 = call("POST", "/api/public/scores", dict(sc, id=fixed, value=1))
rec("M3e score upsert by id", (s, s2), b2)
time.sleep(10)
s, b = call("GET", f"/api/public/v2/scores?traceId={trace_id}")
got = [(x.get("name"), x.get("value"), x.get("stringValue"), x.get("metadata")) for x in b.get("data", [])] if isinstance(b, dict) else b
rec("M3f read scores by trace (v2)", s, got)
if run_id:
    s, b = call("GET", f"/api/public/v2/scores?datasetRunId={run_id}")
    rec("M3g read scores by datasetRunId", s, (len(b.get("data", [])) if isinstance(b, dict) else b))
s, b = call("POST", "/api/public/score-configs", {"name": f"outcome-{TAG}", "dataType": "CATEGORICAL",
            "categories": [{"label": "answered", "value": 0}, {"label": "not_retrieved", "value": 1}]})
rec("M3h score-config (categorical)", s, short(b, ["id", "name", "dataType"]))

# --- M4 judge (LLM-as-a-judge) public surface ---
for path in ["/api/public/llm-connections", "/api/public/evaluators", "/api/public/eval-templates",
             "/api/public/evaluations", "/api/public/job-configurations"]:
    s, b = call("GET", path)
    rec(f"M4 GET {path}", s, (short(b, ["data", "meta", "message", "error"]) if isinstance(b, dict) else str(b)[:120]))

# --- M5 delete run (cleanup ability) ---
s, b = call("DELETE", f"/api/public/datasets/{DS}/runs/{run_name}")
rec("M5 delete dataset run", s, b)

json.dump(RESULTS, open("/out/measure.json", "w"), ensure_ascii=False, indent=1)
