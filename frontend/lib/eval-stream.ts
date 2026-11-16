import { SseParser } from "@/lib/sse";

// Exam progress stream (09 GET …/eval-runs/{id}/stream): `progress` {status, items, scored} every
// few seconds, then one `done` with the end status, `error_code` and `passed`. fetch +
// ReadableStream like lib/sse.ts (brief 10 technical notes). The stream only reads, so a dropped
// stream is simply reopened (it starts from the current state); after `maxReopens` it is `lost`
// and the page reads the exam with GET instead. Nothing is guessed about how it ended.

export type EvalProgress = { status: string; items: number; scored: number };
export type EvalDone = EvalProgress & { error_code: string | null; passed: boolean | null };
export type EvalStreamEnd = "done" | "lost" | "aborted";

export type EvalFollowOptions = {
  open: () => Promise<Response>;
  onProgress: (progress: EvalProgress) => void;
  onDone: (done: EvalDone) => void;
  // An event name outside progress/done: reported, skipped; the stream goes on.
  onUnknown?: (name: string) => void;
  signal?: AbortSignal;
  maxReopens?: number;
  retryDelayMs?: number;
};

export const MAX_REOPENS = 5;
export const REOPEN_DELAY_MS = 2000;

function progressOf(data: Record<string, unknown>): EvalProgress | null {
  const { status, items, scored } = data;
  if (typeof status !== "string" || typeof items !== "number" || typeof scored !== "number") return null;
  return { status, items, scored };
}

// One response to its end: "done", or null when it stopped (or broke) without done.
async function drain(response: Response, options: EvalFollowOptions): Promise<"done" | null> {
  if (!response.ok || !response.body) return null;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  try {
    for (;;) {
      if (options.signal?.aborted) return null;
      const { done, value } = await reader.read();
      for (const message of parser.push(done ? decoder.decode() : decoder.decode(value, { stream: true }))) {
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
    reader.releaseLock();
  }
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
  for (let attempt = 0; attempt <= maxReopens; attempt++) {
    if (options.signal?.aborted) return "aborted";
    if (attempt > 0) await sleep(delay, options.signal);
    if (options.signal?.aborted) return "aborted";
    let response: Response;
    try {
      response = await options.open();
    } catch {
      if (options.signal?.aborted) return "aborted";
      continue;
    }
    if ((await drain(response, options)) === "done") return "done";
  }
  return options.signal?.aborted ? "aborted" : "lost";
}
