"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema-06a";

// Agent calls (06a contract, types generated from backend/openapi/06a.yaml).
type S = components["schemas"];
export type Agent = S["AgentOut"];
export type AgentCreate = S["AgentCreate"];
export type AgentVersion = S["VersionOut"];
export type AgentDefinition = S["AgentDefinition"];

const base = (projectId: string) => `/api/v1/projects/${projectId}/agents`;

export const agentKeys = {
  list: (projectId: string) => ["projects", projectId, "agents"] as const,
  one: (projectId: string, agentId: string) => ["projects", projectId, "agents", agentId] as const,
  versions: (projectId: string, agentId: string) => ["projects", projectId, "agents", agentId, "versions"] as const,
};

export function useAgents(projectId: string) {
  return useQuery({
    queryKey: agentKeys.list(projectId),
    queryFn: () => api<S["AgentList"]>("GET", base(projectId)).then((r) => r.items),
  });
}

export function useAgent(projectId: string, agentId: string) {
  return useQuery({
    queryKey: agentKeys.one(projectId, agentId),
    queryFn: () => api<Agent>("GET", `${base(projectId)}/${agentId}`),
  });
}

export function useAgentVersions(projectId: string, agentId: string) {
  return useQuery({
    queryKey: agentKeys.versions(projectId, agentId),
    queryFn: () => api<S["VersionList"]>("GET", `${base(projectId)}/${agentId}/versions`).then((r) => r.items),
  });
}

// Any agent or version change refreshes the list, the agent and its versions.
function useAgentMutation<T, R>(projectId: string, call: (input: T) => Promise<R>, agentId?: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: agentKeys.list(projectId) });
      // agentKeys.one is a prefix of agentKeys.versions, so both refresh.
      if (agentId) void client.invalidateQueries({ queryKey: agentKeys.one(projectId, agentId) });
    },
  });
}

export function useCreateAgent(projectId: string) {
  return useAgentMutation(projectId, (body: AgentCreate) => api<Agent>("POST", base(projectId), body));
}

export function useUpdateAgent(projectId: string, agentId: string) {
  return useAgentMutation(projectId, (body: S["AgentUpdate"]) => api<Agent>("PATCH", `${base(projectId)}/${agentId}`, body), agentId);
}

export function useDeleteAgent(projectId: string) {
  return useAgentMutation(projectId, (id: string) => api<undefined>("DELETE", `${base(projectId)}/${id}`));
}

export function useSaveVersion(projectId: string, agentId: string) {
  return useAgentMutation(
    projectId,
    ({ version, definition }: { version: number; definition: AgentDefinition }) =>
      api<AgentVersion>("PUT", `${base(projectId)}/${agentId}/versions/${version}`, { definition }),
    agentId,
  );
}

export function useNewDraft(projectId: string, agentId: string) {
  return useAgentMutation(
    projectId,
    (fromVersion: number) => api<AgentVersion>("POST", `${base(projectId)}/${agentId}/versions`, { from_version: fromVersion }),
    agentId,
  );
}

export function usePublish(projectId: string, agentId: string) {
  return useAgentMutation(projectId, (version: number) => api<Agent>("POST", `${base(projectId)}/${agentId}/publish`, { version }), agentId);
}

export function useRollback(projectId: string, agentId: string) {
  return useAgentMutation(projectId, (version: number) => api<Agent>("POST", `${base(projectId)}/${agentId}/rollback`, { version }), agentId);
}
