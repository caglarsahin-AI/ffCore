"""05b: an OpenAPI document becomes MCP tool definitions (operationId -> name, parameters and
JSON body -> input_schema, description) and arguments become one upstream request.

Operations that cannot be published say why (exposable=false + reason); nothing is skipped
silently (ARCH-06)."""

import json
from pathlib import Path

import pytest

from ffcore.services import mcp_openapi
from ffcore.services.mcp_openapi import ArgumentsError, SpecError

SUPERSET = Path(__file__).resolve().parents[3] / "data" / "samples" / "openapi" / "superset.yaml"
SIX = {
    "searchDashboards",
    "listCharts",
    "createChart",
    "addChartToDashboard",
    "getChartData",
    "getDatasetMetrics",
}


def _catalog(spec: dict) -> dict[str, dict]:
    return {op["name"]: op for op in mcp_openapi.catalog(spec)}


def _spec(paths: dict, components: dict | None = None) -> dict:
    return {"openapi": "3.0.3", "info": {"title": "t", "version": "1"}, "paths": paths} | (
        {"components": components} if components else {}
    )


def test_05b_superset_has_six_exposable_operations():
    ops = _catalog(mcp_openapi.load_spec(SUPERSET.read_text(encoding="utf-8")))
    assert set(ops) == SIX
    assert all(op["exposable"] and op["reason"] is None for op in ops.values())
    assert ops["createChart"]["method"] == "POST" and ops["createChart"]["path"] == "/api/v1/chart/"
    assert ops["searchDashboards"]["description"] == "Başlığa göre dashboard arar."


def test_05b_parameters_and_body_become_input_schema_with_refs_resolved():
    ops = _catalog(mcp_openapi.load_spec(SUPERSET.read_text(encoding="utf-8")))
    put = ops["addChartToDashboard"]["input_schema"]
    assert put["type"] == "object"
    assert put["properties"]["pk"]["type"] == "integer"
    assert put["properties"]["body"]["properties"]["dashboards"]["type"] == "array"
    assert sorted(put["required"]) == ["body", "pk"]
    create = ops["createChart"]["input_schema"]
    assert create["properties"]["body"]["required"] == [
        "slice_name",
        "viz_type",
        "datasource_id",
        "datasource_type",
    ]
    assert "$ref" not in json.dumps(ops)
    search = ops["searchDashboards"]["input_schema"]
    assert search["properties"]["q"]["description"].startswith("Rison")
    assert search.get("required", []) == []


def test_05b_json_document_is_accepted():
    spec = _spec(
        {"/a": {"get": {"operationId": "getA", "responses": {"200": {"description": "x"}}}}}
    )
    assert [op["name"] for op in mcp_openapi.catalog(mcp_openapi.load_spec(json.dumps(spec)))] == [
        "getA"
    ]


@pytest.mark.parametrize(
    "text, code",
    [
        ("not: [valid", "spec_invalid"),
        ("- a list", "spec_invalid"),
        ('{"swagger": "2.0", "paths": {}}', "spec_version_unsupported"),
        ('{"openapi": "3.0.0"}', "spec_invalid"),
    ],
)
def test_05b_bad_documents_are_refused_with_a_code(text, code):
    with pytest.raises(SpecError) as caught:
        mcp_openapi.catalog(mcp_openapi.load_spec(text))
    assert caught.value.code == code


def test_05b_oversized_document_is_refused():
    with pytest.raises(SpecError) as caught:
        mcp_openapi.load_spec("x" * (mcp_openapi.MAX_SPEC_CHARS + 1))
    assert caught.value.code == "spec_too_large"


def test_05b_unpublishable_operations_say_why():
    ok = {"200": {"description": "x"}}
    spec = _spec(
        {
            "/h": {
                "get": {
                    "operationId": "withHeader",
                    "parameters": [
                        {"name": "X-Tenant", "in": "header", "schema": {"type": "string"}}
                    ],
                    "responses": ok,
                }
            },
            "/x": {
                "get": {
                    "operationId": "external",
                    "responses": ok,
                    "parameters": [{"$ref": "other.yaml#/p"}],
                }
            },
            "/n": {"get": {"responses": ok}},
            "/f": {
                "post": {
                    "operationId": "upload",
                    "requestBody": {"content": {"multipart/form-data": {"schema": {}}}},
                    "responses": ok,
                }
            },
            "/bad name": {"get": {"operationId": "has space", "responses": ok}},
        }
    )
    ops = _catalog(spec)
    assert ops["withHeader"]["reason"] == "parameter_location_unsupported"
    assert ops["external"]["reason"] == "external_ref"
    assert ops["upload"]["reason"] == "request_body_unsupported"
    assert ops["has space"]["reason"] == "operation_name_invalid"
    unnamed = [op for op in ops.values() if op["reason"] == "operation_id_missing"]
    assert len(unnamed) == 1 and unnamed[0]["path"] == "/n"
    assert not any(op["exposable"] for op in ops.values())


def test_05b_ref_cycle_is_refused_not_looped():
    spec = _spec(
        {
            "/c": {
                "post": {
                    "operationId": "cyclic",
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/A"}}
                        }
                    },
                    "responses": {"200": {"description": "x"}},
                }
            }
        },
        {
            "schemas": {
                "A": {"type": "object", "properties": {"a": {"$ref": "#/components/schemas/A"}}}
            }
        },
    )
    assert _catalog(spec)["cyclic"]["reason"] == "ref_cycle"


def test_05b_request_from_arguments_encodes_path_and_query():
    ops = _catalog(mcp_openapi.load_spec(SUPERSET.read_text(encoding="utf-8")))
    request = mcp_openapi.build_request(ops["getChartData"], {"pk": "1/../../admin"})
    assert request.method == "GET"
    assert request.path == "/api/v1/chart/1%2F..%2F..%2Fadmin/data/"
    assert request.params == {} and request.json is None
    search = mcp_openapi.build_request(ops["searchDashboards"], {"q": "(page:0)"})
    assert search.path == "/api/v1/dashboard/" and search.params == {"q": "(page:0)"}
    body = {"slice_name": "s", "viz_type": "table", "datasource_id": 1, "datasource_type": "table"}
    create = mcp_openapi.build_request(ops["createChart"], {"body": body})
    assert create.method == "POST" and create.json == body


@pytest.mark.parametrize(
    "arguments",
    [{}, {"pk": 1, "extra": 2}, {"pk": None}, {"pk": {"nested": 1}}],
)
def test_05b_bad_arguments_are_refused(arguments):
    ops = _catalog(mcp_openapi.load_spec(SUPERSET.read_text(encoding="utf-8")))
    with pytest.raises(ArgumentsError):
        mcp_openapi.build_request(ops["getChartData"], arguments)
