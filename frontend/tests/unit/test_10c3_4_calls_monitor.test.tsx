// @vitest-environment jsdom
import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import McpServerPage from "@/app/(console)/mcp-servers/[serverId]/page";
import { CallsMonitor } from "@/components/mcp/calls-monitor";

import { refusal, renderGov, stubApi } from "./gov-support";
import { S, call, calls, server } from "./mcp-support";

// 10c-3 D3 (plan/10 "MCP İzleme", FOLLOWUP-195 NOTE-1): the server's last 24 hours (requests,
// calls that did not end ok, blocked, p50/p95 latency) and its last calls. Each call keeps its
// status and its code: `denied` is a refusal before any request left (plain code, e.g.
// openapi_path_invalid), `error` an upstream or argument error (e.g. invalid_arguments,
// upstream_http_404), `blocked` a guardrail block. A call of an agent run links to the run.

vi.mock("next/navigation", () => ({
  useParams: () => ({ serverId: "s1" }),
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/mcp-servers/s1",
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const RUN = "abcdefab-cdef-4abc-8def-abcdefabcdef";
const SUMMARY = calls({
  requests: 4,
  errors: 3,
  blocked: 1,
  p50_ms: 40,
  p95_ms: 900,
  recent: [
    call({ status: "denied", error_code: "openapi_path_invalid", latency_ms: 0, ts: "2026-11-19T09:04:00Z" }),
    call({ status: "error", error_code: "invalid_arguments", latency_ms: 3, ts: "2026-11-19T09:03:00Z", run_id: RUN, actor_type: "agent" }),
    call({ status: "blocked", error_code: "guardrail_blocked", latency_ms: 12, ts: "2026-11-19T09:02:00Z" }),
    call({ status: "ok", error_code: null, latency_ms: 40, ts: "2026-11-19T09:01:00Z" }),
  ],
});

describe("test_10c3_4_calls_monitor", () => {
  it("shows the 24-hour counters and latency percentiles", async () => {
    const api = stubApi({ [`GET ${S}/s1/calls`]: SUMMARY });
    renderGov("developer", "edit", <CallsMonitor projectId="p1" serverId="s1" />);
    expect((await screen.findByTestId("mcp-calls-requests")).textContent).toContain("4");
    expect(screen.getByTestId("mcp-calls-errors").textContent).toContain("3");
    expect(screen.getByTestId("mcp-calls-blocked").textContent).toContain("1");
    expect(screen.getByTestId("mcp-calls-p50").textContent).toContain("40 ms");
    expect(screen.getByTestId("mcp-calls-p95").textContent).toContain("900 ms");
    expect(api[0].search.get("hours")).toBe("24");
  });

  it("lists every call with its status and code, denied apart from error", async () => {
    stubApi({ [`GET ${S}/s1/calls`]: SUMMARY });
    renderGov("developer", "edit", <CallsMonitor projectId="p1" serverId="s1" />);
    const rows = await screen.findAllByTestId("mcp-call");
    expect(rows).toHaveLength(4);
    const seen = rows.map((row) => [within(row).getByTestId("mcp-call-status").textContent, within(row).getByTestId("mcp-call-code").textContent]);
    expect(seen).toEqual([
      ["Denied", "openapi_path_invalid"],
      ["Error", "invalid_arguments"],
      ["Blocked", "guardrail_blocked"],
      ["OK", "None"],
    ]);
    expect(within(rows[1]).getByRole("link").getAttribute("href")).toBe(`/runs/${RUN}`);
    expect(within(rows[0]).queryByRole("link")).toBeNull();
    const note = screen.getByTestId("mcp-calls-note").textContent ?? "";
    expect(note).toMatch(/Denied: refused before any request left/);
    expect(note).toMatch(/Error: the request was made/);
    expect(screen.getByTestId("mcp-calls-audit").textContent).toContain("update_mcp_server_spec");
  });

  it("says there were no calls, without inventing counters", async () => {
    stubApi({ [`GET ${S}/s1/calls`]: calls() });
    renderGov("developer", "edit", <CallsMonitor projectId="p1" serverId="s1" />);
    expect(await screen.findByTestId("mcp-calls-empty")).toBeTruthy();
    expect(screen.getByTestId("mcp-calls-p50").textContent).toContain("No data");
  });

  it("shows a failed read where the numbers would be", async () => {
    stubApi({ [`GET ${S}/s1/calls`]: refusal(403, "insufficient_role") });
    renderGov("developer", "edit", <CallsMonitor projectId="p1" serverId="s1" />);
    expect(await screen.findByTestId("query-error")).toBeTruthy();
    expect(screen.queryByTestId("mcp-calls-requests")).toBeNull();
  });

  it("is a tab of the server page", async () => {
    stubApi({ [`GET ${S}/s1`]: server(), [`GET ${S}/s1/calls`]: SUMMARY });
    renderGov("developer", "edit", <McpServerPage />);
    fireEvent.click(await screen.findByRole("tab", { name: "Monitoring" }));
    expect(await screen.findByTestId("mcp-calls-requests")).toBeTruthy();
  });
});
