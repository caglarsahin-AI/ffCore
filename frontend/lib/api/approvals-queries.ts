"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";

// Approval queue calls (07). TEMPORARY TYPES: backend/openapi/07.yaml arrives with the 07 PR
// (K-10bp2-0002); until then these mirror feat/07-approvals api/approvals_schemas.py field for
// field. When the spec lands they are replaced by `components` from lib/api/schema-07.d.ts and
// the spec joins check:api (PR note; no PR-HAZIR before that).
export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired";
export type ApproverRole = "analyst" | "developer" | "admin";
export type Approval = {
  id: string;
  project_id: string;
  run_id: string;
  tool_call_id: string;
  action: string;
  tool_key: string | null;
  arguments: Record<string, unknown>;
  reason_from_model: string | null;
  status: ApprovalStatus;
  assigned_role: ApproverRole;
  requested_at: string;
  expires_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_note: string | null;
  can_decide: boolean;
};
export type ApprovalDecided = Approval & { stream_after: string | null };
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
    queryFn: () => api<{ data: Approval[] }>("GET", `${base(projectId)}${status ? `?status=${status}` : ""}`).then((r) => r.data),
    refetchInterval: status === "pending" ? APPROVALS_POLL_MS : false,
  });
}

// Pending count for the sidebar badge; refreshed on an interval and after every decision.
export function usePendingApprovalCount(projectId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: approvalKeys.count(projectId ?? "none"),
    queryFn: () => api<{ status: ApprovalStatus; count: number }>("GET", `${base(projectId!)}/count?status=pending`).then((r) => r.count),
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
