"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type S = components["schemas"];
export type Project = S["ProjectOut"];
export type Member = S["MemberOut"];
export type UserSummary = S["UserOut"];
export type Provider = S["ProviderOut"];
export type Model = S["ModelOut"];

// Query keys: one per list; mutations invalidate the list they change.
const keys = {
  projects: ["projects"] as const,
  members: (projectId: string) => ["projects", projectId, "members"] as const,
  users: ["users"] as const,
  providers: ["providers"] as const,
  models: (projectId: string) => ["projects", projectId, "models"] as const,
};

export function useProjects(enabled = true) {
  return useQuery({
    queryKey: keys.projects,
    queryFn: () => api<S["ProjectList"]>("GET", "/api/v1/projects").then((r) => r.data),
    enabled,
  });
}

export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: S["ProjectCreate"]) => api<Project>("POST", "/api/v1/projects", body),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.projects }),
  });
}

export function useMembers(projectId: string) {
  return useQuery({
    queryKey: keys.members(projectId),
    queryFn: () => api<S["MemberList"]>("GET", `/api/v1/projects/${projectId}/members`).then((r) => r.data),
  });
}

function useMemberMutation<T>(projectId: string, call: (input: T) => Promise<unknown>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.members(projectId) }),
  });
}

export function useAddMember(projectId: string) {
  return useMemberMutation(projectId, (body: S["MemberCreate"]) =>
    api<Member>("POST", `/api/v1/projects/${projectId}/members`, body),
  );
}

export function useUpdateMember(projectId: string) {
  return useMemberMutation(projectId, ({ userId, body }: { userId: string; body: S["MemberUpdate"] }) =>
    api<Member>("PATCH", `/api/v1/projects/${projectId}/members/${userId}`, body),
  );
}

export function useRemoveMember(projectId: string) {
  return useMemberMutation(projectId, (userId: string) =>
    api<void>("DELETE", `/api/v1/projects/${projectId}/members/${userId}`),
  );
}

// Superadmin only (03a require_superadmin): used to pick a new member.
export function useUsers(enabled: boolean) {
  return useQuery({
    queryKey: keys.users,
    queryFn: () => api<S["UserList"]>("GET", "/api/v1/users").then((r) => r.data),
    enabled,
  });
}

export function useProviders() {
  return useQuery({
    queryKey: keys.providers,
    queryFn: () => api<S["ProviderList"]>("GET", "/api/v1/providers").then((r) => r.data),
  });
}

export function useModels(projectId: string) {
  return useQuery({
    queryKey: keys.models(projectId),
    queryFn: () => api<S["ModelList"]>("GET", `/api/v1/projects/${projectId}/models`).then((r) => r.data),
  });
}
