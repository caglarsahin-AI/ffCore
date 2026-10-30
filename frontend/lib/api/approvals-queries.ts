"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

import type { components } from "@/lib/api/schema-07";

// Approval queue calls (07 contract, types generated from backend/openapi/07.yaml).
type S = components["schemas"];
export type ApprovalStatus = S["ApprovalStatus"];
export type ApproverRole = S["ApproverRole"];
export type Approval = S["ApprovalOut"];
export type ApprovalDecided = S["ApprovalDecided"];
export type Decision = "approve" | "reject";

export const APPROVAL_STATUSES = ["pending", "approved", "rejected", "expired"] as const satisfies readonly ApprovalStatus[];
export const APPROVALS_POLL_MS = 10_000;

const base = (projectId: string) => `/api/v1/projects/${projectId}/approvals`;

export const approvalKeys = {
  all: (projectId: string) => ["projects", projectId, "approvals"] as const,
  list: (projectId: string, status: ApprovalStatus | null) => ["projects", projectId, "approvals", "list", status] as const,
  count: (projectId: string) => ["projects", projectId, "approvals", "count"] as const,
  one: (projectId: string, id: string) => ["projects", projectId, "approvals", "one", id] as const,
};

export function useApprovals(projectId: string, status: ApprovalStatus | null) {
  return useQuery({
    queryKey: approvalKeys.list(projectId, status),
    queryFn: () => api<S["ApprovalList"]>("GET", `${base(projectId)}${status ? `?status=${status}` : ""}`).then((r) => r.data),
    refetchInterval: status === "pending" ? APPROVALS_POLL_MS : false,
  });
}

// Pending count for the sidebar badge; refreshed on an interval and after every decision.
export function usePendingApprovalCount(projectId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: approvalKeys.count(projectId ?? "none"),
    queryFn: () => api<S["ApprovalCount"]>("GET", `${base(projectId!)}/count?status=pending`).then((r) => r.count),
    enabled: enabled && projectId !== null,
    refetchInterval: APPROVALS_POLL_MS,
  });
}

export function useApproval(projectId: string, id: string) {
  return useQuery({ queryKey: approvalKeys.one(projectId, id), queryFn: () => api<Approval>("GET", `${base(projectId)}/${id}`) });
}

export function useDecideApproval(projectId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision, note }: { id: string; decision: Decision; note: string | null }) =>
      api<ApprovalDecided>("POST", `${base(projectId)}/${id}/${decision}`, { note }),
    onSuccess: () => client.invalidateQueries({ queryKey: approvalKeys.all(projectId) }),
  });
}
