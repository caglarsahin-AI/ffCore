"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema-14";

// Memory calls (14, types generated from backend/openapi/14.yaml). A member reads and changes
// only their own items; settings and statistics are an administrator's (no text in them).
type S = components["schemas"];
export type Memory = S["MemoryOut"];
export type MemoryKind = Memory["kind"];
export type MemorySettings = S["MemorySettingsOut"];
export type MemorySettingsIn = S["MemorySettingsIn"];
export type MemoryStatistics = S["MemoryStats"];

export const MEMORY_KINDS = ["profile", "preference", "fact", "decision"] as const satisfies readonly MemoryKind[];

const base = (projectId: string) => `/api/v1/projects/${projectId}/memories`;

export const memoryKeys = {
  all: (projectId: string) => ["projects", projectId, "memories"] as const,
  list: (projectId: string) => ["projects", projectId, "memories", "list"] as const,
  ids: (projectId: string, ids: string[]) => ["projects", projectId, "memories", "ids", ids] as const,
  optOut: (projectId: string) => ["projects", projectId, "memories", "opt-out"] as const,
  settings: (projectId: string, agentId: string | null) => ["projects", projectId, "memories", "settings", agentId ?? "project"] as const,
  stats: (projectId: string) => ["projects", projectId, "memories", "stats"] as const,
};

export function useMemories(projectId: string) {
  return useQuery({
    queryKey: memoryKeys.list(projectId),
    queryFn: () => api<S["MemoryList"]>("GET", base(projectId)).then((r) => r.items),
  });
}

// The caller's own items among the given ids (run events carry ids only); an id that is gone
// (deleted) is simply not returned.
export function useMemoriesByIds(projectId: string, ids: string[]) {
  const sorted = [...ids].sort();
  return useQuery({
    queryKey: memoryKeys.ids(projectId, sorted),
    enabled: sorted.length > 0,
    queryFn: () => {
      const query = new URLSearchParams(sorted.map((id) => ["ids", id]));
      return api<S["MemoryList"]>("GET", `${base(projectId)}?${query}`).then((r) => r.items);
    },
  });
}

function useMemoryMutation<T, R>(projectId: string, call: (input: T) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () => client.invalidateQueries({ queryKey: memoryKeys.all(projectId) }),
  });
}

export function useRemember(projectId: string) {
  return useMemoryMutation(projectId, (text: string) => api<Memory>("POST", base(projectId), { text }));
}

export function useUpdateMemory(projectId: string) {
  return useMemoryMutation(projectId, ({ id, text }: { id: string; text: string }) => api<Memory>("PATCH", `${base(projectId)}/${id}`, { text }));
}

export function useDeleteMemory(projectId: string) {
  return useMemoryMutation(projectId, (id: string) => api<void>("DELETE", `${base(projectId)}/${id}`));
}

export function useDeleteAllMemories(projectId: string) {
  return useMemoryMutation(projectId, () => api<void>("DELETE", base(projectId)));
}

export function useOptOut(projectId: string) {
  return useQuery({
    queryKey: memoryKeys.optOut(projectId),
    queryFn: () => api<S["OptOutOut"]>("GET", `${base(projectId)}/opt-out`).then((r) => r.opted_out),
  });
}

// `out`: turn memory off for the caller (PUT); false turns it on again (DELETE).
export function useSetOptOut(projectId: string) {
  return useMemoryMutation(projectId, (out: boolean) => api<S["OptOutOut"]>(out ? "PUT" : "DELETE", `${base(projectId)}/opt-out`));
}

const settingsPath = (projectId: string, agentId: string | null) =>
  `${base(projectId)}/settings${agentId ? `?${new URLSearchParams({ agent_id: agentId })}` : ""}`;

export function useMemorySettings(projectId: string, agentId: string | null, enabled = true) {
  return useQuery({
    queryKey: memoryKeys.settings(projectId, agentId),
    enabled,
    queryFn: () => api<MemorySettings>("GET", settingsPath(projectId, agentId)),
  });
}

export function useSaveMemorySettings(projectId: string, agentId: string | null) {
  return useMemoryMutation(projectId, (body: MemorySettingsIn) => api<MemorySettings>("PUT", settingsPath(projectId, agentId), body));
}

export function useMemoryStats(projectId: string) {
  return useQuery({
    queryKey: memoryKeys.stats(projectId),
    queryFn: () => api<MemoryStatistics>("GET", `${base(projectId)}/stats`),
  });
}
