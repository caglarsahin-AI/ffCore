"""Reviewer probe for 09-2 r2 (4e2fcad), over HTTP in the tools container after `make seed`
(E2E_PASSWORD from the same gate run). Synthetic values only.

S: a one-item suite bound to the agent (item from a run), an exam on a draft, then:
   edit the draft -> publish 409 stale_exam; new exam, change the suite threshold -> 409
   stale_suite; blank force_reason -> 422; version record after a forced publish.
M: from-run response `masking` is `regex` on a stack with GUARDRAIL_EGRESS_NER=false; the
   expected answer is masked too.
"""

import json
import os
import time

from tests.e2e.scenarios.conftest import Api

PW = os.environ["E2E_PASSWORD"]
TC, MAIL = "10000000146", "ayse.yilmaz@ornek.com"


def show(tag, r):
    try:
        body = r.json()
    except ValueError:
        body = r.text[:200]
    err = body.get("error", body) if isinstance(body, dict) else body
    print(f"{tag}: {r.status_code} {json.dumps(err, ensure_ascii=False)[:280]}")
    return body


def wait(api, P, ev_id, limit=300):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        out = api.get(f"{P}/eval-runs/{ev_id}").json()
        if out["status"] in ("completed", "failed", "cancelled"):
            return out
        time.sleep(3)
    return {"status": "timeout"}


editor = Api("hastane-a-analyst-edit@example.test", PW)
admin = Api("hastane-a-admin-edit@example.test", PW)
pid = editor.project_id("hastane-a")
P = f"/api/v1/projects/{pid}"
agent = next(a for a in editor.get(f"{P}/agents").json()["items"] if a["key"] == "sozlesme-asistani")
A = f"{P}/agents/{agent['id']}"

# an item from a run, into a fresh suite bound to the agent
run = editor.settle(pid, editor.start_run(pid, "sozlesme-asistani", f"TC {TC} ve {MAIL} için sözleşme fesih süresi nedir?"))
suite = show("S1 suite", editor.post(f"{P}/eval-suites", json={"key": "rv2-gate", "name": "Reviewer r2", "agent_id": agent["id"],
                                                               "scorers": [{"name": "contains"}]}))
S = f"{P}/eval-suites/{suite['id']}"
fr = show("M1 from-run", editor.post(f"{S}/items/from-run/{run.id}",
                                     json={"expected": {"answer": f"{MAIL} adresine yazın", "must_contain": ["fesih"]}, "style": "dogrudan"}))
print(f"M2 masking field: {fr.get('masking') if isinstance(fr, dict) else None}")

# a draft, its exam
draft = show("S2 draft", editor.post(f"{A}/versions", json={}))
ev = show("S3 exam on draft", editor.post(f"{S}/run", params={"agent_version_id": draft["id"]}))
out = wait(editor, P, ev["id"])
print(f"S4 exam status={out['status']} passed={(out.get('summary') or {}).get('passed')} complete={(out.get('summary') or {}).get('complete')}")
cfg = out.get("config") or {}
print(f"S5 exam config has definition_sha256: {'definition_sha256' in json.dumps(cfg)}")

# edit the draft -> stale_exam
d = editor.get(f"{A}/versions/{draft['version']}").json()["definition"]
d["system_prompt"] = (d.get("system_prompt") or "") + " (rv)"
show("S6 edit draft", editor.http.put(f"{A}/versions/{draft['version']}", json={"definition": d}))
show("S7 publish edited draft (expect 409 stale_exam)", editor.post(f"{A}/publish", json={"version": draft["version"]}))

# fresh exam on the edited draft, then change the suite threshold -> stale_suite
ev2 = show("S8 exam again", editor.post(f"{S}/run", params={"agent_version_id": draft["id"]}))
out2 = wait(editor, P, ev2["id"])
print(f"S9 exam2 status={out2['status']} passed={(out2.get('summary') or {}).get('passed')}")
show("S10 publish before suite change (reason after the exam)", editor.post(f"{A}/publish", json={"version": draft["version"]}))
show("S11 change suite threshold", editor.http.patch(S, json={"pass_threshold": 0.5}))
show("S12 publish after suite change (expect 409 stale_suite)", editor.post(f"{A}/publish", json={"version": draft["version"]}))

# force rules and the version record
show("S13 admin force, blank reason (expect 422)", admin.post(f"{A}/publish", json={"version": draft["version"], "force": True, "force_reason": "   "}))
show("S14 admin force with reason", admin.post(f"{A}/publish", json={"version": draft["version"], "force": True, "force_reason": "reviewer probe 09-2 r2"}))
v = editor.get(f"{A}/versions/{draft['version']}").json()
print(f"S15 version record: published={bool(v.get('published_at'))} eval_run_id={v.get('eval_run_id')}")
show("S16 edit a published version (expect 409)", editor.http.put(f"{A}/versions/{draft['version']}", json={"definition": d}))
editor.http.delete(S)
