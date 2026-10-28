"""Superset OpenAPI subset for 05b's "publish OpenAPI as MCP" test (plan/05 A3).

Hand-written subset modelled on Superset's /api/v1 endpoints; NOT a verbatim copy of
a real /api/v1/_openapi output (no external access here). 05b checks it against the
pinned Superset version. Which operations need approval (create chart, add to
dashboard) is a tool_actions setting, so it is documented in README, not in the spec.
"""

import json
import random
import re
from pathlib import Path

from . import write_text

_PLAIN = re.compile(r"^[A-Za-z/][A-Za-z0-9_./{}-]*$")
_RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "y", "n", "~"}


def _scalar(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    if _PLAIN.match(s) and s.lower() not in _RESERVED:
        return s
    return json.dumps(s, ensure_ascii=False)  # JSON string is valid YAML


def to_yaml(node, indent: int = 0) -> list[str]:
    """Minimal block-style YAML emitter for dict/list/scalar trees (deterministic)."""
    pad = " " * indent
    lines: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            key = _scalar(k)
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{key}:")
                lines.extend(to_yaml(v, indent + 2))
            else:
                if isinstance(v, dict):
                    value = "{}"
                elif isinstance(v, list):
                    value = "[]"
                else:
                    value = _scalar(v)
                lines.append(f"{pad}{key}: {value}")
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)) and item:
                sub = to_yaml(item, indent + 2)
                lines.append(f"{pad}- {sub[0].lstrip()}")
                lines.extend(sub[1:])
            else:
                lines.append(f"{pad}- {_scalar(item)}")
    else:
        lines.append(f"{pad}{_scalar(node)}")
    return lines


def _pk() -> dict:
    return {"name": "pk", "in": "path", "required": True, "schema": {"type": "integer"}}


def _ok(description: str, ref: str) -> dict:
    return {
        "200": {
            "description": description,
            "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{ref}"}}},
        }
    }


SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Superset API (FFCore örnek alt kümesi)",
        "version": "1.0.0-sample",
        "description": "Agent aracı olarak yayınlamak için seçilmiş 6 Superset işlemi. Sentetik "
        "örnek; gerçek Superset sürümüyle 05b'de doğrulanır.",
    },
    "servers": [{"url": "http://superset.ornek.local"}],
    "security": [{"bearerAuth": []}],
    "paths": {
        "/api/v1/dashboard/": {
            "get": {
                "operationId": "searchDashboards",
                "summary": "Dashboard ara",
                "description": "Başlığa göre dashboard arar.",
                "parameters": [
                    {
                        "name": "q",
                        "in": "query",
                        "required": False,
                        "description": "Rison biçiminde filtre, ör. "
                        "(filters:!((col:dashboard_title,opr:ct,value:yatak)))",
                        "schema": {"type": "string"},
                    }
                ],
                "responses": _ok("Dashboard listesi", "DashboardList"),
            },
        },
        "/api/v1/chart/": {
            "get": {
                "operationId": "listCharts",
                "summary": "Chart listele",
                "description": "Chart'ları ada ve dataset'e göre listeler.",
                "parameters": [
                    {
                        "name": "q",
                        "in": "query",
                        "required": False,
                        "description": "Rison biçiminde filtre ve sayfalama.",
                        "schema": {"type": "string"},
                    }
                ],
                "responses": _ok("Chart listesi", "ChartList"),
            },
            "post": {
                "operationId": "createChart",
                "summary": "Chart oluştur",
                "description": "Bir dataset üzerinde yeni chart oluşturur.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/ChartCreate"}}
                    },
                },
                "responses": {
                    "201": {
                        "description": "Oluşturulan chart",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ChartRef"}
                            }
                        },
                    }
                },
            },
        },
        "/api/v1/chart/{pk}": {
            "put": {
                "operationId": "addChartToDashboard",
                "summary": "Chart'ı dashboard'a ekle",
                "description": "Chart'ın bağlı olduğu dashboard listesini günceller.",
                "parameters": [_pk()],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ChartDashboards"}
                        }
                    },
                },
                "responses": _ok("Güncellenen chart", "ChartRef"),
            },
        },
        "/api/v1/chart/{pk}/data/": {
            "get": {
                "operationId": "getChartData",
                "summary": "Chart verisi",
                "description": "Chart'ın sorgu sonucunu döner.",
                "parameters": [_pk()],
                "responses": _ok("Chart verisi", "ChartData"),
            },
        },
        "/api/v1/dataset/{pk}": {
            "get": {
                "operationId": "getDatasetMetrics",
                "summary": "Dataset metrikleri",
                "description": "Dataset'in kolonlarını ve metrik tanımlarını döner.",
                "parameters": [_pk()],
                "responses": _ok("Dataset ayrıntısı", "Dataset"),
            },
        },
    },
    "components": {
        "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
        "schemas": {
            "DashboardList": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                    "result": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "dashboard_title": {"type": "string"},
                                "url": {"type": "string"},
                            },
                        },
                    },
                },
            },
            "ChartList": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer"},
                    "result": {"type": "array", "items": {"$ref": "#/components/schemas/ChartRef"}},
                },
            },
            "ChartRef": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "slice_name": {"type": "string"},
                    "viz_type": {"type": "string"},
                },
            },
            "ChartCreate": {
                "type": "object",
                "required": ["slice_name", "viz_type", "datasource_id", "datasource_type"],
                "properties": {
                    "slice_name": {"type": "string"},
                    "viz_type": {"type": "string"},
                    "datasource_id": {"type": "integer"},
                    "datasource_type": {"type": "string", "enum": ["table"]},
                    "params": {"type": "string", "description": "JSON metni olarak chart ayarları"},
                },
            },
            "ChartDashboards": {
                "type": "object",
                "required": ["dashboards"],
                "properties": {"dashboards": {"type": "array", "items": {"type": "integer"}}},
            },
            "ChartData": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "rowcount": {"type": "integer"},
                                "data": {"type": "array", "items": {"type": "object"}},
                            },
                        },
                    }
                },
            },
            "Dataset": {
                "type": "object",
                "properties": {
                    "result": {
                        "type": "object",
                        "properties": {
                            "table_name": {"type": "string"},
                            "columns": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "column_name": {"type": "string"},
                                        "type": {"type": "string"},
                                    },
                                },
                            },
                            "metrics": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "metric_name": {"type": "string"},
                                        "expression": {"type": "string"},
                                        "description": {"type": "string"},
                                    },
                                },
                            },
                        },
                    }
                },
            },
        },
    },
}


def generate(rng: random.Random, out: Path, seed: int) -> None:
    write_text(out / "openapi" / "superset.yaml", "\n".join(to_yaml(SPEC)) + "\n")
