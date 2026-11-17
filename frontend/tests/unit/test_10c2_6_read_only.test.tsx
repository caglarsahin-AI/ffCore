// @vitest-environment jsdom
import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AlertsPage from "@/app/(console)/alerts/page";
import ApiKeysPage from "@/app/(console)/api-keys/page";
import QuotasPage from "@/app/(console)/quotas/page";
import RetentionPage from "@/app/(console)/retention/page";

import { P, alert, apiKey, quota, renderGov, rule, stubApi } from "./gov-support";

// 10c-2 D7: in read mode the governance screens show the same data and every mutation control
// (marked data-write) is disabled with the read-only reason (WriteGate). The API enforces 403.

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const API = {
  [`GET ${P}/api-keys`]: { data: [apiKey()] },
  [`GET ${P}/quotas`]: { data: [quota()] },
  [`GET ${P}/alerts`]: { data: [alert()] },
  [`GET ${P}/alerts/count`]: { open: 1 },
  [`GET ${P}/alert-rules`]: { data: [rule()] },
  "GET /api/v1/alert-kinds": { kinds: ["quota_warn"] },
  [`GET ${P}/notification-settings`]: { project_id: "p1", smtp: null, default_webhook_url: null, from_address: null, updated_at: null, updated_by: null },
  "GET /api/v1/retention/policies": { dry_run_default: true, audit_drop_enabled: false, data: [] },
  "GET /api/v1/retention/runs": { data: [] },
};

async function expectAllWritesDisabled(ready: string) {
  await screen.findByTestId(ready);
  const writes = Array.from(document.querySelectorAll<HTMLButtonElement>("[data-write]"));
  expect(writes.length).toBeGreaterThan(0);
  for (const control of writes) {
    expect(control.disabled, control.dataset.testid).toBe(true);
    expect(control.closest("[data-read-only]"), control.dataset.testid).not.toBeNull();
  }
}

describe("test_10c2_6_read_only", () => {
  it.each([
    ["api keys", <ApiKeysPage key="k" />, "api-key-k1"],
    ["quotas", <QuotasPage key="q" />, "quota-q1"],
    ["retention", <RetentionPage key="r" />, "retention-policies"],
  ])("%s: every mutation control is disabled in read mode", async (_name, page, ready) => {
    stubApi(API);
    renderGov("admin", "read", page, { superadmin: true });
    await expectAllWritesDisabled(ready);
  });

  it("alerts: ack and rule controls are disabled in read mode", async () => {
    stubApi(API);
    renderGov("admin", "read", <AlertsPage />, { superadmin: true });
    await expectAllWritesDisabled("alert-a1");
    fireEvent.click(screen.getByTestId("alerts-tab-rules"));
    await expectAllWritesDisabled("alert-rule-r1");
    fireEvent.click(screen.getByTestId("alerts-tab-notifications"));
    await expectAllWritesDisabled("notification-form");
  });
});
