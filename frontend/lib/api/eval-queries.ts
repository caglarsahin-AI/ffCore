"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema-09";

// Evaluation calls (09 contract, types generated from backend/openapi/09.yaml).
type S = components["schemas"];
export type Suite = S["SuiteOut"];
export type SuiteCreate = S["SuiteCreate"];
export type SuiteUpdate = S["SuiteUpdate"];
export type ScorerConfig = S["ScorerConfig"];
export type ScorerName = ScorerConfig["name"];
export type EvalRun = S["EvalRunOut"];
export type EvalRunStatus = EvalRun["status"];
export type Compare = S["CompareOut"];
export type CompareItem = S["CompareItem"];
export type CompareChange = CompareItem["change"];
export type MetricDiff = S["MetricDiff"];
export type FromRunItem = S["FromRunItem"];
export type FromRunOut = S["FromRunOut"];
export type ExpectedOutput = S["ExpectedOutput"];

export const EVAL_RUN_STATUSES = ["queued", "running", "completed", "failed", "cancelled"] as const satisfies readonly EvalRunStatus[];
export const SCORER_NAMES = [
  "contains",
  "regex",
  "json_schema",
  "cites_source",
  "semantic",
  "llm_judge",
  "sql_result",
  "latency_cost",
] as const satisfies readonly ScorerName[];
export const COMPARE_CHANGES = ["fixed", "regressed", "same", "not_comparable", "only_a", "only_b"] as const satisfies readonly CompareChange[];

const LIVE: ReadonlySet<EvalRunStatus> = new Set(["queued", "running"]);
export function isLiveEvalRun(status: EvalRunStatus): boolean {
  return LIVE.has(status);
}
// While the stream is not followed (lost), a live exam is read again at this pace.
export const EVAL_POLL_MS = 3000;

const base = (projectId: string) => `/api/v1/projects/${projectId}`;

export const evalKeys = {
  all: (projectId: string) => ["projects", projectId, "eval"] as const,
  suites: (projectId: string) => ["projects", projectId, "eval", "suites"] as const,
  suite: (projectId: string, suiteId: string) => ["projects", projectId, "eval", "suites", suiteId] as const,
  runs: (projectId: string, suiteId: string) => ["projects", projectId, "eval", "suites", suiteId, "runs"] as const,
  run: (projectId: string, evalRunId: string) => ["projects", projectId, "eval", "run", evalRunId] as const,
  compare: (projectId: string, a: string, b: string) => ["projects", projectId, "eval", "compare", a, b] as const,
};

export function useSuites(projectId: string) {
  return useQuery({
    queryKey: evalKeys.suites(projectId),
    queryFn: () => api<S["SuiteList"]>("GET", `${base(projectId)}/eval-suites`).then((r) => r.items),
  });
}

export function useSuite(projectId: string, suiteId: string) {
  return useQuery({
    queryKey: evalKeys.suite(projectId, suiteId),
    queryFn: () => api<Suite>("GET", `${base(projectId)}/eval-suites/${suiteId}`),
  });
}

export function useSuiteRuns(projectId: string, suiteId: string) {
  return useQuery({
    queryKey: evalKeys.runs(projectId, suiteId),
    queryFn: () => api<S["EvalRunList"]>("GET", `${base(projectId)}/eval-suites/${suiteId}/runs`).then((r) => r.items),
    // A list with a live exam refreshes until every exam has ended.
    refetchInterval: (q) => (q.state.data?.some((r) => isLiveEvalRun(r.status)) ? EVAL_POLL_MS : false),
  });
}

// `poll`: read a live exam again while its stream is not followed (stream lost).
export function useEvalRun(projectId: string, evalRunId: string, poll = false) {
  return useQuery({
    queryKey: evalKeys.run(projectId, evalRunId),
    queryFn: () => api<EvalRun>("GET", `${base(projectId)}/eval-runs/${evalRunId}`),
    refetchInterval: (q) => (poll && q.state.data && isLiveEvalRun(q.state.data.status) ? EVAL_POLL_MS : false),
  });
}

// Both ids are needed; the backend answers 422 for a missing one (r1 MAJOR-2), so it is not called.
export function useCompare(projectId: string, a: string | null, b: string | null) {
  return useQuery({
    queryKey: evalKeys.compare(projectId, a ?? "", b ?? ""),
    queryFn: () => api<Compare>("GET", `${base(projectId)}/eval-runs/compare?${new URLSearchParams({ a: a ?? "", b: b ?? "" })}`),
    enabled: Boolean(a && b),
    retry: false,
  });
}

function useEvalMutation<T, R>(projectId: string, call: (input: T) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () => void client.invalidateQueries({ queryKey: evalKeys.all(projectId) }),
  });
}

export function useCreateSuite(projectId: string) {
  return useEvalMutation(projectId, (body: SuiteCreate) => api<Suite>("POST", `${base(projectId)}/eval-suites`, body));
}

export function useUpdateSuite(projectId: string, suiteId: string) {
  return useEvalMutation(projectId, (body: SuiteUpdate) => api<Suite>("PATCH", `${base(projectId)}/eval-suites/${suiteId}`, body));
}

export function useDeleteSuite(projectId: string) {
  return useEvalMutation(projectId, (suiteId: string) => api<undefined>("DELETE", `${base(projectId)}/eval-suites/${suiteId}`));
}

export function useStartEvalRun(projectId: string, suiteId: string) {
  return useEvalMutation(projectId, (agentVersionId: string) =>
    api<EvalRun>("POST", `${base(projectId)}/eval-suites/${suiteId}/run?${new URLSearchParams({ agent_version_id: agentVersionId })}`),
  );
}

export function useCancelEvalRun(projectId: string) {
  return useEvalMutation(projectId, (evalRunId: string) => api<EvalRun>("POST", `${base(projectId)}/eval-runs/${evalRunId}/cancel`));
}

export function useItemFromRun(projectId: string) {
  return useEvalMutation(projectId, ({ suiteId, runId, body }: { suiteId: string; runId: string; body: FromRunItem }) =>
    api<FromRunOut>("POST", `${base(projectId)}/eval-suites/${suiteId}/items/from-run/${runId}`, body),
  );
}

// Raw stream response for lib/eval-stream.ts (GET …/stream: `progress` until the exam ends, then
// `done`). Not thrown on failure: the follower decides how often to reopen and reports a lost stream.
export function openEvalStream(projectId: string, evalRunId: string, signal?: AbortSignal): Promise<Response> {
  return fetch(`${base(projectId)}/eval-runs/${evalRunId}/stream`, {
    credentials: "same-origin",
    headers: { accept: "text/event-stream" },
    signal,
  });
}
