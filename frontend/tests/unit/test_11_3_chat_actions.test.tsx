// @vitest-environment jsdom
import { QueryClient } from "@tanstack/react-query";
import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatScreen } from "@/components/chat/chat-screen";

import { renderAs } from "./eval-support";

// 11-2 (K-11-0005): inline approval and the ask_user answer in the chat, the user's vote on an
// answer, the agent's portal settings, and a stream that drops mid-answer (11-1 r1 NOTE-1).

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace, refresh: vi.fn() }),
  usePathname: () => "/chat",
}));

const P = "/api/v1/projects/p1";
const encoder = new TextEncoder();
const AGENT = { id: "a1", key: "asistan", name: "Contract assistant", description: "Answers from contracts", portal_config: null };
const WAIT = { timeout: 4000 };

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

// SSE events with ids `${first + i}-0`; `open` leaves the stream without a terminal event.
function stream(events: [string, Record<string, unknown>][], first = 1) {
  const text = events.map(([event, data], i) => `id: ${first + i}-0\nevent: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
}

const urlOf = (input: RequestInfo | URL) => (typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url);
type Route = (url: string, init?: RequestInit) => Response | undefined;

function serve(agent: Record<string, unknown>, ...routes: Route[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = urlOf(input);
    for (const route of routes) {
      const hit = route(url, init);
      if (hit) return hit;
    }
    if (url === `${P}/chat/agents`) return json({ items: [agent] });
    if (url.startsWith(`${P}/conversations?`) || url === `${P}/conversations`) return json({ items: [] });
    if (url.startsWith(`${P}/conversations/`)) return json({ items: [] });
    return json({ error: { code: "unexpected_test_call", type: "api_error", message: url } }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const calls = (fetchMock: ReturnType<typeof serve>, url: string, method?: string) =>
  fetchMock.mock.calls.filter(([u, i]) => urlOf(u as RequestInfo) === url && (!method || (i as RequestInit | undefined)?.method === method));
const lastEventId = (call: unknown[]) => new Headers((call[1] as RequestInit | undefined)?.headers).get("Last-Event-ID");

const START = ["progress", { run_id: "r1", status: "queued", conversation_id: "c9" }] as [string, Record<string, unknown>];
const APPROVAL = ["approval_required", { approval_id: "ap1", action: "crm__update_ticket", arguments: { id: 7 }, assign_to: "analyst" }] as [string, Record<string, unknown>];
const QUESTION = ["question", { question: "Hangi sözleşme?" }] as [string, Record<string, unknown>];
const ANSWER: [string, Record<string, unknown>][] = [
  ["token", { text: "Tamam." }],
  ["done", { run_id: "r1", status: "completed", outcome_label: "answered" }],
];
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

async function ask(text = "Bileti güncelle") {
  await screen.findByTestId("chat-input");
  fireEvent.change(screen.getByTestId("chat-input"), { target: { value: text } });
  await act(async () => {
    fireEvent.click(screen.getByTestId("chat-send"));
  });
}

beforeEach(() => replace.mockReset());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("test_11_3_chat_actions", () => {
  it("lets an authorized member approve inline and follows the run from stream_after", async () => {
    const fetchMock = serve(
      AGENT,
      (url, init) => (url === `${P}/agents/asistan/runs` && init?.method === "POST" ? stream([START, APPROVAL]) : undefined),
      (url, init) => (url === `/api/v1/projects/p1/approvals/ap1/approve` && init?.method === "POST" ? json({ id: "ap1", status: "approved", stream_after: "2-0" }) : undefined),
      (url) => (url === `${P}/runs/r1/stream` ? stream(ANSWER, 3) : undefined),
    );
    renderAs("analyst", "edit", <ChatScreen projectId="p1" agentKey="asistan" conversationId={null} />, client());
    await ask();
    const prompt = await screen.findByTestId("chat-approval");
    expect(prompt.textContent).toContain("crm__update_ticket");
    fireEvent.change(screen.getByLabelText(/Note/), { target: { value: "Uygun." } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("chat-approve"));
    });
    await waitFor(() => expect(screen.getByTestId("chat-live-answer").textContent).toBe("Tamam."), WAIT);
    const decided = calls(fetchMock, `${P}/approvals/ap1/approve`, "POST");
    expect(JSON.parse(String((decided[0][1] as RequestInit).body))).toEqual({ note: "Uygun." });
    expect(lastEventId(calls(fetchMock, `${P}/runs/r1/stream`)[0])).toBe("2-0");
  });

  for (const [role, access] of [["analyst", "read"], ["user", "edit"]] as const) {
    it(`shows ${role}/${access} who approves instead of buttons, then goes on when someone else decides`, async () => {
      let polls = 0;
      const fetchMock = serve(
        AGENT,
        (url, init) => (url === `${P}/agents/asistan/runs` && init?.method === "POST" ? stream([START, APPROVAL]) : undefined),
        (url) => {
          if (url !== `${P}/runs/r1`) return undefined;
          polls += 1;
          return json({ id: "r1", status: polls === 1 ? "waiting_approval" : "running" });
        },
        (url) => (url === `${P}/runs/r1/stream` ? stream(ANSWER, 3) : undefined),
      );
      renderAs(role, access, <ChatScreen projectId="p1" agentKey="asistan" conversationId={null} />, client());
      await ask();
      const waiting = await screen.findByTestId("chat-approval-waiting");
      expect(waiting.textContent).toContain("Analyst");
      expect(screen.queryByTestId("chat-approve")).toBeNull();
      expect(screen.queryByTestId("chat-reject")).toBeNull();
      await waitFor(() => expect(screen.getByTestId("chat-live-answer").textContent).toBe("Tamam."), { timeout: 9000 });
      expect(lastEventId(calls(fetchMock, `${P}/runs/r1/stream`)[0])).toBe("2-0");
    }, 15_000);
  }

  it("says so when reading a waiting run fails (no silent stop)", async () => {
    serve(
      AGENT,
      (url, init) => (url === `${P}/agents/asistan/runs` && init?.method === "POST" ? stream([START, APPROVAL]) : undefined),
      (url) => (url === `${P}/runs/r1` ? json({ error: { code: "service_unavailable", type: "api_error", message: "x" } }, 503) : undefined),
    );
    renderAs("analyst", "read", <ChatScreen projectId="p1" agentKey="asistan" conversationId={null} />, client());
    await ask();
    const error = await screen.findByTestId("chat-poll-error", undefined, WAIT);
    expect(error.textContent).toContain("service_unavailable");
  });

  it("answers the agent's question and follows the run on", async () => {
    const fetchMock = serve(
      AGENT,
      (url, init) => (url === `${P}/agents/asistan/runs` && init?.method === "POST" ? stream([START, QUESTION]) : undefined),
      (url, init) => (url === `${P}/runs/r1/resume` && init?.method === "POST" ? json({ id: "r1", status: "queued" }) : undefined),
      (url) => (url === `${P}/runs/r1/stream` ? stream(ANSWER, 3) : undefined),
    );
    renderAs("analyst", "read", <ChatScreen projectId="p1" agentKey="asistan" conversationId={null} />, client());
    await ask("Sözleşme süresi?");
    const box = await screen.findByTestId("chat-question");
    expect(box.textContent).toContain("Hangi sözleşme?");
    fireEvent.change(screen.getByTestId("chat-answer-input"), { target: { value: "Hizmet sözleşmesi" } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("chat-answer-send"));
    });
    await waitFor(() => expect(screen.getByTestId("chat-live-answer").textContent).toBe("Tamam."), WAIT);
    const resumed = calls(fetchMock, `${P}/runs/r1/resume`, "POST");
    expect(JSON.parse(String((resumed[0][1] as RequestInit).body))).toEqual({ answer: "Hizmet sözleşmesi" });
    expect(lastEventId(calls(fetchMock, `${P}/runs/r1/stream`)[0])).toBe("2-0");
  });

  it("finishes an answer once after the stream drops mid-answer (Last-Event-ID)", async () => {
    const fetchMock = serve(
      AGENT,
      (url, init) => (url === `${P}/agents/asistan/runs` && init?.method === "POST" ? stream([START, ["token", { text: "30 " }]]) : undefined),
      (url) => (url === `${P}/runs/r1/stream` ? stream([["token", { text: "gün." }], ["done", { run_id: "r1", status: "completed", outcome_label: "answered" }]], 3) : undefined),
      (url) => (url === `${P}/runs/r1` ? json({ id: "r1", status: "running" }) : undefined),
    );
    renderAs("user", "edit", <ChatScreen projectId="p1" agentKey="asistan" conversationId={null} />, client());
    await ask("Fesih süresi?");
    await waitFor(() => expect(screen.getByTestId("chat-live-answer").textContent).toBe("30 gün."), WAIT);
    const reconnects = calls(fetchMock, `${P}/runs/r1/stream`);
    expect(reconnects).toHaveLength(1);
    expect(lastEventId(reconnects[0])).toBe("2-0");
  });

  const STORED = [
    { id: "m1", role: "user", content: "Fesih süresi?", run_id: "r1", run_status: "completed", outcome_label: null, error_code: null, sources: null, feedback: null, user_feedback: null, low_confidence: null, created_at: "2026-11-20T10:00:00Z" },
    { id: "m2", role: "assistant", content: "30 gün.", run_id: "r1", run_status: "completed", outcome_label: "answered", error_code: null, sources: null, feedback: null, user_feedback: null, low_confidence: null, created_at: "2026-11-20T10:00:05Z" },
  ];

  it("sends the user's vote as source chat, with an optional note", async () => {
    const fetchMock = serve(
      AGENT,
      (url) => (url === `${P}/conversations/c1/messages` ? json({ items: STORED }) : undefined),
      (url, init) => (url === `${P}/runs/r1/feedback` && init?.method === "POST" ? json({ run_id: "r1", vote: "wrong", note: null, by: "u1", at: "2026-11-20T10:01:00Z", score_sent: true }) : undefined),
    );
    renderAs("user", "edit", <ChatScreen projectId="p1" agentKey="asistan" conversationId="c1" />, client());
    await act(async () => {
      fireEvent.click(await screen.findByTestId("chat-vote-down"));
    });
    fireEvent.change(await screen.findByTestId("chat-vote-note"), { target: { value: "Madde yanlış." } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("chat-vote-send"));
    });
    await waitFor(() => expect(calls(fetchMock, `${P}/runs/r1/feedback`, "POST")).toHaveLength(1));
    const body = JSON.parse(String((calls(fetchMock, `${P}/runs/r1/feedback`, "POST")[0][1] as RequestInit).body));
    expect(body).toEqual({ vote: "wrong", note: "Madde yanlış.", source: "chat" });
  });

  it("shows the stored vote and disables voting in read-only access with the reason", async () => {
    const voted = STORED.map((m) => (m.role === "assistant" ? { ...m, user_feedback: { vote: "correct", note: null, by: "u1", at: "x" } } : m));
    serve(AGENT, (url) => (url === `${P}/conversations/c1/messages` ? json({ items: voted }) : undefined));
    renderAs("analyst", "read", <ChatScreen projectId="p1" agentKey="asistan" conversationId="c1" />, client());
    const up = (await screen.findByTestId("chat-vote-up")) as HTMLButtonElement;
    expect(up.getAttribute("aria-pressed")).toBe("true");
    expect(up.disabled).toBe(true);
    expect(up.closest("[data-read-only]")).not.toBeNull();
  });

  it("shows the portal welcome and example questions; an example fills the box, never sends", async () => {
    const portal = { ...AGENT, portal_config: { welcome: "Sözleşmeler hakkında sorun.", examples: ["Fesih süresi nedir?", "Cezai şart var mı?"], accent: "#0F766E" } };
    const fetchMock = serve(portal);
    renderAs("user", "edit", <ChatScreen projectId="p1" agentKey="asistan" conversationId={null} />, client());
    expect((await screen.findByTestId("chat-welcome")).textContent).toContain("Sözleşmeler hakkında sorun.");
    const examples = screen.getAllByTestId("chat-example");
    expect(examples.map((e) => e.textContent)).toEqual(["Fesih süresi nedir?", "Cezai şart var mı?"]);
    fireEvent.click(examples[0]);
    expect((screen.getByTestId("chat-input") as HTMLTextAreaElement).value).toBe("Fesih süresi nedir?");
    expect(calls(fetchMock, `${P}/agents/asistan/runs`, "POST")).toHaveLength(0);
    expect(screen.getByTestId("chat-screen").style.getPropertyValue("--chat-accent-light")).toBe("#0f766e");
  });
});
