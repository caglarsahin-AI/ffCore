// @vitest-environment jsdom
import { QueryClient } from "@tanstack/react-query";
import { act, cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import RunPage from "@/app/(console)/runs/[runId]/page";
import { RUNS_POLL_MS } from "@/lib/api/runs-queries";

import { renderAs } from "./eval-support";

// FOLLOWUP-192 (10c-2 D9): the run page keeps reading the run while no answer has arrived (the
// first GET failed) and shows why; a run that is gone (404/410) stops the reading. A failed
// refresh of a live run keeps the last answer on screen and says it could not be refreshed.

vi.mock("next/navigation", () => ({
  useParams: () => ({ runId: "r1" }),
  usePathname: () => "/runs/r1",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

const RUN_GET = "/api/v1/projects/p1/runs/r1";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const refusal = (status: number, code: string) => json({ error: { code, type: "api_error", message: code } }, status);

function run(status: string) {
  return json({
    id: "r1",
    project_id: "p1",
    agent_id: "a1",
    agent_version_id: "v1",
    status,
    channel: "test",
    input: "hello",
    output: null,
    partial: false,
    outcome_label: null,
    error_code: null,
    started_at: null,
    ended_at: null,
    tokens_in: 0,
    tokens_out: 0,
    slowest_step: null,
    model_ms: null,
    tool_ms: null,
    retrieval_ms: null,
    queue_wait_ms: null,
    langfuse_trace_id: null,
    feedback: null,
    created_at: "2026-11-17T08:00:00Z",
  });
}

function urlOf(input: RequestInfo | URL): string {
  return typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function start(answer: (n: number) => Response | Promise<Response>) {
  let n = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = urlOf(input);
    if (url === RUN_GET) {
      n += 1;
      return answer(n);
    }
    if (url.includes("/runs/r1/events")) return json({ items: [] });
    return json({ items: [], data: [] });
  });
  vi.stubGlobal("fetch", fetchMock);
  renderAs("analyst", "edit", <RunPage />, new QueryClient({ defaultOptions: { queries: { retry: false } } }));
  return () => fetchMock.mock.calls.filter(([input]) => urlOf(input as RequestInfo) === RUN_GET).length;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("test_10c2_5_run_page_poll", () => {
  it("keeps reading after the first GET fails, shows the failure, then the run once the backend answers", async () => {
    vi.useFakeTimers();
    let up = false;
    const gets = start(() => {
      if (!up) throw new TypeError("Failed to fetch");
      return run("running");
    });
    await advance(0);
    expect(screen.getByTestId("run-read-error").textContent).toContain("network_error");
    await advance(RUNS_POLL_MS);
    await advance(RUNS_POLL_MS);
    const failed = gets();
    expect(failed).toBeGreaterThanOrEqual(3);
    up = true;
    await advance(RUNS_POLL_MS);
    await advance(0);
    expect(screen.getByTestId("run-detail-status").textContent).toContain("Running");
    expect(screen.queryByTestId("run-read-error")).toBeNull();
  });

  it("shows the contract code of a refused GET and keeps reading", async () => {
    vi.useFakeTimers();
    const gets = start((n) => (n < 3 ? refusal(503, "unavailable") : run("completed")));
    await advance(0);
    expect(screen.getByTestId("run-read-error").textContent).toContain("unavailable");
    await advance(RUNS_POLL_MS);
    await advance(RUNS_POLL_MS);
    await advance(0);
    expect(screen.getByTestId("run-detail-status").textContent).toContain("Completed");
    const ended = gets();
    await advance(5 * RUNS_POLL_MS);
    expect(gets()).toBe(ended);
  });

  it.each([404, 410])("stops reading when the run is gone (%i)", async (status) => {
    vi.useFakeTimers();
    const gets = start(() => refusal(status, "run_not_found"));
    await advance(0);
    expect(screen.getByTestId("run-read-error").textContent).toContain("run_not_found");
    const seen = gets();
    await advance(5 * RUNS_POLL_MS);
    expect(gets()).toBe(seen);
  });

  it("keeps the last answer of a live run when a refresh fails, and says so", async () => {
    vi.useFakeTimers();
    start((n) => {
      if (n === 1) return run("running");
      throw new TypeError("Failed to fetch");
    });
    await advance(0);
    expect(screen.getByTestId("run-detail-status").textContent).toContain("Running");
    await advance(RUNS_POLL_MS);
    await advance(0);
    expect(screen.getByTestId("run-detail-status").textContent).toContain("Running");
    expect(screen.getByTestId("run-read-error").textContent).toContain("network_error");
  });
});
