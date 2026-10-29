"""05a: the compose services mcp-search and mcp-sql themselves (the documented test stack starts
them: `--profile test --profile qdrant up -d --wait`). Discovery of both through the real
containers, and run_sql on the stack's demo database after `seed-sql-demo` (idempotent).

The full search chain with ACLs runs in test_05a_search (real backend over HTTP); here the
containers, their environment and the compose wiring are under test.
"""

import asyncio
from pathlib import Path

import pytest

from ffcore import cli
from ffcore.core.config import get_settings
from ffcore.services import mcp_client
from ffcore.services.mcp_client import Caller, ToolTarget

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "data" / "samples" / "schema"
SERVICES = {"mcp-search": "http://mcp-search:8000/mcp", "mcp-sql": "http://mcp-sql:8000/mcp"}
CALLER = Caller(user_id="live-test-user", project_id="00000000-0000-0000-0000-000000000000")


@pytest.fixture(scope="module")
def settings():
    return get_settings()


def target(key):
    return ToolTarget(key=key, endpoint_url=SERVICES[key], auth_type="forward_user", auth={})


@pytest.mark.parametrize(
    ("key", "actions"),
    [("mcp-search", {"search_documents"}), ("mcp-sql", {"get_schema", "run_sql"})],
)
def test_05a_live_discovery(settings, key, actions):
    found = asyncio.run(mcp_client.discover(target(key), settings, caller=CALLER))
    assert {a.name for a in found} == actions


def test_05a_live_token_for_another_tool_refused(settings):
    # A token cut for mcp-search is refused by the mcp-sql container (aud list, S3).
    wrong = ToolTarget(
        key="mcp-search", endpoint_url=SERVICES["mcp-sql"], auth_type="forward_user", auth={}
    )
    with pytest.raises(mcp_client.ToolCallError) as err:
        asyncio.run(mcp_client.discover(wrong, settings, caller=CALLER))
    assert err.value.code == "tool_auth_failed"


def test_05a_live_run_sql_on_demo_database(settings):
    cli._seed_sql_demo(settings, SCHEMA_DIR)  # the documented operator step; idempotent
    sql = "SELECT code FROM departments ORDER BY id LIMIT 2"
    result = asyncio.run(
        mcp_client.call(
            target("mcp-sql"), "run_sql", {"sql": sql, "reason": "live"}, settings, caller=CALLER
        )
    )
    assert not result.is_error, result.text
    assert result.text.splitlines()[0] == "code" and result.text.endswith("rows: 2")
