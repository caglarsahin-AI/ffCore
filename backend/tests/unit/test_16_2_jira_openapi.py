"""16-2: the Jira sample (`data/samples/openapi/jira.yaml`) publishes through 05b's OpenAPI →
MCP road: two reads (search, get) and two writes (create, comment) that are published with
approval. Synthetic: no real Jira address."""

from pathlib import Path

from ffcore.services import mcp_openapi

JIRA = Path(__file__).resolve().parents[3] / "data" / "samples" / "openapi" / "jira.yaml"


def test_16_2_jira_sample_has_four_exposable_operations():
    spec = mcp_openapi.load_spec(JIRA.read_text(encoding="utf-8"))
    ops = {op["name"]: op for op in mcp_openapi.catalog(spec)}
    assert set(ops) == {"searchIssues", "getIssue", "createIssue", "addComment"}
    assert all(op["exposable"] and op["reason"] is None for op in ops.values())
    assert {n for n, op in ops.items() if op["method"] == "POST"} == {"createIssue", "addComment"}
    search = mcp_openapi.build_request(ops["searchIssues"], {"jql": "project = OPS"})
    assert (search.method, search.path) == ("GET", "/rest/api/2/search")
    assert search.params == {"jql": "project = OPS"}
    comment = mcp_openapi.build_request(
        ops["addComment"], {"issueKey": "OPS-1", "body": {"body": "Denendi."}}
    )
    assert (comment.method, comment.path) == ("POST", "/rest/api/2/issue/OPS-1/comment")
    assert comment.json == {"body": "Denendi."}
