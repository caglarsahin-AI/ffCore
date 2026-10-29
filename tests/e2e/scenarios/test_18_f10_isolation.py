"""F10 (project isolation and audit trail), plan/18: a member of project B sees none of
project A's resources, by listing or by guessing an id; data/samples/projects/projects.json."""

import pytest


@pytest.fixture(scope="module")
def pair(seed, login):
    iso = seed["isolation"]
    owner = login(iso["target_project"], "admin", "edit")
    outsider = login(iso["viewer_project"], "admin", "edit")
    return iso, owner, owner.project_id(iso["target_project"]), outsider


def test_18_f10_4_direct_ids_are_404(pair):
    iso, owner, a_pid, outsider = pair
    paths = [
        f"/api/v1/projects/{a_pid}/knowledge-bases",
        f"/api/v1/projects/{a_pid}/agents",
        f"/api/v1/projects/{a_pid}/runs",
    ]
    for path in paths:
        assert owner.get(path).status_code == 200, path  # control: the resource exists
        r = outsider.get(path)
        assert r.status_code == iso["expected_status"], (path, r.status_code, r.text[:200])
        assert a_pid not in r.text  # nothing about A in the error body either


def test_18_f10_5_listing_does_not_leak(pair):
    iso, owner, a_pid, outsider = pair
    b_pid = outsider.project_id(iso["viewer_project"])
    a_agents = {a["id"] for a in owner.get(f"/api/v1/projects/{a_pid}/agents").json()["items"]}
    b_agents = {a["id"] for a in outsider.get(f"/api/v1/projects/{b_pid}/agents").json()["items"]}
    assert a_agents and not (a_agents & b_agents)


def test_18_f10_6_run_and_tool_call_of_a(pair):
    """B cannot read A's run detail or events, nor have A's tool (mcp-sql) called for it."""
    pytest.skip("NOT_RUN: tool registry is 05a; run on A's agent needs 13b seed of tools")


def test_18_f10_7_trace_chain_and_deleted_source():
    """run → source document → LiteLLM call id → Langfuse trace; after the document is deleted
    the run_events source reference stays, marked deleted, with no content."""
    pytest.skip("NOT_RUN: document delete marking in run_events is checked once 06a merges")
