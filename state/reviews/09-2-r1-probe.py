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

PW = os.environ["E2E_PASSWORD"]
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


editor = Api("hastane-a-analyst-edit@example.test", PW)
admin = Api("hastane-a-admin-edit@example.test", PW)
superadmin = Api(os.environ["E2E_ADMIN_EMAIL"], os.environ["E2E_ADMIN_PASSWORD"])
pid = editor.project_id("hastane-a")
P = f"/api/v1/projects/{pid}"
agent = next(a for a in editor.get(f"{P}/agents").json()["items"] if a["key"] == "sozlesme-asistani")
versions = editor.get(f"{P}/agents/{agent['id']}/versions").json()["items"]
current = next(v for v in versions if v["id"] == agent["current_version_id"])
print(f"G0 agent={agent['key']} current_version={current['version']} versions={[v['version'] for v in versions]}")

# --- publish gate ---------------------------------------------------------------------------
r = editor.post(f"{P}/eval-suites", json={"key": "rv-gate", "name": "Reviewer gate", "agent_id": agent["id"],
                                           "scorers": [{"name": "contains"}]})
suite = show("G1 bound suite create", r)
pub = f"{P}/agents/{agent['id']}/publish"
v = current["version"]
show("G2 publish, no exam (expect 409 eval_gate_failed)", editor.post(pub, json={"version": v}))
show("G3 editor force (expect 403)", editor.post(pub, json={"version": v, "force": True, "force_reason": "rv"}))
show("G4 admin force, no reason (expect 422)", admin.post(pub, json={"version": v, "force": True}))
show("G5 reason without force (expect 422)", admin.post(pub, json={"version": v, "force_reason": "rv"}))
show("G6 admin force, blank reason (expect 422)", admin.post(pub, json={"version": v, "force": True, "force_reason": "   "}))
show("G7 admin force + reason (expect 200)", admin.post(pub, json={"version": v, "force": True, "force_reason": "reviewer probe 09-2"}))
for action in ("eval_gate_forced", "publish_agent"):
    rows = superadmin.get("/api/v1/audit", params={"action": action, "limit": 3}).json()
    rows = rows.get("items", rows.get("data", rows)) if isinstance(rows, dict) else rows
    row = rows[0] if rows else {}
    print(f"G8 audit {action}: n={len(rows)} keys={sorted(row)} after={json.dumps(row.get('after'), ensure_ascii=False)[:400]}")
older = [x["version"] for x in versions if x["version"] != v and x.get("published_at")]
if older:
    show(f"G9 rollback to {older[0]} with the failing gate (expect 200, ungated)",
         admin.post(f"{P}/agents/{agent['id']}/rollback", json={"version": older[0]}))
    admin.post(pub, json={"version": v, "force": True, "force_reason": "reviewer probe restore"})
else:
    print("G9 rollback: NOT_RUN (no earlier published version in the seed)")
editor.http.delete(f"{P}/eval-suites/{suite.get('id')}")

# --- from-run -------------------------------------------------------------------------------
run = editor.settle(pid, editor.start_run(pid, "sozlesme-asistani", QUESTION))
print(f"F0 run {run.id} events={run.names()[-3:]}")
s33 = next(s for s in editor.get(f"{P}/eval-suites").json()["items"] if s["key"] == "sozlesme-33")
url = f"{P}/eval-suites/{s33['id']}/items/from-run/{run.id}"
body = {"expected": {"must_contain": ["fesih"]}, "style": "dogrudan"}
out1 = show("F1 from-run (expect 201)", editor.post(url, json=body))
out2 = show("F2 same run again", editor.post(url, json=body))
show("F3 another member reads the editor's run (admin-read)", Api("hastane-a-admin-read@example.test", PW).post(url, json=body))
print(f"F4 item ids: {out1.get('item_id')} / {out2.get('item_id') if isinstance(out2, dict) else None}")
with open("/tmp/probe092-item.json", "w", encoding="utf-8") as f:
    json.dump({"dataset": out1.get("dataset"), "item_id": out1.get("item_id")}, f)
for action in ("eval_item_from_run",):
    rows = superadmin.get("/api/v1/audit", params={"action": action, "limit": 2}).json()
    rows = rows.get("items", rows.get("data", rows)) if isinstance(rows, dict) else rows
    blob = json.dumps(rows, ensure_ascii=False)
    print(f"F5 audit {action}: n={len(rows)} raw_pii_in_audit={[x for x in (NAME, TC, MAIL) if x in blob]}")
