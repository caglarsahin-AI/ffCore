import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { vi } from "vitest";

import { SessionProvider } from "@/components/session-provider";
import type { AccessMode, Role } from "@/lib/access";
import en from "@/messages/en.json";

// Shared fetch stub for the 10c-2 governance component tests: answers by "METHOD path" (query
// string left out) and records every call with its parsed body.

export type Call = { method: string; path: string; search: URLSearchParams; body: unknown };
export type Handler = (call: Call) => unknown;

export const json = (body: unknown, status = 200) => new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

export const refusal = (status: number, code: string) => json({ error: { code, type: "invalid_request_error", message: code } }, status);

export function stubApi(handlers: Record<string, Handler | unknown>) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(typeof input === "string" ? input : input.toString(), "http://console");
      const call: Call = { method: init?.method ?? "GET", path: url.pathname, search: url.searchParams, body: init?.body ? JSON.parse(String(init.body)) : undefined };
      calls.push(call);
      const handler = handlers[`${call.method} ${call.path}`];
      if (handler === undefined) return json({ error: { code: "not_stubbed", type: "test", message: `${call.method} ${call.path}` } }, 599);
      const answer = typeof handler === "function" ? (handler as Handler)(call) : handler;
      if (answer instanceof Response) return answer;
      return answer === null ? new Response(null, { status: 204 }) : json(answer);
    }),
  );
  return calls;
}

export const quietClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

export const P = "/api/v1/projects/p1";

export function apiKey(over: Record<string, unknown> = {}) {
  return {
    id: "k1",
    project_id: "p1",
    name: "ci",
    key_prefix: "ffk_ab12",
    scopes: ["agents"],
    acl_role: "analyst",
    allowed_cidrs: [],
    expires_at: null,
    last_used_at: null,
    revoked_at: null,
    created_by: "u1",
    created_at: "2026-11-17T08:00:00Z",
    ...over,
  };
}

export function quota(over: Record<string, unknown> = {}) {
  return {
    id: "q1",
    project_id: "p1",
    scope_type: "project",
    scope_id: "p1",
    label: "Daily cap",
    priority: 100,
    windows: { rpm: null, rph: null, rpd: 1000, rpm_month: null, concurrent: null },
    tokens: { tpm: null, tpd: null, tpm_month: null, max_input: null, max_output: null, max_total: null },
    budget: { daily_usd: null, monthly_usd: null },
    action: "warn",
    is_active: true,
    activate_at: null,
    created_by: "u1",
    created_at: "2026-11-17T08:00:00Z",
    updated_at: "2026-11-17T08:00:00Z",
    ...over,
  };
}

export function alert(over: Record<string, unknown> = {}) {
  return {
    id: "a1",
    rule_id: "r1",
    project_id: "p1",
    kind: "quota_warn",
    fired_at: "2026-11-17T09:00:00Z",
    severity: "warning",
    payload: { quota_id: "q1", scope_type: "project", window: "rpd", limit: "1", used: "2" },
    acked_by: null,
    acked_at: null,
    ...over,
  };
}

export function rule(over: Record<string, unknown> = {}) {
  return {
    id: "r1",
    project_id: "p1",
    kind: "quota_warn",
    channel: "ui",
    params: {},
    recipients: [],
    is_active: true,
    created_by: "u1",
    created_at: "2026-11-17T08:00:00Z",
    ...over,
  };
}

// One project "p1" with the given role and access mode; `superadmin` for installation screens.
export function renderGov(role: Role, access: AccessMode, children: React.ReactNode, { superadmin = false, client = quietClient() } = {}) {
  const me = {
    user: { id: "u1", email: "a@example.org", full_name: "A", is_superadmin: superadmin },
    role,
    access,
    memberships: [{ project_id: "p1", project_key: "alpha", role, access }],
  };
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={en} timeZone="UTC">
        <SessionProvider value={{ me, projectId: "p1" }}>{children}</SessionProvider>
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}
