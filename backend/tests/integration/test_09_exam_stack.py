"""09 acceptance on the scenario stack: the 33-item set through a real exam (fake-llm).

Needs the test stack with the plan/18 overlay, `make seed` and `make seed-eval PROJECT=hastane-a`
(state/pr/09.md "Komutlar"); run with RUN_EVAL_STACK=1 and E2E_PASSWORD in the environment.
Without the flag every test here is NOT_RUN (skipped with that reason), never silently passed.
The background worker's advancer does the work; the test only starts, waits and reads.
"""

import os
import time

import anyio
import httpx
import pytest

from ffcore.core.config import get_settings
from ffcore.evaluation.langfuse_api import LangfuseApi

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EVAL_STACK") != "1",
    reason="NOT_RUN: set RUN_EVAL_STACK=1 (scenario stack + make seed + make seed-eval)",
)

BACKEND = os.environ.get("E2E_BACKEND_URL", "http://backend:8000")
ANALYST = "hastane-a-analyst-edit@example.test"
ADMIN_READ = "hastane-a-admin-read@example.test"
WAIT_S = float(os.environ.get("EVAL_STACK_WAIT_S", "900"))


def _login(email: str) -> httpx.Client:
    c = httpx.Client(base_url=BACKEND, timeout=60)
    r = c.post("/api/v1/auth/login", json={"email": email, "password": os.environ["E2E_PASSWORD"]})
    assert r.status_code == 200, f"login {email}: {r.status_code} (is make seed loaded?)"
    c.headers["cookie"] = f"ffcore_session={r.cookies['ffcore_session']}"
    c.me = r.json()  # type: ignore[attr-defined]
    return c


def _project(c) -> str:
    return next(m["project_id"] for m in c.me["memberships"] if m["project_key"] == "hastane-a")


def _suite(c, pid, key):
    items = c.get(f"/api/v1/projects/{pid}/eval-suites").json()["items"]
    return next(s for s in items if s["key"] == key)


def _published_version(c, pid, agent_key):
    agents = c.get(f"/api/v1/projects/{pid}/agents").json()["items"]
    agent = next(a for a in agents if a["key"] == agent_key)
    versions = c.get(f"/api/v1/projects/{pid}/agents/{agent['id']}/versions").json()["items"]
    return next(v for v in versions if v["id"] == agent["current_version_id"])


def _wait(c, pid, eval_run_id) -> dict:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        out = c.get(f"/api/v1/projects/{pid}/eval-runs/{eval_run_id}").json()
        if out["status"] in ("completed", "failed", "cancelled"):
            return out
        time.sleep(3)
    pytest.fail(f"exam {eval_run_id} not finished in {WAIT_S} s")


@pytest.fixture(scope="module")
def exam():
    c = _login(ANALYST)
    pid = _project(c)
    suite = _suite(c, pid, "sozlesme-33")
    version = _published_version(c, pid, "sozlesme-asistani")
    started = time.monotonic()
    r = c.post(
        f"/api/v1/projects/{pid}/eval-suites/{suite['id']}/run",
        params={"agent_version_id": version["id"]},
    )
    assert r.status_code == 202, r.text[:300]
    out = _wait(c, pid, r.json()["id"])
    out["_seconds"] = round(time.monotonic() - started, 1)
    print(f"exam {out['id']} {out['status']} in {out['_seconds']} s: {out['summary']}")
    return c, pid, suite, out


def test_09_1_suite_runs_33_items(exam):
    _, _, _, out = exam
    assert out["status"] == "completed", out.get("error_code")
    assert out["items"] == 33 and out["scored"] == 33
    s = out["summary"]
    assert s["n"] == 33 and isinstance(s["passed"], bool) and 0 <= s["pass_rate"] <= 1
    assert s["warm_cache"] is True and s["warmup_ms"] is not None


def test_09_2a_summary_has_outcome_and_style_distribution(exam):
    s = exam[3]["summary"]
    assert sum(s["outcomes"].values()) > 0
    assert {"dogrudan", "dolayli", "alan_ici_cevapsiz", "alan_disi_cevapsiz"} <= set(s["styles"])


def test_09_langfuse_dataset_run_links_every_item(exam):
    _, _, suite, out = exam
    api = LangfuseApi(get_settings())
    # Langfuse 3.120 reads dataset run items back with a lag (measured 31/33 right after the
    # exam ended, 33/33 seconds later; state/pr/09.md L17): poll, bounded.
    deadline = time.monotonic() + 60
    while True:
        items = anyio.run(api.run_items, suite["langfuse_dataset_name"], out["langfuse_run_name"])
        if len({i.item_id for i in items}) == 33 or time.monotonic() > deadline:
            break
        time.sleep(3)
    assert len({i.item_id for i in items}) == 33
    scores = anyio.run(api.trace_scores, items[0].trace_id, ["outcome", "passed", "contains"])
    assert {"outcome", "passed"} <= {s["name"] for s in scores}


def test_09_g6_item_runs_are_background_test_runs(exam):
    c, pid, _, _ = exam
    runs = c.get(f"/api/v1/projects/{pid}/runs", params={"channel": "test"}).json()["items"]
    assert len(runs) >= 33


def test_09_read_only_member_cannot_start(exam):
    _, pid, suite, _ = exam
    c = _login(ADMIN_READ)
    version = _published_version(c, pid, "sozlesme-asistani")
    r = c.post(
        f"/api/v1/projects/{pid}/eval-suites/{suite['id']}/run",
        params={"agent_version_id": version["id"]},
    )
    assert r.status_code == 403


def test_09_dataset_name_not_in_project():
    c = _login(ANALYST)
    pid = _project(c)
    r = c.post(
        f"/api/v1/projects/{pid}/eval-suites",
        json={
            "key": "foreign",
            "name": "x",
            "langfuse_dataset_name": "klinik-b.secret",
            "scorers": [{"name": "contains"}],
        },
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "dataset_name_not_in_project"


def test_09_stream_ends_with_done(exam):
    c, pid, _, out = exam
    with c.stream("GET", f"/api/v1/projects/{pid}/eval-runs/{out['id']}/stream") as r:
        assert r.status_code == 200
        text = "".join(r.iter_text())
    assert "event: done" in text and '"status": "completed"' in text


def test_09_2c_declined_answer_text_kept(exam):
    c, pid, _, out = exam
    declined = [w for w in out["summary"]["worst"] if w["outcome"] == "declined"]
    runs = c.get(f"/api/v1/projects/{pid}/runs", params={"channel": "test"}).json()["items"]
    labelled = [r for r in runs if r.get("outcome_label") == "declined"]
    assert out["summary"]["outcomes"]["declined"] >= 1 or not declined
    for r in labelled:
        detail = c.get(f"/api/v1/projects/{pid}/runs/{r['id']}").json()
        assert detail["output"], "a declined answer keeps its text"
