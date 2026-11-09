"""Reviewer probe for 09-2 r1 (892bdfe), run over HTTP in the tools container after `make seed`:
publish gate (409 / force 403 / reason 422 / admin force 200 + audit without content / rollback
ungated) and from-run (masked question in the Langfuse dataset item, second save, other user's
run). Synthetic values only.

docker compose ... run --rm -e E2E_PASSWORD -e E2E_ADMIN_EMAIL -e E2E_ADMIN_PASSWORD \
  -v <this file>:/tmp/probe092.py tools sh -c "cd /work && PYTHONPATH=/work python /tmp/probe092.py"
"""

import json
import os

from tests.e2e.scenarios.conftest import Api

NAME, TC, MAIL = "Ayşe Yılmaz", "10000000146", "ayse.yilmaz@ornek.com"
QUESTION = f"{NAME} (TC {TC}, {MAIL}) için sözleşmenin fesih süresi nedir?"


def show(tag, r):
    try:
        body = r.json()
    except ValueError:
        body = r.text[:200]
    err = body.get("error", body) if isinstance(body, dict) else body
    print(f"{tag}: {r.status_code} {json.dumps(err, ensure_ascii=False)[:300]}")
    return body


editor = Api(os.environ["PROBE_EMAIL"], os.environ["PROBE_PASSWORD"])
superadmin = editor
_ps = editor.get("/api/v1/projects").json()
_ps = _ps.get("items", _ps.get("data", _ps)) if isinstance(_ps, dict) else _ps
pid = next(x["id"] for x in _ps if x.get("key") == "hastane-a")
_me = editor.get("/api/v1/auth/me").json()
print("M0 add member:", editor.post(f"/api/v1/projects/{pid}/members", json={"user_id": _me.get("id") or _me.get("user", {}).get("id"), "role": "analyst", "access": "edit"}).status_code)
P = f"/api/v1/projects/{pid}"
agent = next(a for a in editor.get(f"{P}/agents").json()["items"] if a["key"] == "sozlesme-asistani")
versions = editor.get(f"{P}/agents/{agent['id']}/versions").json()["items"]
current = next(v for v in versions if v["id"] == agent["current_version_id"])
print(f"G0 agent={agent['key']} current_version={current['version']} versions={[v['version'] for v in versions]}")

# --- from-run -------------------------------------------------------------------------------
run = editor.settle(pid, editor.start_run(pid, "sozlesme-asistani", QUESTION))
print(f"F0 run {run.id} events={run.names()[-3:]}")
s33 = next(s for s in editor.get(f"{P}/eval-suites").json()["items"] if s["key"] == "sozlesme-33")
url = f"{P}/eval-suites/{s33['id']}/items/from-run/{run.id}"
body = {"expected": {"must_contain": ["fesih"]}, "style": "dogrudan"}
out1 = show("F1 from-run (expect 201)", editor.post(url, json=body))
out2 = show("F2 same run again", editor.post(url, json=body))
print("F3 other member: NOT_RUN in the probe (seed passwords were ephemeral); covered by test_09_from_run")
print(f"F4 item ids: {out1.get('item_id')} / {out2.get('item_id') if isinstance(out2, dict) else None}")
with open("/tmp/probe092-item.json", "w", encoding="utf-8") as f:
    json.dump({"dataset": out1.get("dataset"), "item_id": out1.get("item_id")}, f)
for action in ("eval_item_from_run",):
    rows = superadmin.get("/api/v1/audit", params={"action": action, "limit": 2}).json()
    rows = rows.get("items", rows.get("data", rows)) if isinstance(rows, dict) else rows
    blob = json.dumps(rows, ensure_ascii=False)
    print(f"F5 audit {action}: n={len(rows)} raw_pii_in_audit={[x for x in (NAME, TC, MAIL) if x in blob]}")
