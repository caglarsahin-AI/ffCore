"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { components } from "@/lib/api/schema-03c";

// Governance calls (03c contract, types generated from backend/openapi/03c.yaml): API keys,
// quotas, usage, alerts, notification settings and retention. 10c-2.
type S = components["schemas"];
export type ApiKey = S["ApiKeyOut"];
export type ApiKeyCreate = S["ApiKeyCreate"];
export type ApiKeyCreated = S["ApiKeyCreated"];
export type ApiKeyScope = S["ApiKeyScope"];
export type ApiKeyAclRole = S["ApiKeyAclRole"];
export type Quota = S["QuotaOut"];
export type QuotaCreate = S["QuotaCreate"];
export type QuotaUpdate = S["QuotaUpdate"];
export type QuotaScope = S["QuotaScope"];
export type QuotaAction = S["QuotaAction"];
export type QuotaWindows = S["QuotaWindows"];
export type QuotaTokens = S["QuotaTokens"];
export type Usage = S["UsageSummary"];
export type UsageRow = S["UsageRow"];
export type AlertKind = S["AlertKind"];
export type AlertChannel = S["AlertChannel"];
export type AlertRule = S["AlertRuleOut"];
export type AlertRuleCreate = S["AlertRuleCreate"];
export type AlertRuleUpdate = S["AlertRuleUpdate"];
export type Alert = S["AlertOut"];
export type NotificationSettings = S["NotificationSettingsOut"];
export type NotificationSettingsIn = S["NotificationSettingsIn"];
export type NotificationTest = S["NotificationTest"];
export type NotificationTestResult = S["NotificationTestResult"];
export type DataClass = S["DataClass"];
export type Policy = S["PolicyOut"];
export type PolicyList = S["PolicyList"];
export type RunResults = S["RunResults"];
export type RunRecord = S["RunRecord"];

export const API_KEY_SCOPES = ["chat_direct", "agents", "kb_search", "tools_invoke", "impersonate"] as const satisfies readonly ApiKeyScope[];
export const API_KEY_ACL_ROLES = ["analyst", "developer", "admin"] as const satisfies readonly ApiKeyAclRole[];
export const QUOTA_SCOPES = ["project", "api_key", "user"] as const satisfies readonly QuotaScope[];
export const QUOTA_ACTIONS = ["block", "warn"] as const satisfies readonly QuotaAction[];
export const QUOTA_WINDOWS = ["rpm", "rph", "rpd", "rpm_month", "concurrent"] as const satisfies readonly (keyof QuotaWindows)[];
export const QUOTA_TOKENS = ["tpm", "tpd", "tpm_month", "max_input", "max_output", "max_total"] as const satisfies readonly (keyof QuotaTokens)[];
export const ALERT_CHANNELS = ["ui", "email", "webhook"] as const satisfies readonly AlertChannel[];
export const ALERT_LIST_CAP = 500; // backend: the newest 500 alerts (api/alerts.py _alerts)
// The open-alert badge refreshes at this pace (alerts are fired by the worker, not by this page).
export const ALERT_COUNT_POLL_MS = 30_000;

// Alerts, alert rules and notification settings exist per project and for the installation
// (superadmin): "tenant" uses the routes without a project.
export type AlertScope = { kind: "project"; projectId: string } | { kind: "tenant" };
const scopeBase = (scope: AlertScope) => (scope.kind === "project" ? `/api/v1/projects/${scope.projectId}` : "/api/v1");
const scopeKey = (scope: AlertScope) => (scope.kind === "project" ? scope.projectId : "tenant");

const base = (projectId: string) => `/api/v1/projects/${projectId}`;

