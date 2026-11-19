// Builders for the 10c-3 MCP server component tests (05b contract shapes, McpServerOut/OperationOut/CallOut).

export const S = "/api/v1/projects/p1/mcp-servers";

export function operation(over: Record<string, unknown> = {}) {
  return {
    name: "listCharts",
    method: "GET",
    path: "/api/v1/chart/",
    description: "List charts",
    input_schema: { type: "object", properties: {} },
    exposable: true,
    reason: null,
    alias: null,
    alias_description: null,
    exposed: false,
    ...over,
  };
}

export function server(over: Record<string, unknown> = {}) {
  return {
    id: "s1",
    project_id: "p1",
    key: "superset",
    name: "Superset",
    source_kind: "openapi",
    endpoint_path: "/mcp/superset/",
    upstream_base_url: "http://superset.example.com/api",
    upstream_auth: { type: "bearer", token: "***" },
    operations: [operation()],
    exposed_operations: [],
    protocols: ["streamable_http"],
    access: "internal",
    guardrail_mode: "monitor",
    guardrail_policy_key: "default",
    status: "draft",
    discovered_at: "2026-11-19T08:00:00Z",
    last_error_code: null,
    created_by: "u1",
    created_at: "2026-11-19T08:00:00Z",
    updated_at: "2026-11-19T08:00:00Z",
    ...over,
  };
}

export function call(over: Record<string, unknown> = {}) {
  return {
    operation: "listCharts",
    status: "ok",
    error_code: null,
    latency_ms: 42,
    ts: "2026-11-19T09:00:00Z",
    run_id: null,
    actor_type: "user",
    ...over,
  };
}

export function calls(over: Record<string, unknown> = {}) {
  return { window_hours: 24, requests: 0, errors: 0, blocked: 0, p50_ms: null, p95_ms: null, recent: [], ...over };
}
