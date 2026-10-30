import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { SSE_EVENTS, SseParser, followRunStream, isTerminalEvent } from "@/lib/sse";
import type { RunStreamEvent } from "@/lib/sse";

const encoder = new TextEncoder();

function body(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

function response(chunks: string[], status = 200): Response {
  return new Response(body(chunks), { status, headers: { "content-type": "text/event-stream" } });
}

describe("test_10bp2_6_sse: parser", () => {
  it("splits events across chunk boundaries, joins multi-line data and keeps the id", () => {
    const parser = new SseParser();
    expect(parser.push("id: 1-0\nevent: tok")).toEqual([]);
    const out = parser.push('en\ndata: {"text":\ndata: "hi"}\n\n: keepalive\n\nid: 1-1\r\nevent: done\r\ndata: {}\r\n\r\n');
    expect(out).toEqual([
      { id: "1-0", event: "token", data: '{"text":\n"hi"}' },
      { id: "1-1", event: "done", data: "{}" },
    ]);
  });

  it("names an event without an event field `message`, as the SSE spec does", () => {
    expect(new SseParser().push("data: x\n\n")).toEqual([{ id: null, event: "message", data: "x" }]);
  });

  it("knows exactly the C9 SSE event names", () => {
    const contracts = readFileSync("../handbook/CONTRACTS.md", "utf8");
    const row = contracts.split("\n").find((line) => line.startsWith("| C9 |"));
    const names = /`SSE` event adları \(10\): ([^(]+)\(/.exec(row ?? "")?.[1];
    const fromContract = (names ?? "").split(",").map((name) => name.replaceAll("`", "").trim());
    expect([...SSE_EVENTS].sort()).toEqual(fromContract.sort());
    expect(SSE_EVENTS).toHaveLength(10);
  });

  it("ends a stream on done, error, approval_required and question only", () => {
    expect(SSE_EVENTS.filter(isTerminalEvent).sort()).toEqual(["approval_required", "done", "error", "question"]);
  });
});

describe("test_10bp2_6_sse: following a run", () => {
  it("delivers known events with parsed data and ignores unknown names (C9 consumer rule)", async () => {
    const seen: RunStreamEvent[] = [];
    const result = await followRunStream({
      open: async () =>
        response([
          'id: 1-0\nevent: progress\ndata: {"run_id":"r1"}\n\n',
          'id: 1-1\nevent: brand_new_event\ndata: {"x":1}\n\n',
          'id: 1-2\nevent: token\ndata: {"text":"Hi"}\n\n',
          'id: 1-3\nevent: done\ndata: {"status":"completed"}\n\n',
        ]),
      reconnect: async () => {
        throw new Error("must not reconnect after done");
      },
      onEvent: (event) => seen.push(event),
    });
    expect(seen.map((e) => e.event)).toEqual(["progress", "token", "done"]);
    expect(seen[1].data).toEqual({ text: "Hi" });
    expect(result).toEqual({ runId: "r1", lastEventId: "1-3", ended: "done", reconnects: 0 });
  });

  it("reconnects with the last event id when the stream drops before a terminal event", async () => {
    const lastIds: (string | null)[] = [];
    const states: string[] = [];
    const result = await followRunStream({
      open: async () => response(['id: 1-0\nevent: progress\ndata: {"run_id":"r1"}\n\n', 'id: 1-1\nevent: token\ndata: {"text":"a"}\n\n']),
      reconnect: async (runId, lastEventId) => {
        lastIds.push(lastEventId);
        expect(runId).toBe("r1");
        return response(['id: 1-2\nevent: token\ndata: {"text":"b"}\n\n', 'id: 1-3\nevent: done\ndata: {}\n\n']);
      },
      onEvent: () => undefined,
      onState: (state) => states.push(state),
      retryDelayMs: 0,
    });
    expect(lastIds).toEqual(["1-1"]);
    expect(states).toContain("reconnecting");
    expect(result.ended).toBe("done");
    expect(result.reconnects).toBe(1);
  });

  it("fails loudly when reconnecting keeps failing; it never pretends the run finished", async () => {
    const result = await followRunStream({
      open: async () => response(['id: 1-0\nevent: progress\ndata: {"run_id":"r1"}\n\n']),
      reconnect: async () => response([], 503),
      onEvent: () => undefined,
      retryDelayMs: 0,
      maxReconnects: 2,
    });
    expect(result.ended).toBe("lost");
    expect(result.reconnects).toBe(2);
  });

  it("reports a stream that never named its run as lost, without reconnecting", async () => {
    const result = await followRunStream({
      open: async () => response(['id: 1-0\nevent: token\ndata: {"text":"a"}\n\n']),
      reconnect: async () => {
        throw new Error("no run id to reconnect to");
      },
      onEvent: () => undefined,
      retryDelayMs: 0,
    });
    expect(result).toMatchObject({ runId: null, ended: "lost", reconnects: 0 });
  });
});
