// @vitest-environment jsdom
import { QueryClient } from "@tanstack/react-query";
import { act, cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgentTestPanel } from "@/components/agent-test-panel";
import type { AgentDefinition } from "@/lib/agent-definition";
import { RUNS_POLL_MS } from "@/lib/api/runs-queries";
import * as sse from "@/lib/sse";
import { RETRY_DELAY_MS } from "@/lib/sse";

import { renderAs } from "./eval-support";

// FOLLOWUP-188 D2 (10c-1 ek, K-SSE-0002): while the run stream reconnects or is lost, the test
// panel reads the run with GET (RUNS_POLL_MS) and shows the server status; a stream that speaks
// again stops the reading. The panel never shows a stale state as current.

const STALL = (sse as Record<string, unknown>).STALL_MS as number;
const encoder = new TextEncoder();
const first = 'id: 1-0\nevent: progress\ndata: {"run_id":"r1"}\n\n';
const RUN_GET = "/api/v1/projects/p1/runs/r1";

type Push = (chunk: string) => void;

function openBody(chunks: string[], keep?: (push: Push) => void): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      keep?.((chunk) => controller.enqueue(encoder.encode(chunk)));
    },
  });
  return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
}

function run(status: string) {
  return new Response(JSON.stringify({ id: "r1", project_id: "p1", status }), { status: 200, headers: { "content-type": "application/json" } });
}

function urlOf(input: RequestInfo | URL): string {
  return typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function start() {
  renderAs("developer", "edit", <AgentTestPanel projectId="p1" agentKey="a1" version={1} definition={{ variables: [] } as unknown as AgentDefinition} dirty={false} />, new QueryClient({ defaultOptions: { queries: { retry: false } } }));
  fireEvent.change(screen.getByTestId("test-input"), { target: { value: "hello" } });
  fireEvent.submit(screen.getByTestId("test-input").closest("form")!);
  await advance(0);
}

const gets = (fetchMock: ReturnType<typeof vi.fn>) => fetchMock.mock.calls.filter(([input]) => urlOf(input as RequestInfo) === RUN_GET).length;

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("test_10bsse_2_panel_poll", () => {
  it("reads the run with GET once the stream stalls and shows the server status while reconnecting", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = urlOf(input);
      if (url === RUN_GET) return run("running");
      if (url.endsWith("/runs/r1/stream")) return openBody([]); // reconnect goes silent too
      return openBody([first]); // POST …/agents/a1/runs
    });
    vi.stubGlobal("fetch", fetchMock);
    await start();
    await advance(STALL - 1);
    expect(gets(fetchMock)).toBe(0);
    expect(screen.queryByTestId("test-server-status")).toBeNull();
    await advance(1);
    expect(screen.getByTestId("test-status").dataset.stream).toBe("reconnecting");
    await advance(0);
    expect(gets(fetchMock)).toBeGreaterThanOrEqual(1);
    expect(screen.getByTestId("test-server-status").textContent).toContain("Running");
    const before = gets(fetchMock);
    await advance(RUNS_POLL_MS);
    expect(gets(fetchMock)).toBeGreaterThan(before);
  });

  it("keeps reading with GET after the stream is lost", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = urlOf(input);
      if (url === RUN_GET) return run("waiting_approval");
      if (url.endsWith("/runs/r1/stream")) return new Response(null, { status: 503 });
      return openBody([first]);
    });
    vi.stubGlobal("fetch", fetchMock);
    await start();
    await advance(STALL + 10 * RETRY_DELAY_MS);
    expect(screen.getByTestId("test-status").dataset.stream).toBe("lost");
    expect(screen.getByTestId("test-server-status").textContent).toContain("Waiting for approval");
    const before = gets(fetchMock);
    await advance(RUNS_POLL_MS);
    expect(gets(fetchMock)).toBeGreaterThan(before);
  });

  it("stops reading with GET when the reconnected stream speaks again", async () => {
    vi.useFakeTimers();
    let push: Push | undefined;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = urlOf(input);
      if (url === RUN_GET) return run("running");
      if (url.endsWith("/runs/r1/stream")) return openBody(['id: 1-1\nevent: token\ndata: {"text":"b"}\n\n'], (p) => (push = p));
      return openBody([first]);
    });
    vi.stubGlobal("fetch", fetchMock);
    await start();
    await advance(STALL);
    await advance(RETRY_DELAY_MS);
    expect(fetchMock.mock.calls.some(([input]) => urlOf(input as RequestInfo).endsWith("/runs/r1/stream"))).toBe(true);
    expect(screen.getByTestId("test-status").dataset.stream).toBe("streaming");
    expect(screen.queryByTestId("test-server-status")).toBeNull();
    const before = gets(fetchMock);
    for (let i = 0; i < 3; i++) {
      push?.(": keepalive\n\n");
      await advance(RUNS_POLL_MS);
    }
    expect(gets(fetchMock)).toBe(before);
  });
});
