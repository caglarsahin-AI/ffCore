"""FOLLOWUP-197 over HTTP (R-10C2-0008 MINOR-1 `ozet-skaler-500`): a stored exam summary that is a
bare number or `true` reads as `summary: null` (200) on the exam and on the suite's exam list,
like any other summary that does not fit the contract (10c-2 r1 NOTE-2), never a 500.
"""

# ruff: noqa: F811 - the 09 fixtures are imported by name and used as parameters

import pytest

from tests.integration.test_09_api import P, member, project  # noqa: F401 - fixtures
from tests.integration.test_10c2_eval_items_int import _exam


@pytest.mark.parametrize("stored", ["7", "true"])
def test_10c3_0_scalar_summary_reads_as_null_not_500(pg, member, project, stored):
    ev = _exam(pg, project, {"q1": True})
    pg.execute("UPDATE eval_runs SET summary = %s::jsonb WHERE id = %s", (stored, ev))
    suite_id = pg.execute("SELECT suite_id FROM eval_runs WHERE id = %s", (ev,)).fetchone()[0]
    client = member("analyst")
    detail = client.get(f"{P.format(project)}/eval-runs/{ev}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["summary"] is None
    runs = client.get(f"{P.format(project)}/eval-suites/{suite_id}/runs")
    assert runs.status_code == 200, runs.text
    assert next(r for r in runs.json()["items"] if r["id"] == str(ev))["summary"] is None
