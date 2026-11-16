import { SseParser } from "@/lib/sse";

// Exam progress stream (09 GET …/eval-runs/{id}/stream): `progress` {status, items, scored} every
// few seconds, then one `done` with the end status, `error_code` and `passed`. fetch +
// ReadableStream like lib/sse.ts (brief 10 technical notes). The stream only reads, so a dropped
// or silent (STALL_MS) stream is simply reopened (it starts from the current state); after
// `maxReopens` it is `lost` and the page reads the exam with GET instead. Nothing is guessed
// about how it ended.

export type EvalProgress = { status: string; items: number; scored: number };
export type EvalDone = EvalProgress & { error_code: string | null; passed: boolean | null };
export type EvalStreamEnd = "done" | "lost" | "aborted";

export type EvalFollowOptions = {
  // Opens one attempt; the signal ends that attempt (outside abort or the stall watchdog).
  open: (signal: AbortSignal) => Promise<Response>;
  onProgress: (progress: EvalProgress) => void;
  onDone: (done: EvalDone) => void;
  // An event name outside progress/done: reported, skipped; the stream goes on.
  onUnknown?: (name: string) => void;
  // An attempt ended without done and the stream is being reopened: the page reads the exam with
  // GET meanwhile (K-10C1-0007). Said once per phase; the last failed attempt is `lost` instead.
  onReconnecting?: () => void;
  // A reopened stream spoke again (its first event, before that event is delivered).
  onResumed?: () => void;
  signal?: AbortSignal;
  maxReopens?: number;
  retryDelayMs?: number;
  stallMs?: number;
};

export const MAX_REOPENS = 5;
export const REOPEN_DELAY_MS = 2000;
// The backend sends `progress` every PROGRESS_INTERVAL_S = 2.0 s (backend/ffcore/api/eval.py).
export const PROGRESS_INTERVAL_MS = 2000;
// Stall watchdog (R-10C1-0003 MAJOR-1): a half-open connection (backend killed, a proxy dropping
// an idle socket) sends nothing and never closes. Three missed progress events end the attempt;
// the usual reopen / `lost` path takes over, so the page never shows a stale state as current.
export const STALL_MS = 3 * PROGRESS_INTERVAL_MS;

function progressOf(data: Record<string, unknown>): EvalProgress | null {
  const { status, items, scored } = data;
  if (typeof status !== "string" || typeof items !== "number" || typeof scored !== "number") return null;
  return { status, items, scored };
}

// One response to its end: "done", or null when it stopped (or broke) without done.
// The attempt may be ended from outside (abort, watchdog); the pending read is then cancelled.
async function drain(response: Response, options: EvalFollowOptions, attempt: Attempt): Promise<"done" | null> {
  if (!response.ok || !response.body) return null;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  const stop = () => void reader.cancel().catch(() => {});
  attempt.signal.addEventListener("abort", stop, { once: true });
  try {
    for (;;) {
      if (attempt.signal.aborted) return null;
      const { done, value } = await reader.read();
      if (attempt.signal.aborted) return null;
      attempt.alive();
      for (const message of parser.push(done ? decoder.decode() : decoder.decode(value, { stream: true }))) {
        attempt.spoke();
        if (message.event !== "progress" && message.event !== "done") {
          options.onUnknown?.(message.event);
          continue;
        }
        let data: unknown;
        try {
          data = JSON.parse(message.data);
        } catch {
          return null; // a broken event is a broken stream, not a guessed value
        }
        const progress = data && typeof data === "object" ? progressOf(data as Record<string, unknown>) : null;
        if (!progress) return null;
        if (message.event === "progress") {
          options.onProgress(progress);
          continue;
        }
        const d = data as Record<string, unknown>;
        options.onDone({
          ...progress,
          error_code: typeof d.error_code === "string" ? d.error_code : null,
          passed: typeof d.passed === "boolean" ? d.passed : null,
        });
        return "done";
      }
      if (done) return null;
    }
  } catch {
    return null;
  } finally {
    attempt.signal.removeEventListener("abort", stop);
    reader.releaseLock();
  }
}

// One attempt: its own AbortController, chained to the outside signal and fired by the watchdog
// when nothing arrived for `stallMs` (the request itself included).
type Attempt = { signal: AbortSignal; alive: () => void; end: () => void; spoke: () => void };

function startAttempt(stallMs: number, outside: AbortSignal | undefined, spoke: () => void): Attempt {
  const controller = new AbortController();
  const abort = () => controller.abort();
  outside?.addEventListener("abort", abort, { once: true });
  let timer: ReturnType<typeof setTimeout> | undefined;
  const alive = () => {
    clearTimeout(timer);
    timer = setTimeout(abort, stallMs);
  };
  alive();
  return {
    signal: controller.signal,
    alive,
    spoke,
    end: () => {
      clearTimeout(timer);
      outside?.removeEventListener("abort", abort);
      controller.abort();
    },
  };
}

// The request, unless the attempt ends first (an open() that ignores its signal cannot hang it).
function openWithin(attempt: Attempt, open: EvalFollowOptions["open"]): Promise<Response> {
  return new Promise<Response>((resolve, reject) => {
    if (attempt.signal.aborted) return reject(new DOMException("attempt ended", "AbortError"));
    attempt.signal.addEventListener("abort", () => reject(new DOMException("attempt ended", "AbortError")), { once: true });
    open(attempt.signal).then(resolve, reject);
  });
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve) => {
    if (ms <= 0) return resolve();
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      resolve();
    });
  });

export async function followEvalStream(options: EvalFollowOptions): Promise<EvalStreamEnd> {
  const maxReopens = options.maxReopens ?? MAX_REOPENS;
  const delay = options.retryDelayMs ?? REOPEN_DELAY_MS;
  const stallMs = options.stallMs ?? STALL_MS;
  let reconnecting = false;
  const spoke = () => {
    if (!reconnecting) return;
    reconnecting = false;
    options.onResumed?.();
  };
  for (let i = 0; i <= maxReopens; i++) {
    if (options.signal?.aborted) return "aborted";
    if (i > 0) {
      if (!reconnecting) {
        reconnecting = true;
        options.onReconnecting?.();
      }
      await sleep(delay, options.signal);
    }
    if (options.signal?.aborted) return "aborted";
    const attempt = startAttempt(stallMs, options.signal, spoke);
    try {
      const response = await openWithin(attempt, options.open);
      attempt.alive();
      if ((await drain(response, options, attempt)) === "done") return "done";
    } catch {
      // refused, broken or ended request: the next attempt (or `lost`) follows
    } finally {
      attempt.end();
    }
  }
  return options.signal?.aborted ? "aborted" : "lost";
}

// What the exam page shows: whichever it heard last, the stream's progress or the exam read with
// GET (each with the time it arrived). A failed GET keeps its last data and time, so an older
// status never comes back while the stream reconnects; a tie goes to GET, the full record.
export function newestState<T extends EvalProgress>(run: T, runAt: number, progress: EvalProgress | null, progressAt: number): EvalProgress {
  return progress && progressAt > runAt ? progress : run;
}
