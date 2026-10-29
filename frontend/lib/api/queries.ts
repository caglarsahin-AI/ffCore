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
export type DriverSpec = S["DriverSpec"];
export type CatalogEntry = S["CatalogEntryOut"];
export type TestResult = S["ProviderTestResult"];

// Query keys: one per list; mutations invalidate the list they change.
const keys = {
  projects: ["projects"] as const,
  members: (projectId: string) => ["projects", projectId, "members"] as const,
  users: ["users"] as const,
  providers: ["providers"] as const,
  drivers: ["provider-drivers"] as const,
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

export function useProviders(enabled = true) {
  return useQuery({
    queryKey: keys.providers,
    queryFn: () => api<S["ProviderList"]>("GET", "/api/v1/providers").then((r) => r.data),
    enabled,
  });
}

// Superadmin only, like every provider call (03a require_superadmin).
export function useDrivers() {
  return useQuery({
    queryKey: keys.drivers,
    queryFn: () => api<S["DriverList"]>("GET", "/api/v1/provider-drivers").then((r) => r.data),
    staleTime: Infinity,
  });
}

function useProviderMutation<T, R>(call: (input: T) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.providers }),
  });
}

export function useCreateProvider() {
  return useProviderMutation((body: S["ProviderCreate"]) => api<Provider>("POST", "/api/v1/providers", body));
}

export function useUpdateProvider() {
  return useProviderMutation(({ id, body }: { id: string; body: S["ProviderUpdate"] }) =>
    api<Provider>("PATCH", `/api/v1/providers/${id}`, body),
  );
}

export function useSetProviderProjects() {
  return useProviderMutation(({ id, projectIds }: { id: string; projectIds: string[] }) =>
    api<Provider>("PUT", `/api/v1/providers/${id}/projects`, { project_ids: projectIds } satisfies S["ProviderProjectsUpdate"]),
  );
}

export function useDeactivateProvider() {
  return useProviderMutation((id: string) => api<void>("DELETE", `/api/v1/providers/${id}`));
}

// Connection tests change nothing, so they invalidate nothing; a failed test is a result, not an error.
export function useTestProviderConfig() {
  return useMutation({
    mutationFn: (body: S["ProviderTestRequest"]) => api<TestResult>("POST", "/api/v1/providers/test", body),
  });
}

export function useTestProvider() {
  return useMutation({
    mutationFn: (id: string) => api<TestResult>("POST", `/api/v1/providers/${id}/test`),
  });
}

// "Fill from catalog" is an explicit button, so a mutation-style call rather than a cached query.
export function useCatalogLookup() {
  return useMutation({
    mutationFn: ({ driver, modelId }: { driver: S["ProviderDriver"]; modelId: string }) =>
      api<S["CatalogList"]>(
        "GET",
        `/api/v1/model-catalog?${new URLSearchParams({ driver, model_id: modelId })}`,
      ).then((r) => r.data),
  });
}

export function useModels(projectId: string) {
  return useQuery({
    queryKey: keys.models(projectId),
    queryFn: () => api<S["ModelList"]>("GET", `/api/v1/projects/${projectId}/models`).then((r) => r.data),
  });
}

function useModelMutation<T, R>(projectId: string, call: (input: T) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () => client.invalidateQueries({ queryKey: keys.models(projectId) }),
  });
}

export function useCreateModel(projectId: string) {
  return useModelMutation(projectId, (body: S["ModelCreate"]) =>
    api<Model>("POST", `/api/v1/projects/${projectId}/models`, body),
  );
}

export function useUpdateModel(projectId: string) {
  return useModelMutation(projectId, ({ id, body }: { id: string; body: S["ModelUpdate"] }) =>
    api<Model>("PATCH", `/api/v1/projects/${projectId}/models/${id}`, body),
  );
}

export function useDeleteModel(projectId: string) {
  return useModelMutation(projectId, (id: string) => api<void>("DELETE", `/api/v1/projects/${projectId}/models/${id}`));
}
