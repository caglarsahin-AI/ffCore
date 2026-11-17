import { afterEach, describe, expect, it, vi } from "vitest";

import * as sse from "@/lib/sse";
import { MAX_RECONNECTS, RETRY_DELAY_MS, followRunStream } from "@/lib/sse";
import type { StreamState } from "@/lib/sse";

// FOLLOWUP-188 (sse-sessiz-kopus, 10c-1 r1 MAJOR-1 for the run stream): a half-open connection
// sends no bytes and never closes, so `reader.read()` waits forever and the run looks live. The
// backend writes a `: keepalive` comment every sse_keepalive_s (10 s), so silence for STALL_MS
// (three keepalives) ends the attempt and the Last-Event-ID reconnect / `lost` path takes over.

const encoder = new TextEncoder();
const first = 'id: 1-0\nevent: progress\ndata: {"run_id":"r1"}\n\n';
const doneEvent = 'id: 1-9\nevent: done\ndata: {"status":"completed"}\n\n';
const keepalive = ": keepalive\n\n";

// The constants under test; read through the module so a missing export fails the assertion,
// not the import.
const KEEPALIVE_MS = (sse as Record<string, unknown>).SSE_KEEPALIVE_MS as number;
const STALL = (sse as Record<string, unknown>).STALL_MS as number;

function closed(chunks: string[], status = 200): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { status, headers: { "content-type": "text/event-stream" } });
}

// The given chunks, then silence: the body stays open forever (a half-open connection).
function silentAfter(...chunks: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
    },
  });
  return new Response(body, { status: 200 });
}

afterEach(() => {
  vi.useRealTimers();
});

describe("test_10bsse_1_stall: constants", () => {
  it("derives STALL_MS from the backend keepalive interval (three missed keepalives)", () => {
    expect(KEEPALIVE_MS).toBe(10_000);
    expect(STALL).toBe(3 * KEEPALIVE_MS);
  });
});

