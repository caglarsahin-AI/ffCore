"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema-05b";
import { toolKeys } from "@/lib/api/tools-queries";

// Published MCP servers (05b contract, types generated from backend/openapi/05b.yaml). Reads are
// analyst and up; every change is a project admin's (backend `Admin`, KARARLAR "10c-3 plan
// kararları" S1).
type S = components["schemas"];
export type McpServer = S["McpServerOut"];
export type McpServerCreate = S["McpServerCreate"];
export type McpServerUpdate = S["McpServerUpdate"];
export type McpOperation = S["OperationOut"];
export type McpAlias = S["Alias"];
export type ConnectionTest = S["ConnectionTest"];
export type CallsSummary = S["CallsSummary"];
export type McpCall = S["CallOut"];
export type McpAuth = McpServerCreate["upstream_auth"];
export type McpAuthType = McpAuth["type"];
export type SourceKind = McpServerOut["source_kind"];
export type McpAccess = McpServerOut["access"];
export type GuardrailMode = McpServerOut["guardrail_mode"];
export type ServerStatus = McpServerOut["status"];
export type CallStatus = McpCall["status"];
type McpServerOut = S["McpServerOut"];

export const SOURCE_KINDS = ["openapi", "remote_mcp"] as const satisfies readonly SourceKind[];
export const MCP_ACCESS_MODES = ["internal", "token"] as const satisfies readonly McpAccess[];
export const GUARDRAIL_MODES = ["off", "monitor", "enforce"] as const satisfies readonly GuardrailMode[];
export const SERVER_STATUSES = ["draft", "active", "disabled"] as const satisfies readonly ServerStatus[];
export const CALL_STATUSES = ["ok", "error", "blocked", "denied"] as const satisfies readonly CallStatus[];
export const MCP_AUTH_TYPES = ["none", "bearer", "header", "basic"] as const satisfies readonly McpAuthType[];

// Why an operation of the document cannot be published (backend/ffcore/services/mcp_openapi.py).
// A reason outside this list is shown as its raw code, never hidden.
export const OPERATION_REASONS = [
  "external_ref",
  "ref_not_found",
  "ref_cycle",
  "openapi_path_invalid",
  "operation_id_missing",
  "operation_id_duplicate",
  "operation_name_invalid",
  "parameter_location_unsupported",
  "parameter_name_conflict",
  "request_body_unsupported",
] as const;
export type OperationReason = (typeof OPERATION_REASONS)[number];
export const isKnownReason = (reason: string): reason is OperationReason =>
  (OPERATION_REASONS as readonly string[]).includes(reason);

// The monitoring window (05b `hours`, 1..744); the screen shows the brief's 24 hours.
export const CALLS_WINDOW_HOURS = 24;

const base = (projectId: string) => `/api/v1/projects/${projectId}/mcp-servers`;

export const mcpServerKeys = {
  list: (projectId: string) => ["projects", projectId, "mcp-servers"] as const,
  one: (projectId: string, serverId: string) => ["projects", projectId, "mcp-servers", serverId] as const,
  calls: (projectId: string, serverId: string) => ["projects", projectId, "mcp-servers", serverId, "calls"] as const,
};

export function useMcpServers(projectId: string) {
  return useQuery({
    queryKey: mcpServerKeys.list(projectId),
    queryFn: () => api<S["McpServerList"]>("GET", base(projectId)).then((r) => r.data),
  });
}

export function useMcpServer(projectId: string, serverId: string) {
  return useQuery({
    queryKey: mcpServerKeys.one(projectId, serverId),
    queryFn: () => api<McpServer>("GET", `${base(projectId)}/${serverId}`),
  });
}

export function useMcpServerCalls(projectId: string, serverId: string) {
  return useQuery({
    queryKey: mcpServerKeys.calls(projectId, serverId),
    queryFn: () => api<CallsSummary>("GET", `${base(projectId)}/${serverId}/calls?hours=${CALLS_WINDOW_HOURS}`),
  });
}

// Every server change refreshes the list and stores the changed server (its operations come with it).
function useServerMutation<T>(projectId: string, call: (input: T) => Promise<McpServer | undefined>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: (server) => {
      // exact: the list key is a prefix of the server's own key, which gets the fresh answer below.
      void client.invalidateQueries({ queryKey: mcpServerKeys.list(projectId), exact: true });
      if (server) client.setQueryData(mcpServerKeys.one(projectId, server.id), server);
    },
  });
}

export function useCreateMcpServer(projectId: string) {
  return useServerMutation(projectId, (body: McpServerCreate) => api<McpServer>("POST", base(projectId), body));
}

export function useUpdateMcpServer(projectId: string) {
  return useServerMutation(projectId, ({ id, body }: { id: string; body: McpServerUpdate }) =>
    api<McpServer>("PATCH", `${base(projectId)}/${id}`, body),
  );
}

export function useReplaceMcpSpec(projectId: string) {
  return useServerMutation(projectId, ({ id, spec }: { id: string; spec: string }) =>
    api<McpServer>("PUT", `${base(projectId)}/${id}/spec`, { spec }),
  );
}

export function useDiscoverMcpServer(projectId: string) {
  return useServerMutation(projectId, (id: string) => api<McpServer>("POST", `${base(projectId)}/${id}/discover`));
}

export function useDeleteMcpServer(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<undefined>("DELETE", `${base(projectId)}/${id}`),
    onSuccess: () => client.invalidateQueries({ queryKey: mcpServerKeys.list(projectId) }),
  });
}

export function useTestMcpServer(projectId: string) {
  return useMutation({
    mutationFn: (id: string) => api<ConnectionTest>("POST", `${base(projectId)}/${id}/test`),
  });
}

// "Add as a tool": a 05a tool at the server's own /mcp/<key>/ endpoint; the tool list refreshes.
export function useAddMcpServerTool(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<S["ToolOut"]>("POST", `${base(projectId)}/${id}/tools`),
    onSuccess: () => client.invalidateQueries({ queryKey: toolKeys.list(projectId) }),
  });
}
