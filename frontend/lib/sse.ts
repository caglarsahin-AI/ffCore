// Run event stream client (06a, C9). Plain fetch + ReadableStream instead of EventSource: the
// stream is a POST, and the reconnect needs a Last-Event-ID header (brief 10 technical notes).
// Pure apart from the injected open/reconnect calls, so the tests drive it with fake responses.

// C9 SSE event names; test_10bp2_6_sse pins the list to handbook/CONTRACTS.md.
export const SSE_EVENTS = [
  "token",
  "tool_call",
  "tool_result",
  "approval_required",
  "question",
  "sources",
  "done",
  "error",
  "progress",
  "fallback",
] as const;
export type SseEventName = (typeof SSE_EVENTS)[number];

const KNOWN: ReadonlySet<string> = new Set(SSE_EVENTS);
const TERMINAL: ReadonlySet<SseEventName> = new Set(["done", "error", "approval_required", "question"]);

export function isKnownEvent(name: string): name is SseEventName {
  return KNOWN.has(name);
}

// The stream ends after these (docs/agentlar.md "Runs").
export function isTerminalEvent(name: SseEventName): boolean {
  return TERMINAL.has(name);
}

export type SseMessage = { id: string | null; event: string; data: string };

// Incremental text/event-stream parser: feed decoded text, get complete messages back.
export class SseParser {
  private buffer = "";

  push(text: string): SseMessage[] {
    this.buffer += text.replace(/\r\n?/g, "\n");
    const messages: SseMessage[] = [];
    let end = this.buffer.indexOf("\n\n");
    while (end !== -1) {
      const block = this.buffer.slice(0, end);
      this.buffer = this.buffer.slice(end + 2);
      const message = parseBlock(block);
      if (message) messages.push(message);
      end = this.buffer.indexOf("\n\n");
    }
    return messages;
  }
}

function parseBlock(block: string): SseMessage | null {
  let id: string | null = null;
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line === "" || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "id") id = value;
    else if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  if (data.length === 0 && id === null && event === "message") return null;
  return { id, event, data: data.join("\n") };
}

export type RunStreamEvent = { id: string | null; event: SseEventName; data: Record<string, unknown> };
export type StreamState = "streaming" | "reconnecting";
// `lost`: the stream dropped and could not be resumed; the run itself may still be going.
export type StreamEnd = SseEventName | "lost" | "aborted";
export type StreamResult = { runId: string | null; lastEventId: string | null; ended: StreamEnd; reconnects: number };

export type FollowOptions = {
  // Each call opens one attempt; its signal ends that attempt (outside abort or the stall watchdog)
  // and should go to fetch so the connection really closes.
  open: (signal: AbortSignal) => Promise<Response>;
  reconnect: (runId: string, lastEventId: string | null, signal: AbortSignal) => Promise<Response>;
  onEvent: (event: RunStreamEvent) => void;
  onState?: (state: StreamState) => void;
  signal?: AbortSignal;
  maxReconnects?: number;
  retryDelayMs?: number;
  stallMs?: number;
};

export const MAX_RECONNECTS = 5;
export const RETRY_DELAY_MS = 1000;
// The backend writes a `: keepalive` comment every sse_keepalive_s = 10 s
// (backend/ffcore/core/config.py, backend/ffcore/runtime/events.py) while a run is quiet.
export const SSE_KEEPALIVE_MS = 10_000;
// Stall watchdog (FOLLOWUP-188, sse-sessiz-kopus): a half-open connection (backend killed, a proxy
// dropping an idle socket) sends nothing and never closes. Three missed keepalives end the attempt;
// the Last-Event-ID reconnect / `lost` path takes over, so a silent stream never looks live.
// Worst case until `lost`: STALL_MS + maxReconnects × (retryDelayMs + STALL_MS).
export const STALL_MS = 3 * SSE_KEEPALIVE_MS;

function parseData(raw: string): Record<string, unknown> {
  if (raw === "") return {};
  const value: unknown = JSON.parse(raw);
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : { value };
}

// One attempt of a stream (shared with lib/eval-stream.ts): its own AbortController, chained to the
// outside signal and fired by the watchdog when nothing arrived for `stallMs` (the request itself
// included). `alive()` restarts the watchdog; `end()` clears the timer and the listener.
export type Attempt = { signal: AbortSignal; alive: () => void; end: () => void; spoke: () => void };

