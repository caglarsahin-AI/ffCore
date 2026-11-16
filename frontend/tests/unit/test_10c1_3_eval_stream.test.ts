import { describe, expect, it, vi } from "vitest";

import { followEvalStream } from "@/lib/eval-stream";
import type { EvalProgress } from "@/lib/eval-stream";

const encoder = new TextEncoder();

function response(chunks: string[], status = 200): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { status, headers: { "content-type": "text/event-stream" } });
}

describe("test_10c1_3_eval_stream", () => {
  it("delivers progress across chunk boundaries, then done, and ends", async () => {
    const seen: EvalProgress[] = [];
    const done = vi.fn();
    const result = await followEvalStream({
      open: async () =>
        response([
          'event: progress\ndata: {"status":"queued","items":0,"scored":0}\n\nevent: prog',
          'ress\ndata: {"status":"running","items":3,"scored":1}\n\n',
          'event: done\ndata: {"status":"completed","items":3,"scored":3,"error_code":null,"passed":true}\n\n',
        ]),
      onProgress: (p) => seen.push(p),
      onDone: done,
    });
    expect(seen).toEqual([
      { status: "queued", items: 0, scored: 0 },
      { status: "running", items: 3, scored: 1 },
    ]);
    expect(done).toHaveBeenCalledWith({ status: "completed", items: 3, scored: 3, error_code: null, passed: true });
    expect(result).toBe("done");
  });

  it("reports an unknown event name and goes on (the UI does not break)", async () => {
    const unknown = vi.fn();
    const result = await followEvalStream({
      open: async () =>
        response(['event: heartbeat2\ndata: {}\n\n', 'event: done\ndata: {"status":"failed","items":1,"scored":0,"error_code":"definition_changed","passed":null}\n\n']),
      onProgress: () => {},
      onDone: () => {},
      onUnknown: unknown,
    });
    expect(unknown).toHaveBeenCalledWith("heartbeat2");
    expect(result).toBe("done");
  });

  it("reopens a stream that stopped without done, then reports it lost (never a guessed end)", async () => {
    const open = vi.fn(async () => response(['event: progress\ndata: {"status":"running","items":3,"scored":1}\n\n']));
    const result = await followEvalStream({ open, onProgress: () => {}, onDone: () => {}, maxReopens: 2, retryDelayMs: 0 });
    expect(open).toHaveBeenCalledTimes(3);
    expect(result).toBe("lost");
  });

  it("treats a refused open as lost after the retries and a broken data line as lost too", async () => {
    const refused = await followEvalStream({ open: async () => response([], 503), onProgress: () => {}, onDone: () => {}, maxReopens: 0, retryDelayMs: 0 });
    expect(refused).toBe("lost");
    const broken = await followEvalStream({ open: async () => response(["event: progress\ndata: {not json\n\n"]), onProgress: () => {}, onDone: () => {}, maxReopens: 0, retryDelayMs: 0 });
    expect(broken).toBe("lost");
  });

  it("stops on abort without reopening", async () => {
    const controller = new AbortController();
    controller.abort();
    const open = vi.fn(async () => response([]));
    const result = await followEvalStream({ open, onProgress: () => {}, onDone: () => {}, signal: controller.signal });
    expect(result).toBe("aborted");
    expect(open).not.toHaveBeenCalled();
  });
});