export const govKeys = {
  apiKeys: (projectId: string, all: boolean) => ["projects", projectId, "api-keys", all] as const,
  apiKeysAll: (projectId: string) => ["projects", projectId, "api-keys"] as const,
  quotas: (projectId: string) => ["projects", projectId, "quotas"] as const,
  usage: (projectId: string, from: string, to: string) => ["projects", projectId, "usage", from, to] as const,
  alertKinds: () => ["alert-kinds"] as const,
  alertsRoot: (scope: AlertScope) => ["alerts", scopeKey(scope)] as const,
  alerts: (scope: AlertScope) => ["alerts", scopeKey(scope), "list"] as const,
  alertCount: (scope: AlertScope) => ["alerts", scopeKey(scope), "count"] as const,
  alertRules: (scope: AlertScope) => ["alerts", scopeKey(scope), "rules"] as const,
  notifications: (scope: AlertScope) => ["alerts", scopeKey(scope), "notification-settings"] as const,
  retention: () => ["retention"] as const,
  retentionPolicies: () => ["retention", "policies"] as const,
  retentionRuns: () => ["retention", "runs"] as const,
};

function useInvalidating<T, R>(keys: readonly (readonly unknown[])[], call: (input: T) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: () => Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

// --- API keys ------------------------------------------------------------------------------------

// `all`: every key of the project (a project admin); otherwise the caller's own keys.
export function useApiKeys(projectId: string, all: boolean) {
  return useQuery({
    queryKey: govKeys.apiKeys(projectId, all),
    queryFn: () => api<S["ApiKeyList"]>("GET", `${base(projectId)}/api-keys${all ? "?all=true" : ""}`).then((r) => r.data),
  });
}

export function useCreateApiKey(projectId: string) {
  return useInvalidating([govKeys.apiKeysAll(projectId)], (body: ApiKeyCreate) => api<ApiKeyCreated>("POST", `${base(projectId)}/api-keys`, body));
}

export function useRevokeApiKey(projectId: string) {
  return useInvalidating([govKeys.apiKeysAll(projectId)], (keyId: string) => api<ApiKey>("POST", `${base(projectId)}/api-keys/${keyId}/revoke`));
}

// --- Quotas --------------------------------------------------------------------------------------

export function useQuotas(projectId: string) {
  return useQuery({
    queryKey: govKeys.quotas(projectId),
    queryFn: () => api<S["QuotaList"]>("GET", `${base(projectId)}/quotas`).then((r) => r.data),
  });
}

export function useCreateQuota(projectId: string) {
  return useInvalidating([govKeys.quotas(projectId)], (body: QuotaCreate) => api<Quota>("POST", `${base(projectId)}/quotas`, body));
}

export function useUpdateQuota(projectId: string) {
  return useInvalidating([govKeys.quotas(projectId)], ({ id, body }: { id: string; body: QuotaUpdate }) => api<Quota>("PATCH", `${base(projectId)}/quotas/${id}`, body));
}

export function useDeleteQuota(projectId: string) {
  return useInvalidating([govKeys.quotas(projectId)], (id: string) => api<void>("DELETE", `${base(projectId)}/quotas/${id}`));
}

// --- Usage ---------------------------------------------------------------------------------------

// Dates are calendar days (YYYY-MM-DD, UTC as usage_daily); both ends included.
export function useUsage(projectId: string, from: string, to: string) {
  return useQuery({
    queryKey: govKeys.usage(projectId, from, to),
    queryFn: () => api<Usage>("GET", `${base(projectId)}/usage?${new URLSearchParams({ date_from: from, date_to: to })}`),
  });
}

// --- Alerts --------------------------------------------------------------------------------------

export function useAlertKinds() {
  return useQuery({
    queryKey: govKeys.alertKinds(),
    queryFn: () => api<S["AlertKinds"]>("GET", "/api/v1/alert-kinds").then((r) => r.kinds),
    staleTime: Infinity,
  });
}

export function useAlerts(scope: AlertScope) {
  return useQuery({
    queryKey: govKeys.alerts(scope),
    queryFn: () => api<S["AlertList"]>("GET", `${scopeBase(scope)}/alerts`).then((r) => r.data),
  });
}

export function useAlertCount(scope: AlertScope, enabled = true) {
  return useQuery({
    queryKey: govKeys.alertCount(scope),
    queryFn: () => api<S["AlertCount"]>("GET", `${scopeBase(scope)}/alerts/count`).then((r) => r.open),
    enabled,
    refetchInterval: ALERT_COUNT_POLL_MS,
  });
}

export function useAckAlert(scope: AlertScope) {
  return useInvalidating([govKeys.alertsRoot(scope)], (alertId: string) => api<Alert>("POST", `${scopeBase(scope)}/alerts/${alertId}/ack`));
}

export function useAlertRules(scope: AlertScope) {
  return useQuery({
    queryKey: govKeys.alertRules(scope),
    queryFn: () => api<S["AlertRuleList"]>("GET", `${scopeBase(scope)}/alert-rules`).then((r) => r.data),
  });
}

export function useCreateAlertRule(scope: AlertScope) {
  return useInvalidating([govKeys.alertRules(scope)], (body: AlertRuleCreate) => api<AlertRule>("POST", `${scopeBase(scope)}/alert-rules`, body));
}

export function useUpdateAlertRule(scope: AlertScope) {
  return useInvalidating([govKeys.alertRules(scope)], ({ id, body }: { id: string; body: AlertRuleUpdate }) => api<AlertRule>("PATCH", `${scopeBase(scope)}/alert-rules/${id}`, body));
}

export function useDeleteAlertRule(scope: AlertScope) {
  return useInvalidating([govKeys.alertRules(scope)], (id: string) => api<void>("DELETE", `${scopeBase(scope)}/alert-rules/${id}`));
}

export function useNotificationSettings(scope: AlertScope, enabled = true) {
  return useQuery({
    queryKey: govKeys.notifications(scope),
    queryFn: () => api<NotificationSettings>("GET", `${scopeBase(scope)}/notification-settings`),
    enabled,
  });
}

export function useSaveNotificationSettings(scope: AlertScope) {
  return useInvalidating([govKeys.notifications(scope)], (body: NotificationSettingsIn) => api<NotificationSettings>("PUT", `${scopeBase(scope)}/notification-settings`, body));
}

export function useTestNotification(scope: AlertScope) {
  return useMutation({ mutationFn: (body: NotificationTest) => api<NotificationTestResult>("POST", `${scopeBase(scope)}/notifications/test`, body) });
}

// --- Retention (installation, superadmin) ---------------------------------------------------------

export function useRetentionPolicies() {
  return useQuery({ queryKey: govKeys.retentionPolicies(), queryFn: () => api<PolicyList>("GET", "/api/v1/retention/policies") });
}

export function useRetentionRuns() {
  return useQuery({ queryKey: govKeys.retentionRuns(), queryFn: () => api<S["RunRecords"]>("GET", "/api/v1/retention/runs").then((r) => r.data) });
}

export function useSavePolicy() {
  return useInvalidating([govKeys.retentionPolicies()], ({ dataClass, keepDays, projectId }: { dataClass: DataClass; keepDays: number; projectId: string | null }) =>
    api<Policy>("PUT", `/api/v1/retention/policies/${dataClass}`, { keep_days: keepDays, project_id: projectId }),
  );
}

export function useDeleteOverride() {
  return useInvalidating([govKeys.retentionPolicies()], ({ dataClass, projectId }: { dataClass: DataClass; projectId: string }) =>
    api<void>("DELETE", `/api/v1/retention/policies/${dataClass}/overrides/${projectId}`),
  );
}

// `dry: true` counts what would go; `dry: false` is the real deletion (RETENTION_DRY_RUN does not
// apply to it, FOLLOWUP-130). Both are recorded as runs.
export function useRetentionRun() {
  return useInvalidating([govKeys.retentionRuns()], (dry: boolean) => api<RunResults>("POST", `/api/v1/retention/${dry ? "dry-run" : "run"}`));
}