describe("test_10bsse_1_stall: watchdog", () => {
  it("(1) ends a stream that spoke then went silent after STALL_MS and reconnects with Last-Event-ID", async () => {
    vi.useFakeTimers();
    const signals: AbortSignal[] = [];
    const states: StreamState[] = [];
    const reconnect = vi.fn(async (_runId: string, _last: string | null) => closed([doneEvent]));
    const end = followRunStream({
      open: async (signal?: AbortSignal) => {
        if (signal) signals.push(signal);
        return silentAfter(first);
      },
      reconnect,
      onEvent: () => undefined,
      onState: (state) => states.push(state),
    });
    await vi.advanceTimersByTimeAsync(STALL - 1);
    expect(reconnect).not.toHaveBeenCalled();
    expect(states).toEqual(["streaming"]);
    await vi.advanceTimersByTimeAsync(1);
    expect(states).toContain("reconnecting");
    expect(signals).toHaveLength(1);
    expect(signals[0].aborted).toBe(true);
    await vi.advanceTimersByTimeAsync(RETRY_DELAY_MS);
    await expect(end).resolves.toEqual({ runId: "r1", lastEventId: "1-9", ended: "done", reconnects: 1 });
    expect(reconnect).toHaveBeenCalledWith("r1", "1-0", expect.any(AbortSignal));
  });

  it("(2) keeps a stream alive on `: keepalive` comments alone (they carry no message but are a sign of life)", async () => {
    vi.useFakeTimers();
    let push: ((chunk: string) => void) | undefined;
    let close: (() => void) | undefined;
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(first));
        push = (chunk) => controller.enqueue(encoder.encode(chunk));
        close = () => controller.close();
      },
    });
    const reconnect = vi.fn(async () => closed([doneEvent]));
    const end = followRunStream({ open: async () => new Response(body), reconnect, onEvent: () => undefined });
    const ticks = Math.ceil((3 * STALL) / KEEPALIVE_MS);
    for (let i = 0; i < ticks; i++) {
      await vi.advanceTimersByTimeAsync(KEEPALIVE_MS);
      push?.(keepalive);
    }
    expect(reconnect).not.toHaveBeenCalled();
    push?.(doneEvent);
    close?.();
    await expect(end).resolves.toMatchObject({ ended: "done", reconnects: 0 });
  });

  it("(3) reports lost after maxReconnects when every reconnect goes silent too, within the named upper bound", async () => {
    vi.useFakeTimers();
    // Each attempt waits the retry delay, then STALL of silence (the first attempt has no delay).
    const LOST_UPPER_BOUND_MS = STALL + MAX_RECONNECTS * (RETRY_DELAY_MS + STALL);
    const reconnect = vi.fn(async () => silentAfter(keepalive));
    let ended: string | null = null;
    const end = followRunStream({ open: async () => silentAfter(first), reconnect, onEvent: () => undefined }).then((r) => {
      ended = r.ended;
      return r;
    });
    await vi.advanceTimersByTimeAsync(LOST_UPPER_BOUND_MS - 1);
    expect(ended).toBeNull();
    await vi.advanceTimersByTimeAsync(1);
    await expect(end).resolves.toMatchObject({ ended: "lost", reconnects: MAX_RECONNECTS });
    expect(reconnect).toHaveBeenCalledTimes(MAX_RECONNECTS);
  });

  it("(3b) ends a reconnect request that hangs (ignoring its signal) through the same watchdog", async () => {
    vi.useFakeTimers();
    const reconnect = vi.fn(() => new Promise<Response>(() => undefined));
    const end = followRunStream({ open: async () => silentAfter(first), reconnect, onEvent: () => undefined, maxReconnects: 2, retryDelayMs: 0 });
    await vi.advanceTimersByTimeAsync(3 * STALL);
    await expect(end).resolves.toMatchObject({ ended: "lost", reconnects: 2 });
  });

  it("(4) reports done when the stream reopened after a stall ends with done", async () => {
    vi.useFakeTimers();
    const end = followRunStream({
      open: async () => silentAfter(first),
      reconnect: async () => closed(['id: 1-1\nevent: token\ndata: {"text":"b"}\n\n', doneEvent]),
      onEvent: () => undefined,
      retryDelayMs: 0,
    });
    await vi.advanceTimersByTimeAsync(STALL);
    await expect(end).resolves.toMatchObject({ ended: "done", reconnects: 1 });
  });

  it("(5) ends as aborted on the outside signal, without reconnecting and leaving no timer behind", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const reconnect = vi.fn(async () => closed([doneEvent]));
    const end = followRunStream({ open: async () => silentAfter(first), reconnect, onEvent: () => undefined, signal: controller.signal });
    await vi.advanceTimersByTimeAsync(STALL / 2);
    controller.abort();
    await expect(end).resolves.toMatchObject({ ended: "aborted", reconnects: 0 });
    expect(reconnect).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("uses FollowOptions.stallMs when given", async () => {
    vi.useFakeTimers();
    const reconnect = vi.fn(async () => closed([doneEvent]));
    const end = followRunStream({ open: async () => silentAfter(first), reconnect, onEvent: () => undefined, retryDelayMs: 0, stallMs: 500 } as Parameters<typeof followRunStream>[0]);
    await vi.advanceTimersByTimeAsync(500);
    await expect(end).resolves.toMatchObject({ ended: "done", reconnects: 1 });
  });
});

describe("test_10bsse_1_stall: a failed read is a drop", () => {
  it("reconnects after a read error instead of throwing (never a guessed end)", async () => {
    let pulls = 0;
    const body = new ReadableStream<Uint8Array>(
      {
        pull(controller) {
          if (++pulls === 1) controller.enqueue(encoder.encode(first));
          else controller.error(new TypeError("network error"));
        },
      },
      { highWaterMark: 0 },
    );
    const reconnect = vi.fn(async () => closed([doneEvent]));
    const result = await followRunStream({ open: async () => new Response(body), reconnect, onEvent: () => undefined, retryDelayMs: 0 });
    expect(reconnect).toHaveBeenCalledWith("r1", "1-0", expect.any(AbortSignal));
    expect(result).toMatchObject({ ended: "done", reconnects: 1 });
  });

  it("still throws on a broken data line (a broken event is not a drop)", async () => {
    await expect(
      followRunStream({ open: async () => closed(["id: 1-0\nevent: progress\ndata: {not json\n\n"]), reconnect: async () => closed([doneEvent]), onEvent: () => undefined, retryDelayMs: 0 }),
    ).rejects.toThrow(SyntaxError);
  });
});
