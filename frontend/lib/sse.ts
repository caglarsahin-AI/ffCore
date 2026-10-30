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
  open: () => Promise<Response>;
  reconnect: (runId: string, lastEventId: string | null) => Promise<Response>;
  onEvent: (event: RunStreamEvent) => void;
  onState?: (state: StreamState) => void;
  signal?: AbortSignal;
  maxReconnects?: number;
  retryDelayMs?: number;
};

export const MAX_RECONNECTS = 5;
export const RETRY_DELAY_MS = 1000;

function parseData(raw: string): Record<string, unknown> {
  if (raw === "") return {};
  const value: unknown = JSON.parse(raw);
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : { value };
}

// Reads one response body to its end; returns the terminal event name, or null if it just stopped.
async function drain(
  response: Response,
  state: { runId: string | null; lastEventId: string | null },
  onEvent: (event: RunStreamEvent) => void,
  signal?: AbortSignal,
): Promise<SseEventName | null> {
  if (!response.ok || !response.body) return null;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  try {
    for (;;) {
      if (signal?.aborted) return null;
      const { done, value } = await reader.read();
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
    reader.releaseLock();
  }
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// Follows a run from its first response; when the stream drops before a terminal event it
// reconnects with Last-Event-ID (06a GET /runs/{id}/stream). Closing never cancels the run.
export async function followRunStream(options: FollowOptions): Promise<StreamResult> {
  const max = options.maxReconnects ?? MAX_RECONNECTS;
  const delay = options.retryDelayMs ?? RETRY_DELAY_MS;
  const state = { runId: null as string | null, lastEventId: null as string | null };
  let reconnects = 0;
  options.onState?.("streaming");
  let ended = await drain(await options.open(), state, options.onEvent, options.signal);
  while (ended === null) {
    if (options.signal?.aborted) return { ...state, ended: "aborted", reconnects };
    if (state.runId === null || reconnects >= max) return { ...state, ended: "lost", reconnects };
    reconnects += 1;
    options.onState?.("reconnecting");
    if (delay > 0) await sleep(delay);
    let response: Response;
    try {
      response = await options.reconnect(state.runId, state.lastEventId);
    } catch {
      continue;
    }
    if (response.ok) options.onState?.("streaming");
    ended = await drain(response, state, options.onEvent, options.signal);
  }
  return { ...state, ended, reconnects };
}
