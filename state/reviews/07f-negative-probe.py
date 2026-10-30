"""Reviewer's negative probe for fix/07-followups (K-07F-0005). Copied into backend/tests/integration/
for one run with FFCORE_TEST_HOOKS off, then removed. An anonymous caller must learn nothing from the
sweep hook: its answer equals an unknown path's answer (404, same body)."""

import pytest

from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures

from tests.integration.test_07f_followups import SWEEP  # noqa: F401 - the route under test


def test_rev_07f_neg_1_anonymous_sees_the_same_404_as_an_unknown_path(client_factory, settings):
    assert settings.ffcore_test_hooks is False
    anonymous = client_factory()
    unknown = anonymous.post("/api/v1/internal/approvals/no-such-path")
    hook = anonymous.post(SWEEP)
    assert (hook.status_code, hook.json()) == (unknown.status_code, unknown.json()) == (404, unknown.json())
