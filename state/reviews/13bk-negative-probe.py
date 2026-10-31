"""Reviewer's negative probe for feat/13bk-ttl-negative (K-13BK-0003). Copied into tests/e2e/negative/
for one run on the scenario stack (RUN_E2E_SCENARIOS=1), then removed. The sweep hook must not act on a
`now` in the far past, and must refuse a `now` it cannot trust (no time zone, unparseable)."""

import httpx

from tests.e2e.negative.test_13b_negative import BACKEND_URL, SWEEP, _service


def _post(**params):
    return httpx.post(BACKEND_URL + SWEEP, params=params, headers=_service(), timeout=60)


def test_rev_13bk_neg_1_sweep_in_the_far_past_expires_nothing():
    r = _post(now="2000-01-01T00:00:00+00:00")
    assert r.status_code == 200, r.text
    assert r.json()["expired"] == [], r.json()


def test_rev_13bk_neg_2_now_without_time_zone_is_refused_with_a_code():
    r = _post(now="2030-01-01T00:00:00")
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "now_without_timezone", r.json()


def test_rev_13bk_neg_3_unparseable_now_is_refused():
    r = _post(now="not-a-date")
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "validation_error", r.json()
