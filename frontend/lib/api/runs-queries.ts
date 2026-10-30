"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api } from "@/lib/api/client";
import type { components, operations } from "@/lib/api/schema-06a";

// Run calls (06a contract, types generated from backend/openapi/06a.yaml).
type S = components["schemas"];
export type Run = S["RunOut"];
export type RunEvent = S["RunEventOut"];
export type RunStatus = S["RunStatus"];
export type RunCreate = S["RunCreate"];
export type FeedbackVote = S["FeedbackRequest"]["vote"];
export type RunFilters = NonNullable<operations["list_runs_api_v1_projects__project_id__runs_get"]["parameters"]["query"]>;

export const RUN_STATUSES = [
  "queued",
  "running",
  "waiting_approval",
  "waiting_user",
  "completed",
  "failed",
  "cancelled",
  "abandoned",
] as const satisfies readonly RunStatus[];
const LIVE: ReadonlySet<RunStatus> = new Set(["queued", "running", "waiting_approval", "waiting_user"]);
export const RUNS_POLL_MS = 3000;

export function isLiveRun(status: RunStatus): boolean {
  return LIVE.has(status);
}

const base = (projectId: string) => `/api/v1/projects/${projectId}`;

export const runKeys = {
  list: (projectId: string, filters: RunFilters) => ["projects", projectId, "runs", filters] as const,
  all: (projectId: string) => ["projects", projectId, "runs"] as const,
  one: (projectId: string, runId: string) => ["projects", projectId, "run", runId] as const,
  events: (projectId: string, runId: string) => ["projects", projectId, "run", runId, "events"] as const,
};

function query(filters: RunFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, String(value));
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function useRuns(projectId: string, filters: RunFilters) {
  return useQuery({
    queryKey: runKeys.list(projectId, filters),
    queryFn: () => api<S["RunList"]>("GET", `${base(projectId)}/runs${query(filters)}`).then((r) => r.items),
    placeholderData: keepPreviousData,
  });
}

// A run that is still going refreshes until it ends; an ended run is read once.
export function useRun(projectId: string, runId: string) {
  return useQuery({
    queryKey: runKeys.one(projectId, runId),
    queryFn: () => api<Run>("GET", `${base(projectId)}/runs/${runId}`),
    refetchInterval: (q) => (q.state.data && isLiveRun(q.state.data.status) ? RUNS_POLL_MS : false),
  });
}

export function useRunEvents(projectId: string, runId: string, live: boolean) {
  return useQuery({
    queryKey: runKeys.events(projectId, runId),
    queryFn: () => api<S["RunEventList"]>("GET", `${base(projectId)}/runs/${runId}/events`).then((r) => r.items),
    refetchInterval: live ? RUNS_POLL_MS : false,
  });
}

function useRunMutation<T, R>(projectId: string, call: (input: T) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: runKeys.all(projectId) });
      void client.invalidateQueries({ queryKey: ["projects", projectId, "run"] });
    },
  });
}

export function useCancelRun(projectId: string) {
  return useRunMutation(projectId, (runId: string) => api<Run>("POST", `${base(projectId)}/runs/${runId}/cancel`));
}

export function useGiveFeedback(projectId: string) {
  return useRunMutation(projectId, ({ runId, vote, note }: { runId: string; vote: FeedbackVote; note: string | null }) =>
    api<S["FeedbackOut"]>("POST", `${base(projectId)}/runs/${runId}/feedback`, { vote, note }),
  );
}

// Raw stream responses for lib/sse.ts. A refused start (4xx/5xx JSON) is thrown as ApiError with
// the contract code, like every other call; the stream itself is read by followRunStream.
async function streamResponse(path: string, init: RequestInit): Promise<Response> {
  const response = await fetch(path, { credentials: "same-origin", ...init });
  if (response.ok) return response;
  const body: unknown = await response.json().catch(() => undefined);
  const error = (body as { error?: { code?: string; type?: string; message?: string } } | undefined)?.error;
  throw new ApiError(response.status, error?.code ?? "unexpected_response", error?.type ?? "api_error", error?.message ?? `${path} returned ${response.status}`);
}

export function startRun(projectId: string, agentKey: string, body: RunCreate, signal?: AbortSignal): Promise<Response> {
  return streamResponse(`${base(projectId)}/agents/${encodeURIComponent(agentKey)}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
}

// Reconnect after `lastEventId` (06a GET /runs/{id}/stream). Not thrown on failure: the stream
// follower decides how often to retry and reports a lost stream.
export function reconnectRun(projectId: string, runId: string, lastEventId: string | null, signal?: AbortSignal): Promise<Response> {
  const headers: Record<string, string> = { accept: "text/event-stream" };
  if (lastEventId) headers["Last-Event-ID"] = lastEventId;
  return fetch(`${base(projectId)}/runs/${runId}/stream`, { credentials: "same-origin", headers, signal });
}

// The answer to an ask_user question goes to 06a /resume; approval decisions go to 07 (D1).
export function answerQuestion(projectId: string, runId: string, answer: string): Promise<unknown> {
  return api("POST", `${base(projectId)}/runs/${runId}/resume`, { answer });
}
