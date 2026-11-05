"""09 madde 1, ek: v2 scores filtreleri ve SDK run_experiment (OSS)."""

import base64
import json
import os
import urllib.request
import uuid

HOST = "http://langfuse-web:3000"
PK = os.environ["LANGFUSE_INIT_PROJECT_PUBLIC_KEY"]
SK = os.environ["LANGFUSE_INIT_PROJECT_SECRET_KEY"]
AUTH = "Basic " + base64.b64encode(f"{PK}:{SK}".encode()).decode()


def get(path):
    req = urllib.request.Request(HOST + path)
    req.add_header("Authorization", AUTH)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode())


def out(name, val):
    print(json.dumps({"check": name, "note": val}, ensure_ascii=False, default=str), flush=True)


s, b = get(f"/api/public/v2/scores?traceId={uuid.uuid4().hex}")
out("F1 v2 scores traceId=<unknown> (filter applies?)", (s, b["meta"]))
s, b = get("/api/public/v2/scores?limit=100")
out("F2 v2 scores total", b["meta"].get("totalItems"))
s, b = get(f"/api/public/scores?traceId={uuid.uuid4().hex}")
out("F3 v1 scores traceId=<unknown>", b.get("meta") if isinstance(b, dict) else b)

from langfuse import Evaluation, Langfuse  # noqa: E402

lf = Langfuse(public_key=PK, secret_key=SK, host=HOST)
name = f"m09sdk-{uuid.uuid4().hex[:6]}"
lf.create_dataset(name=name, metadata={"suite": "sdk"})
for i in range(2):
    lf.create_dataset_item(dataset_name=name, id=f"{name}-{i}", input={"message": f"q{i}"},
                           expected_output={"must_contain": ["a"]}, metadata={"style": "dogrudan"})
ds = lf.get_dataset(name)


def task(*, item, **kwargs):
    return "a answer"


def contains(*, input, output, expected_output, **kwargs):
    ok = all(x in output for x in expected_output["must_contain"])
    return Evaluation(name="contains", value=1.0 if ok else 0.0, metadata={"outcome": "answered"})


res = ds.run_experiment(name="exp", run_name=f"{name}-run", task=task, evaluators=[contains], max_concurrency=1)
lf.flush()
out("S1 run_experiment items", [(r.item.id if hasattr(r.item, "id") else None, r.trace_id,
                                 [(e.name, e.value) for e in r.evaluations]) for r in res.item_results])
out("S2 run_experiment dataset_run_id", getattr(res, "dataset_run_id", None))
import time  # noqa: E402

time.sleep(10)
s, b = get(f"/api/public/datasets/{name}/runs/{name}-run")
out("S3 run via REST", {"items": len(b.get("datasetRunItems", [])), "metadata": b.get("metadata")})
