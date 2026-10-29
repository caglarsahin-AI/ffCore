"""07: who may decide an approval, and the tool part of an action name."""

import pytest

from ffcore.core.auth import SERVICE_ACTOR, Actor, Grant
from ffcore.services.approvals import may_decide, tool_key

USER = Actor(actor_type="user", actor_id="u1", project_id="p1")


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("mcp-sql__run_sql", "mcp-sql"),
        ("ticket-desk__create__ticket", "ticket-desk"),
        ("run_sql", None),
        ("__run_sql", None),
    ],
)
def test_07_tool_key(action, expected):
    assert tool_key(action) == expected


@pytest.mark.parametrize(
    ("role", "access", "assigned", "expected"),
    [
        ("admin", "edit", "admin", True),
        ("developer", "edit", "analyst", True),
        ("analyst", "edit", "analyst", True),
        ("analyst", "edit", "developer", False),
        ("analyst", "read", "analyst", False),
        ("user", "edit", "analyst", False),
    ],
)
def test_07_may_decide_role_and_access(role, access, assigned, expected):
    assert may_decide(USER, Grant(role, access, False), assigned) is expected


def test_07_may_decide_needs_console_session():
    admin = Grant("admin", "edit", True)
    via_service = Actor(actor_type="user", actor_id="u1", project_id="p1", via_service=True)
    api_key = Actor(actor_type="api_key", actor_id="k1", scopes=frozenset({"impersonate"}))
    assert may_decide(via_service, admin, "analyst") is False
    assert may_decide(api_key, admin, "analyst") is False
    assert may_decide(SERVICE_ACTOR, admin, "analyst") is False
    assert may_decide(USER, None, "analyst") is False
