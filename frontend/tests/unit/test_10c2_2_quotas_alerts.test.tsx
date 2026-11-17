// @vitest-environment jsdom
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AlertsPage from "@/app/(console)/alerts/page";
import QuotasPage from "@/app/(console)/quotas/page";
import { AlertBadge } from "@/components/governance/alert-badge";

import { P, alert, quota, renderGov, rule, stubApi } from "./gov-support";

// 10c-2 D4/D5: quotas show the limits as set and their last recorded warning (03c quota_warn
// alert); only limits that were filled are sent. Alerts: open ones can be acknowledged, acked ones
// are history; rules use the kinds the backend emits; the header badge counts open alerts.

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const QUOTA_API = {
  [`GET ${P}/quotas`]: { data: [quota()] },
  [`GET ${P}/alerts`]: { data: [alert()] },
  [`GET ${P}/api-keys`]: { data: [] },
};

describe("test_10c2_2_quotas", () => {
  it("shows each limit as set and the quota's last warning", async () => {
    stubApi(QUOTA_API);
    renderGov("admin", "edit", <QuotasPage />);
    const row = await screen.findByTestId("quota-q1");
    expect(within(row).getByTestId("quota-limits").textContent).toContain("rpd");
    expect(within(row).getByTestId("quota-limits").textContent).toContain("1,000");
    await waitFor(() => expect(within(row).getByTestId("quota-exceeded").textContent).toMatch(/rpd.*2.*1/));
  });

  it("sends only the limits that were filled", async () => {
    const calls = stubApi({ ...QUOTA_API, [`POST ${P}/quotas`]: quota({ id: "q2" }) });
    renderGov("admin", "edit", <QuotasPage />);
    await screen.findByTestId("quota-q1");
    fireEvent.click(screen.getByTestId("quota-add"));
    const form = screen.getByTestId("quota-form");
    fireEvent.change(within(form).getByLabelText(/^label/i), { target: { value: "Warn early" } });
    fireEvent.change(within(form).getByLabelText(/^action/i), { target: { value: "warn" } });
    fireEvent.change(within(form).getByLabelText(/requests per day/i), { target: { value: "1" } });
    fireEvent.submit(form);
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const body = calls.find((c) => c.method === "POST")?.body as Record<string, unknown>;
    expect(body).toMatchObject({ scope_type: "project", scope_id: null, label: "Warn early", action: "warn", is_active: true });
    expect(body.windows).toEqual({ rpm: null, rph: null, rpd: 1, rpm_month: null, concurrent: null });
    expect(body.tokens).toEqual({ tpm: null, tpd: null, tpm_month: null, max_input: null, max_output: null, max_total: null });
    expect(body.budget).toEqual({ daily_usd: null, monthly_usd: null });
  });

  it("does not send a quota without any limit", async () => {
    const calls = stubApi(QUOTA_API);
    renderGov("admin", "edit", <QuotasPage />);
    await screen.findByTestId("quota-q1");
    fireEvent.click(screen.getByTestId("quota-add"));
    fireEvent.change(within(screen.getByTestId("quota-form")).getByLabelText(/^label/i), { target: { value: "Nothing" } });
    fireEvent.submit(screen.getByTestId("quota-form"));
    expect(await screen.findByText(/at least one limit/i)).toBeTruthy();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("shows a developer the quotas with editing disabled for admins only", async () => {
    stubApi(QUOTA_API);
    renderGov("developer", "edit", <QuotasPage />);
    await screen.findByTestId("quota-q1");
    const add = screen.getByTestId("quota-add") as HTMLButtonElement;
    expect(add.disabled).toBe(true);
    expect(add.closest("[data-needs-role]")?.getAttribute("data-needs-role")).toBe("admin");
  });
});

describe("test_10c2_2_alerts", () => {
  const ALERTS_API = {
    [`GET ${P}/alerts`]: { data: [alert(), alert({ id: "a2", kind: "budget_threshold", acked_by: "u1", acked_at: "2026-11-17T09:30:00Z", payload: { percent: 80 } })] },
    [`GET ${P}/alert-rules`]: { data: [rule()] },
    "GET /api/v1/alert-kinds": { kinds: ["budget_threshold", "service_down", "quota_warn"] },
    [`GET ${P}/alerts/count`]: { open: 1 },
    [`GET ${P}/notification-settings`]: { project_id: "p1", smtp: null, default_webhook_url: null, from_address: null, updated_at: null, updated_by: null },
  };

  it("acknowledges an open alert; acked alerts are history", async () => {
    const calls = stubApi({ ...ALERTS_API, [`POST ${P}/alerts/a1/ack`]: alert({ acked_by: "u1", acked_at: "2026-11-17T10:00:00Z" }) });
    renderGov("developer", "edit", <AlertsPage />);
    const open = await screen.findByTestId("alerts-open");
    expect(within(open).getByTestId("alert-a1")).toBeTruthy();
    expect(within(open).queryByTestId("alert-a2")).toBeNull();
    fireEvent.click(within(open).getByTestId("alert-ack"));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === `${P}/alerts/a1/ack`)).toBe(true));
    fireEvent.click(screen.getByTestId("alerts-tab-history"));
    expect(within(await screen.findByTestId("alerts-history")).getByTestId("alert-a2")).toBeTruthy();
  });

  it("creates a rule from the kinds the backend emits; e-mail needs recipients", async () => {
    const calls = stubApi({ ...ALERTS_API, [`POST ${P}/alert-rules`]: rule({ id: "r2" }) });
    renderGov("admin", "edit", <AlertsPage />);
    fireEvent.click(await screen.findByTestId("alerts-tab-rules"));
    fireEvent.click(await screen.findByTestId("alert-rule-add"));
    const form = screen.getByTestId("alert-rule-form");
    const kind = within(form).getByLabelText(/^kind/i) as HTMLSelectElement;
    await waitFor(() => expect(Array.from(kind.options).map((o) => o.value)).toEqual(["budget_threshold", "service_down", "quota_warn"]));
    fireEvent.change(kind, { target: { value: "quota_warn" } });
    fireEvent.change(within(form).getByLabelText(/^channel/i), { target: { value: "email" } });
    fireEvent.submit(form);
    expect(await within(form).findByText(/needs at least one recipient/i)).toBeTruthy();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    fireEvent.change(within(form).getByLabelText(/^channel/i), { target: { value: "ui" } });
    fireEvent.submit(form);
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ kind: "quota_warn", channel: "ui", params: {}, recipients: [], is_active: true });
  });

  it("lets a developer see rules but not change them", async () => {
    stubApi(ALERTS_API);
    renderGov("developer", "edit", <AlertsPage />);
    fireEvent.click(await screen.findByTestId("alerts-tab-rules"));
    const add = (await screen.findByTestId("alert-rule-add")) as HTMLButtonElement;
    expect(add.disabled).toBe(true);
    expect(add.closest("[data-needs-role]")?.getAttribute("data-needs-role")).toBe("admin");
  });

  it("shows the open-alert badge to a developer, not to an analyst", async () => {
    stubApi(ALERTS_API);
    renderGov("developer", "edit", <AlertBadge />);
    await waitFor(() => expect(screen.getByTestId("alert-badge").dataset.count).toBe("1"));
    expect(screen.getByTestId("alert-badge").getAttribute("aria-label")).toMatch(/1 open alert/);
    cleanup();
    const calls = stubApi(ALERTS_API);
    renderGov("analyst", "edit", <AlertBadge />);
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByTestId("alert-badge")).toBeNull();
    expect(calls).toHaveLength(0);
  });
});
