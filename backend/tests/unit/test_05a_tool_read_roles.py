"""FOLLOWUP-100 (decision A, K-10bp2-0003): analysts read tools and actions, only admins change them.

Route-level scan of the role each tool route requires; the behaviour (403/200, masked secrets)
is proven against the real app in tests/integration/test_05a_tools_api.py.
"""

from ffcore.core.auth import RoleRequirement
from ffcore.main import app
from tests.unit.test_03a_write_flag import api_routes

# The nested router keeps its own path; /api/v1 is the parent's prefix (03a scan note).
PREFIX = "/projects/{project_id}/tools"


def _requirement(route) -> RoleRequirement:
    found = []

    def walk(dependant):
        for dep in dependant.dependencies:
            if isinstance(dep.call, RoleRequirement):
                found.append(dep.call)
            walk(dep)

    walk(route.dependant)
    assert len(found) == 1, route.path
    return found[0]


def _tool_routes():
    routes = [r for r in api_routes(app.routes) if r.path.startswith(PREFIX)]
    assert routes, "tool routes not found"
    return routes


def test_05a_tool_reads_need_analyst():
    reads = [r for r in _tool_routes() if r.methods == {"GET"}]
    assert {r.name for r in reads} == {"list_tools", "get_tool"}
    for route in reads:
        need = _requirement(route)
        assert (need.min_role, need.write) == ("analyst", False), route.path


def test_05a_tool_changes_stay_admin_with_edit():
    for route in _tool_routes():
        if route.methods == {"GET"} or route.name == "sql_context":
            continue
        need = _requirement(route)
        assert (need.min_role, need.write) == ("admin", True), (route.name, route.path)
