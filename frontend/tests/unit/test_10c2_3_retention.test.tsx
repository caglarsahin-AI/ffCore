// @vitest-environment jsdom
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import RetentionPage from "@/app/(console)/retention/page";

import { renderGov, stubApi } from "./gov-support";

// 10c-2 D6 (FOLLOWUP-130): retention is the installation's (superadmin). The dry run shows what
// would go; the real run deletes, ignores RETENTION_DRY_RUN, and only starts from a confirmation
// dialog that says so. Policies are edited per data class; past runs are listed.

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const POLICY = { data_class: "telemetry", project_id: null, keep_days: 30, min_days: 7, max_days: 365, expiry_behavior: "delete", source: "default", updated_at: "2026-11-17T08:00:00Z", updated_by: "seed" };
const RESULT = { data_class: "telemetry", project_id: null, cutoff: "2026-10-18T00:00:00Z", counts: { run_events: 12 }, status: "ok", error_code: null };
const API = {
  "GET /api/v1/retention/policies": { dry_run_default: true, audit_drop_enabled: false, data: [POLICY, { ...POLICY, project_id: "p1", keep_days: 14, source: "override" }] },
  "GET /api/v1/retention/runs": { data: [{ ...RESULT, id: "x1", ts: "2026-11-16T03:00:00Z", trigger: "schedule", dry_run: true, actor_id: "system" }] },
  "POST /api/v1/retention/dry-run": { dry_run: true, data: [RESULT] },
  "POST /api/v1/retention/run": { dry_run: false, data: [RESULT] },
  "PUT /api/v1/retention/policies/telemetry": { ...POLICY, keep_days: 60 },
};

describe("test_10c2_3_retention", () => {
  it("shows the policies, the dry-run default and past runs", async () => {
    stubApi(API);
    renderGov("admin", "edit", <RetentionPage />, { superadmin: true });
    expect((await screen.findByTestId("retention-dry-run-default")).textContent).toMatch(/dry run/i);
    const rows = within(screen.getByTestId("retention-policies")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    expect(within(screen.getByTestId("retention-runs")).getByText("schedule")).toBeTruthy();
  });

  it("shows what a dry run would delete", async () => {
    const calls = stubApi(API);
    renderGov("admin", "edit", <RetentionPage />, { superadmin: true });
    fireEvent.click(await screen.findByTestId("retention-dry-run"));
    const result = await screen.findByTestId("retention-result");
    expect(result.dataset.dryRun).toBe("true");
    expect(within(result).getByText(/run_events/)).toBeTruthy();
    expect(calls.some((c) => c.path === "/api/v1/retention/run")).toBe(false);
  });

  it("starts the real deletion only from the confirmation, which says the dry-run setting does not apply", async () => {
    const calls = stubApi(API);
    renderGov("admin", "edit", <RetentionPage />, { superadmin: true });
    fireEvent.click(await screen.findByTestId("retention-run"));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog.textContent).toContain("RETENTION_DRY_RUN");
    fireEvent.click(within(dialog).getByTestId("retention-run-cancel"));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    expect(calls.some((c) => c.path === "/api/v1/retention/run")).toBe(false);
    fireEvent.click(screen.getByTestId("retention-run"));
    fireEvent.click(within(await screen.findByRole("alertdialog")).getByTestId("retention-run-confirm"));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/api/v1/retention/run")).toBe(true));
    expect((await screen.findByTestId("retention-result")).dataset.dryRun).toBe("false");
  });

  it("saves a data class's keep days for the installation", async () => {
    const calls = stubApi(API);
    renderGov("admin", "edit", <RetentionPage />, { superadmin: true });
    const row = (await screen.findAllByTestId("policy-telemetry-default"))[0];
    fireEvent.click(within(row).getByTestId("policy-edit"));
    fireEvent.change(within(row).getByLabelText(/keep days/i), { target: { value: "60" } });
    fireEvent.click(within(row).getByTestId("policy-save"));
    await waitFor(() => expect(calls.some((c) => c.method === "PUT")).toBe(true));
    expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ keep_days: 60, project_id: null });
  });
});
