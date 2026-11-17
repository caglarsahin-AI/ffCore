"""10c-2 D8 (FOLLOWUP-185) over HTTP: GET .../eval-runs/{id}/items and the typed exam summary.

Pages are `limit` (1-200, default 50) and `offset`; `total` counts the filtered items. Read mode
answers byte-for-byte as edit mode; another project's exam is the same 404.
"""

# ruff: noqa: F811 - the 09 fixtures are imported by name and used as parameters

import uuid

from tests.integration.test_09_api import (  # noqa: F401 - fixtures
    P,
    _scored_exam,
    _suite_and_run,
    member,
    project,
)


def _exam(pg, pid, passed: dict):
    suite_id, _ = _suite_and_run(pg, pid)
    version_id = pg.execute(
        "SELECT agent_version_id FROM eval_runs WHERE suite_id = %s", (suite_id,)
    ).fetchone()[0]
    return _scored_exam(pg, pid, suite_id, version_id, passed)


def test_10c2_items_page_filter_and_read_parity(pg, member, project):
    ev = _exam(pg, project, {f"q{i:02d}": i % 3 != 0 for i in range(7)})
    edit, read = member("analyst", "edit"), member("analyst", "read")
    url = f"{P.format(project)}/eval-runs/{ev}/items"
    first = edit.get(f"{url}?limit=2")
    assert first.status_code == 200, first.text
    body = first.json()
    assert (body["total"], body["limit"], body["offset"]) == (7, 2, 0)
    assert [r["item_id"] for r in body["data"]] == ["q00", "q03"]  # failed first
    assert body["data"][0]["passed"] is False and body["data"][0]["scores"][0]["name"] == "contains"
    rest = edit.get(f"{url}?limit=2&offset=2").json()
    assert [r["item_id"] for r in rest["data"]] == ["q06", "q01"]
    failed = edit.get(f"{url}?status=failed").json()
    assert failed["total"] == 3 and {r["item_id"] for r in failed["data"]} == {"q00", "q03", "q06"}
    assert read.get(f"{url}?limit=2").content == first.content


def test_10c2_items_rejects_bad_parameters(pg, member, project):
    ev = _exam(pg, project, {"q1": True})
    client = member("analyst")
    url = f"{P.format(project)}/eval-runs/{ev}/items"
    for query in ("limit=0", "limit=201", "offset=-1", "status=pending"):
        r = client.get(f"{url}?{query}")
        assert r.status_code == 422, (query, r.text)


def test_10c2_items_of_unknown_or_foreign_exam_is_404(
    pg,
    member,
    project,
    make_project,
    make_user,
    client_factory,
):
    ev = _exam(pg, project, {"q1": True})
    other = make_project()
    _, email = make_user(memberships={other: ("admin", "edit")})
    stranger = client_factory(email)
    assert stranger.get(f"{P.format(project)}/eval-runs/{ev}/items").status_code == 404
    unknown = member("analyst").get(f"{P.format(project)}/eval-runs/{uuid.uuid4()}/items")
    assert unknown.status_code == 404


def test_10c2_eval_run_summary_is_typed(pg, member, project):
    ev = _exam(pg, project, {"q1": True, "q2": False})
    out = member("analyst").get(f"{P.format(project)}/eval-runs/{ev}").json()
    assert out["summary"]["pass_rate"] == 0.5
    assert {"n", "scored", "not_run", "complete", "worst", "latency_ms"} <= set(out["summary"])
