"""Reviewer's negative probe for fix/03a-nonmember-404 (K-03ANM-0004). Copied into
backend/tests/integration/ of the reviewed worktree for one run, then removed.

Adds what the branch's own test does not: a malformed project id gets the same answer from a
stranger as from a member (no existence or membership signal), and the stranger's answer for a
missing project equals the one for a foreign project on a GET route that the branch lists."""

import uuid

import pytest

from tests.integration.test_03a_nonmember_404 import NOT_FOUND, ROUTES, _call, _fill


@pytest.fixture
def stranger(make_user, make_project, client_factory):
    _, email = make_user(memberships={make_project(): ("admin", "edit")})
    return client_factory(email)


@pytest.fixture
def member(make_user, make_project, client_factory):
    target = make_project()
    _, email = make_user(memberships={target: ("admin", "edit")})
    return client_factory(email), target


GETS = [(m, p) for m, p in ROUTES if m == "get" and "{project_id}" in p][:6]


@pytest.mark.parametrize(("method", "path"), GETS, ids=[f"{m} {p}" for m, p in GETS])
def test_rev_03anm_neg_1_malformed_id_same_for_stranger_and_member(method, path, stranger, member):
    client_member, _ = member
    bad = path.replace("{project_id}", "not-a-uuid")
    stranger_answer = _call(stranger, method, bad)
    member_answer = _call(client_member, method, bad)
    assert stranger_answer.status_code == member_answer.status_code, (
        stranger_answer.status_code,
        member_answer.status_code,
    )
    assert stranger_answer.json() == member_answer.json()


@pytest.mark.parametrize(("method", "path"), GETS, ids=[f"{m} {p}" for m, p in GETS])
def test_rev_03anm_neg_2_foreign_and_missing_are_byte_equal(method, path, stranger, make_project):
    foreign = make_project()
    a = _call(stranger, method, _fill(path, foreign))
    b = _call(stranger, method, _fill(path, uuid.uuid4()))
    assert (a.status_code, a.content) == (b.status_code, b.content)
    assert (a.status_code, a.json()) == (404, NOT_FOUND)
