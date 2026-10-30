"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema-05a";

// Tool calls (05a contract, types generated from backend/openapi/05a.yaml).
type S = components["schemas"];
export type Tool = S["ToolOut"];
export type ToolAction = S["ToolActionOut"];
export type ToolCreate = S["ToolCreate"];
export type ToolUpdate = S["ToolUpdate"];
export type ToolActionUpdate = S["ToolActionUpdate"];
export type InvokeResult = S["InvokeResult"];
export type ToolAuth = ToolCreate["auth"];
export type ToolAuthType = ToolAuth["type"];

export const TOOL_AUTH_TYPES = ["none", "bearer", "header", "basic", "forward_user"] as const satisfies readonly ToolAuthType[];

const base = (projectId: string) => `/api/v1/projects/${projectId}/tools`;

export const toolKeys = {
  list: (projectId: string) => ["projects", projectId, "tools"] as const,
  one: (projectId: string, toolId: string) => ["projects", projectId, "tools", toolId] as const,
};

export function useTools(projectId: string, enabled = true) {
  return useQuery({
    queryKey: toolKeys.list(projectId),
    queryFn: () => api<S["ToolList"]>("GET", base(projectId)).then((r) => r.data),
    enabled,
  });
}

export function useTool(projectId: string, toolId: string) {
  return useQuery({
    queryKey: toolKeys.one(projectId, toolId),
    queryFn: () => api<Tool>("GET", `${base(projectId)}/${toolId}`),
  });
}

// Every tool change refreshes the list and the changed tool (its actions come with it).
function useToolMutation<T>(projectId: string, call: (input: T) => Promise<Tool | undefined>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: (tool) => {
      void client.invalidateQueries({ queryKey: toolKeys.list(projectId) });
      if (tool) client.setQueryData(toolKeys.one(projectId, tool.id), tool);
    },
  });
}

export function useCreateTool(projectId: string) {
  return useToolMutation(projectId, (body: ToolCreate) => api<Tool>("POST", base(projectId), body));
}

export function useUpdateTool(projectId: string) {
  return useToolMutation(projectId, ({ id, body }: { id: string; body: ToolUpdate }) =>
    api<Tool>("PATCH", `${base(projectId)}/${id}`, body),
  );
}

export function useDeleteTool(projectId: string) {
  return useToolMutation(projectId, (id: string) => api<undefined>("DELETE", `${base(projectId)}/${id}`));
}

export function useDiscoverTool(projectId: string) {
  return useToolMutation(projectId, (id: string) => api<Tool>("POST", `${base(projectId)}/${id}/discover`));
}

export function useUpdateToolAction(projectId: string, toolId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ action, body }: { action: string; body: ToolActionUpdate }) =>
      api<ToolAction>("PATCH", `${base(projectId)}/${toolId}/actions/${encodeURIComponent(action)}`, body),
    onSuccess: () => client.invalidateQueries({ queryKey: toolKeys.one(projectId, toolId) }),
  });
}

export function useInvokeToolAction(projectId: string, toolId: string) {
  return useMutation({
    mutationFn: ({ action, args }: { action: string; args: Record<string, unknown> }) =>
      api<InvokeResult>("POST", `${base(projectId)}/${toolId}/actions/${encodeURIComponent(action)}/invoke`, {
        arguments: args,
      }),
  });
}
