"""Reviewer probe 19 (paycoreLLM side): scripts/ffcore_stage_raw.py on a synthetic PRSIM issue and
a Confluence page. Synthetic data only. Run in paycore-llm-test with /pc (paycoreLLM tree)."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/pc/scripts")
os.environ.setdefault("JIRA_URL", "https://jira.example.test")
import ffcore_stage_raw as s  # noqa: E402

NAMES = ["Ali Veli", "jdoe", "zeynep.k", "ali.veli@example.org", "Mehmet Yilmaz", "Ayse Kaya"]
issue = {
    "key": "PRSIM-1",
    "fields": {
        "summary": "Access request for the build server",
        "issuetype": {"name": "Task"}, "status": {"name": "Done"}, "resolution": {"name": "Fixed"},
        "description": "Please grant access.\n[~jdoe] and @zeynep.k are watching. Contact ali.veli@example.org.\n"
                       "Saygılarımla\nAli Veli\nIT Operations\n+90 532 256 60 38\n\nThen next paragraph stays.",
        "assignee": {"displayName": "Mehmet Yilmaz", "name": "myilmaz"},
        "reporter": {"displayName": "Ali Veli", "name": "jdoe"},
        "creator": {"displayName": "Ayse Kaya"},
        "watches": {"watchers": [{"displayName": "Zeynep K"}]},
        "comment": {"comments": [{"author": {"displayName": "Mehmet Yilmaz"}, "body": "Done, @jdoe.\n--\nMehmet\nIT"}]},
        "updated": "2026-01-02T03:04:05.000+0300",
    },
}
page = {"id": "77", "title": "Policy", "space": {"key": "DEMO"}, "ancestors": [],
        "body": {"storage": {"value": "<p>Owner: see <ac:link><ri:user ri:userkey=\"u1\"/></ac:link> and @ali.veli</p>"}},
        "version": {"when": "2026-01-01T00:00:00Z", "by": {"displayName": "Ali Veli"}},
        "history": {"createdBy": {"displayName": "Ayse Kaya"}, "createdDate": "2025-01-01"}}

with tempfile.TemporaryDirectory() as t:
    raw, out = Path(t) / "raw", Path(t) / "out"
    (raw / "jira/PRSIM").mkdir(parents=True); (raw / "confluence/DEMO").mkdir(parents=True)
    (raw / "jira/PRSIM/PRSIM-1.json").write_text(json.dumps(issue))
    (raw / "confluence/DEMO/77.json").write_text(json.dumps(page))
    try:
        s.stage(raw, out, ["jira:PRSIM"], limit=None, attachments=False)
        print("FAIL PRSIM staged without the flag")
    except s.StagingError as e:
        print("PASS without flag:", e.code)
    print("counts", dict(s.stage(raw, out, ["jira:PRSIM", "confluence:DEMO"], limit=None, attachments=False, accept_personnel_data=True)))
    bad = 0
    for p in sorted(out.rglob("*")):
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            hits = [n for n in NAMES if n in text]
            print(("LEAK " if hits else "ok   ") + str(p.relative_to(out)), hits)
            bad += bool(hits)
    print("--- PRSIM-1.md ---"); print((out / "jira/PRSIM/PRSIM-1/PRSIM-1.md").read_text(encoding="utf-8"))
    print("--- meta ---"); print((out / "jira/PRSIM/PRSIM-1/PRSIM-1.md.meta.json").read_text(encoding="utf-8"))
    inside = Path(t) / "raw" / "x"
    try:
        s.stage(raw, inside, ["confluence:DEMO"], limit=None, attachments=False)
        print("FAIL out inside raw accepted")
    except SystemExit as e:
        print("PASS out inside raw refused:", e)
    print("leaks:", bad)