export function startAttempt(stallMs: number, outside: AbortSignal | undefined, spoke: () => void = () => {}): Attempt {
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
export function openWithin(attempt: Attempt, open: (signal: AbortSignal) => Promise<Response>): Promise<Response> {
  return new Promise<Response>((resolve, reject) => {
    if (attempt.signal.aborted) return reject(new DOMException("attempt ended", "AbortError"));
    attempt.signal.addEventListener("abort", () => reject(new DOMException("attempt ended", "AbortError")), { once: true });
    open(attempt.signal).then(resolve, reject);
  });
}

export const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve) => {
    if (ms <= 0) return resolve();
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });

// Reads one response body to its end; returns the terminal event name, or null if it stopped:
// closed, failed to read (a drop, K-SSE-0002) or ended by the attempt (abort, watchdog). Every raw
// chunk restarts the watchdog, comments included (`: keepalive` makes no message but is a sign of
// life). A broken data line still throws: a broken event is not a drop, and no end is guessed.
async function drain(
  response: Response,
  state: { runId: string | null; lastEventId: string | null },
  onEvent: (event: RunStreamEvent) => void,
  attempt: Attempt,
): Promise<SseEventName | null> {
  if (!response.ok || !response.body) return null;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  const stop = () => void reader.cancel().catch(() => {});
  attempt.signal.addEventListener("abort", stop, { once: true });
  if (attempt.signal.aborted) stop(); // ended before reading: the abort event is already past (r1 NOTE-2)
  try {
    for (;;) {
      if (attempt.signal.aborted) return null;
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await reader.read();
      } catch {
        return null;
      }
      if (attempt.signal.aborted) return null;
      attempt.alive();
      const { done, value } = chunk;
      const messages = parser.push(done ? decoder.decode() : decoder.decode(value, { stream: true }));
      for (const message of messages) {
        if (message.id !== null) state.lastEventId = message.id;
        if (!isKnownEvent(message.event)) continue; // C9: unknown names are ignored, not mapped
        const data = parseData(message.data);
        if (state.runId === null && typeof data.run_id === "string") state.runId = data.run_id;
        onEvent({ id: message.id, event: message.event, data });
        if (isTerminalEvent(message.event)) return message.event;
      }
      if (done) return null;
    }
  } finally {
    attempt.signal.removeEventListener("abort", stop);
    reader.releaseLock();
  }
}

// Follows a run from its first response; when the stream drops (closes, fails to read or stays
// silent for stallMs) before a terminal event it reconnects with Last-Event-ID (06a GET
// /runs/{id}/stream). Closing never cancels the run. A refused first request still throws.
export async function followRunStream(options: FollowOptions): Promise<StreamResult> {
  const max = options.maxReconnects ?? MAX_RECONNECTS;
  const delay = options.retryDelayMs ?? RETRY_DELAY_MS;
  const stallMs = options.stallMs ?? STALL_MS;
  const state = { runId: null as string | null, lastEventId: null as string | null };
  let reconnects = 0;

  const attemptOnce = async (open: (signal: AbortSignal) => Promise<Response>, isReconnect: boolean): Promise<SseEventName | null> => {
    const attempt = startAttempt(stallMs, options.signal);
    try {
      let response: Response;
      try {
        response = await openWithin(attempt, open);
      } catch (error) {
        // an ended attempt or a failed reconnect is a drop; a refused first request is the caller's
        if (attempt.signal.aborted || isReconnect) return null;
        throw error;
      }
      attempt.alive();
      if (isReconnect && response.ok) options.onState?.("streaming");
      return await drain(response, state, options.onEvent, attempt);
    } finally {
      attempt.end();
    }
  };

  options.onState?.("streaming");
  let ended = await attemptOnce(options.open, false);
  while (ended === null) {
    if (options.signal?.aborted) return { ...state, ended: "aborted", reconnects };
    if (state.runId === null || reconnects >= max) return { ...state, ended: "lost", reconnects };
    reconnects += 1;
    options.onState?.("reconnecting");
    await sleep(delay, options.signal);
    if (options.signal?.aborted) continue;
    const runId = state.runId;
    ended = await attemptOnce((signal) => options.reconnect(runId, state.lastEventId, signal), true);
  }
  return { ...state, ended, reconnects };
}
