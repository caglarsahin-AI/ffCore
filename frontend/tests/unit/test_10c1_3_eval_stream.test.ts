import { afterEach, describe, expect, it, vi } from "vitest";

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

// R-10C1-0003 MAJOR-1 (sse-sessiz-kopus): a half-open connection sends no bytes and never closes.
// The backend sends `progress` every PROGRESS_INTERVAL_MS, so silence for STALL_MS ends the
// attempt and the usual reopen / lost path takes over.
describe("test_10c1_3_eval_stream stall watchdog", () => {
  const progress = 'event: progress\ndata: {"status":"running","items":3,"scored":1}\n\n';
  const doneEvent = 'event: done\ndata: {"status":"completed","items":3,"scored":3,"error_code":null,"passed":true}\n\n';

  // One chunk, then silence: the body stays open forever.
  function silentAfter(chunk: string): Response {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(chunk));
      },
    });
    return new Response(body, { status: 200 });
  }

  afterEach(() => {
    vi.useRealTimers();
  });

  it("derives STALL_MS from the backend progress interval", async () => {
    const { STALL_MS, PROGRESS_INTERVAL_MS } = await import("@/lib/eval-stream");
    expect(PROGRESS_INTERVAL_MS).toBe(2000);
    expect(STALL_MS).toBe(3 * PROGRESS_INTERVAL_MS);
  });

  it("ends a silent attempt after STALL_MS, aborts its request and reports lost after the reopens", async () => {
    vi.useFakeTimers();
    const signals: AbortSignal[] = [];
    const open = vi.fn(async (signal: AbortSignal) => {
      signals.push(signal);
      return silentAfter(progress);
    });
    const seen: EvalProgress[] = [];
    const end = followEvalStream({ open, onProgress: (p) => seen.push(p), onDone: () => {}, maxReopens: 1, retryDelayMs: 0, stallMs: 6000 });
    await vi.advanceTimersByTimeAsync(5999);
    expect(open).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    await vi.advanceTimersByTimeAsync(6000);
    await expect(end).resolves.toBe("lost");
    expect(open).toHaveBeenCalledTimes(2);
    expect(signals.every((s) => s.aborted)).toBe(true);
    expect(seen).toHaveLength(2);
  });

  it("reports done when the stream reopened after a stall ends with done", async () => {
    vi.useFakeTimers();
    let calls = 0;
    const open = vi.fn(async () => (++calls === 1 ? silentAfter(progress) : response([progress, doneEvent])));
    const onDone = vi.fn();
    const end = followEvalStream({ open, onProgress: () => {}, onDone, maxReopens: 2, retryDelayMs: 0, stallMs: 6000 });
    await vi.advanceTimersByTimeAsync(6000);
    await expect(end).resolves.toBe("done");
    expect(open).toHaveBeenCalledTimes(2);
    expect(onDone).toHaveBeenCalledOnce();
  });

  it("ends an attempt whose request never answers", async () => {
    vi.useFakeTimers();
    const open = vi.fn(
      (signal: AbortSignal) =>
        new Promise<Response>((_, reject) => signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")))),
    );
    const end = followEvalStream({ open, onProgress: () => {}, onDone: () => {}, maxReopens: 0, retryDelayMs: 0, stallMs: 6000 });
    await vi.advanceTimersByTimeAsync(6000);
    await expect(end).resolves.toBe("lost");
    expect(open).toHaveBeenCalledTimes(1);
  });

  it("keeps a slow but living stream: every chunk resets the watchdog", async () => {
    vi.useFakeTimers();
    let push: ((chunk: string) => void) | undefined;
    let close: (() => void) | undefined;
    const open = vi.fn(async () => {
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          push = (chunk) => controller.enqueue(encoder.encode(chunk));
          close = () => controller.close();
        },
      });
      return new Response(body, { status: 200 });
    });
    const end = followEvalStream({ open, onProgress: () => {}, onDone: () => {}, maxReopens: 0, retryDelayMs: 0, stallMs: 6000 });
    for (let i = 0; i < 4; i++) {
      await vi.advanceTimersByTimeAsync(5000);
      push?.(progress);
    }
    push?.(doneEvent);
    close?.();
    await expect(end).resolves.toBe("done");
    expect(open).toHaveBeenCalledTimes(1);
  });

  it("an outside abort still wins over the watchdog", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const open = vi.fn(async () => silentAfter(progress));
    const end = followEvalStream({ open, onProgress: () => {}, onDone: () => {}, signal: controller.signal, retryDelayMs: 0, stallMs: 6000 });
    await vi.advanceTimersByTimeAsync(1000);
    controller.abort();
    await expect(end).resolves.toBe("aborted");
    expect(open).toHaveBeenCalledTimes(1);
  });
});
