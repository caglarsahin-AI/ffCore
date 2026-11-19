// @vitest-environment jsdom
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import OverviewPage from "@/app/(console)/overview/page";
import UsagePage from "@/app/(console)/usage/page";
import { byDay, byModel, lastDays } from "@/lib/usage";

import { P, renderGov, stubApi } from "./gov-support";

// 10c-2 D2: the overview shows the project's usage of the last 30 days (03c usage), pending
// approvals and, from developer up, open alerts, plus the 10 newest runs. There is no run-count
// endpoint, so no run total is shown (KARARLAR "10c-2 plan kararları" S5: a count read from a
// capped list would be wrong). Usage: daily tokens and cost per project, by day and by model.

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const ROWS = [
  { date: "2026-11-16", model: "chat", api_key_id: null, user_id: "u1", input_tokens: 100, output_tokens: 50, cost_usd: "0.0100", requests: 2, unpriced_requests: 0 },
  { date: "2026-11-16", model: "embed", api_key_id: "k1", user_id: null, input_tokens: 400, output_tokens: 0, cost_usd: "0.0020", requests: 4, unpriced_requests: 0 },
  { date: "2026-11-17", model: "chat", api_key_id: "k1", user_id: null, input_tokens: 300, output_tokens: 150, cost_usd: "0.0300", requests: 6, unpriced_requests: 1 },
];
const USAGE = (from = "2026-10-19", to = "2026-11-17") => ({
  project_id: "p1",
  date_from: from,
  date_to: to,
  totals: { input_tokens: 800, output_tokens: 200, cost_usd: "0.0420", requests: 12, unpriced_requests: 1 },
  data: ROWS,
});
const RUN = (id: string) => ({ id, project_id: "p1", agent_id: "a1", agent_version_id: "v1", status: "completed", channel: "test", input: `question ${id}`, queued_at: "2026-11-17T08:00:00Z" });

const API = {
  [`GET ${P}/usage`]: (c: { search: URLSearchParams }) => USAGE(c.search.get("date_from") ?? "", c.search.get("date_to") ?? ""),
  [`GET ${P}/approvals/count`]: { status: "pending", count: 3 },
  [`GET ${P}/alerts/count`]: { open: 2 },
  [`GET ${P}/runs`]: { items: [RUN("r1"), RUN("r2")] },
};

describe("test_10c2_8_usage_helpers", () => {
  it("counts the last N calendar days, today included (UTC)", () => {
    expect(lastDays(30, new Date("2026-11-17T23:30:00Z"))).toEqual({ from: "2026-10-19", to: "2026-11-17" });
    expect(lastDays(1, new Date("2026-11-17T00:00:00Z"))).toEqual({ from: "2026-11-17", to: "2026-11-17" });
  });

  it("groups usage rows by day and by model", () => {
    expect(byDay(ROWS)).toEqual([
      { key: "2026-11-16", input_tokens: 500, output_tokens: 50, cost_usd: 0.012, requests: 6, unpriced_requests: 0 },
      { key: "2026-11-17", input_tokens: 300, output_tokens: 150, cost_usd: 0.03, requests: 6, unpriced_requests: 1 },
    ]);
    expect(byModel(ROWS).map((r) => [r.key, r.requests])).toEqual([
      ["chat", 8],
      ["embed", 4],
    ]);
  });
});

describe("test_10c2_8_overview", () => {
  it("shows usage, pending approvals and the newest runs to an analyst, without alerts or a run total", async () => {
    const calls = stubApi(API);
    renderGov("analyst", "edit", <OverviewPage />);
    await waitFor(() => expect(screen.getByTestId("overview-requests").textContent).toContain("12"));
    expect(screen.getByTestId("overview-cost").textContent).toContain("0.042");
    await waitFor(() => expect(screen.getByTestId("overview-approvals").textContent).toContain("3"));
    const runs = await screen.findByTestId("overview-runs");
    expect(within(runs).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual(["/runs/r1", "/runs/r2"]);
    expect(calls.find((c) => c.path === `${P}/runs`)?.search.get("limit")).toBe("10");
    const usage = calls.find((c) => c.path === `${P}/usage`)!;
    expect(usage.search.get("date_from")).toBeTruthy();
    expect(screen.getByTestId("overview-range").textContent).toContain(usage.search.get("date_from")!);
    expect(screen.queryByTestId("overview-alerts")).toBeNull();
    expect(calls.some((c) => c.path.endsWith("/alerts/count"))).toBe(false);
    expect(screen.queryByTestId("overview-run-total")).toBeNull();
    expect(screen.getByTestId("overview-unpriced").textContent).toContain("1");
  });

  it("adds open alerts for a developer", async () => {
    stubApi(API);
    renderGov("developer", "edit", <OverviewPage />);
    await waitFor(() => expect(screen.getByTestId("overview-alerts").textContent).toContain("2"));
  });
});

describe("test_10c2_8_usage", () => {
  it("shows usage by day and by model for the chosen range", async () => {
    const calls = stubApi(API);
    renderGov("admin", "edit", <UsagePage />);
    const days = await screen.findByTestId("usage-by-day");
    expect(within(days).getAllByRole("row")).toHaveLength(3);
    expect(within(screen.getByTestId("usage-by-model")).getByText("embed")).toBeTruthy();
    expect(screen.getByTestId("usage-totals").textContent).toContain("12");
    fireEvent.change(screen.getByLabelText(/^from/i), { target: { value: "2026-11-01" } });
    await waitFor(() => expect(calls.at(-1)?.search.get("date_from")).toBe("2026-11-01"));
  });

  it("refuses a range that ends before it starts, without asking the backend", async () => {
    const calls = stubApi(API);
    renderGov("admin", "edit", <UsagePage />);
    await screen.findByTestId("usage-by-day");
    const before = calls.length;
    fireEvent.change(screen.getByLabelText(/^from/i), { target: { value: "2099-01-01" } });
    expect(await screen.findByText(/ends before it starts/i)).toBeTruthy();
    expect(calls.length).toBe(before);
  });
});
