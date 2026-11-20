// @vitest-environment jsdom
import { QueryClient } from "@tanstack/react-query";
import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ChatHome } from "@/components/chat/chat-home";
import { ChatScreen } from "@/components/chat/chat-screen";

import { renderAs } from "./eval-support";

// 11-1 (K-11-0002): the chat screen against a faked API: agent picker, a streamed answer with a
// tool card and a source card that opens the cited chunk, stored conversations, delete, and the
// read-only exception (chatting and deleting one's own conversation stay open).

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace, refresh: vi.fn() }),
  usePathname: () => "/chat",
}));

const P = "/api/v1/projects/p1";
const encoder = new TextEncoder();
const AGENTS = { items: [{ id: "a1", key: "asistan", name: "Contract assistant", description: "Answers from contracts" }] };
const CONVERSATIONS = {
  items: [{ id: "c1", agent_id: "a1", agent_key: "asistan", title: "Fesih süresi?", created_at: "2026-11-20T10:00:00Z", last_message_at: "2026-11-20T10:00:05Z" }],
};
const SOURCE = { n: 1, kb_key: "sozlesmeler", chunk_id: "ch1", document_id: "d1", document_name: "hizmet.pdf", page: 3, breadcrumb: "Madde 9", updated_at_source: "2024-05-01T00:00:00+00:00", rerank_score: 0.8 };

function msg(over: Record<string, unknown>) {
  return { id: "m1", role: "user", content: "Fesih süresi?", run_id: "r1", run_status: "completed", outcome_label: null, error_code: null, sources: null, feedback: null, low_confidence: null, created_at: "2026-11-20T10:00:00Z", ...over };
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function stream(events: [string, Record<string, unknown>][]) {
  const text = events.map(([event, data], i) => `id: ${i + 1}-0\nevent: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");
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

function serve(...routes: Route[]) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = urlOf(input);
    for (const route of routes) {
      const hit = route(url, init);
      if (hit) return hit;
    }
    if (url === `${P}/chat/agents`) return json(AGENTS);
    if (url.startsWith(`${P}/conversations?`) || url === `${P}/conversations`) return json(CONVERSATIONS);
    return json({ error: { code: "unexpected_test_call", type: "api_error", message: url } }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

beforeEach(() => {
  push.mockReset();
  replace.mockReset();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("test_11_2_chat_screen", () => {
  it("lists the published agents and links each to its chat", async () => {
    serve();
    renderAs("user", "edit", <ChatHome projectId="p1" />, client());
    const link = await screen.findByTestId("chat-agent");
    expect(link.textContent).toContain("Contract assistant");
    expect(link.getAttribute("href")).toBe("/chat/asistan");
  });

  it("asks for a project when none is selected, without calling the API", () => {
    const fetchMock = serve();
    renderAs("user", "edit", <ChatHome projectId={null} />, client());
    expect(screen.getByTestId("chat-no-project")).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("says so when the project has no published agent", async () => {
    serve((url) => (url === `${P}/chat/agents` ? json({ items: [] }) : undefined));
    renderAs("user", "edit", <ChatHome projectId="p1" />, client());
    expect(await screen.findByTestId("chat-no-agents")).toBeTruthy();
  });

  it("streams an answer with a tool card and opens the cited chunk", async () => {
    const fetchMock = serve(
      (url, init) =>
        url === `${P}/agents/asistan/runs` && init?.method === "POST"
          ? stream([
              ["progress", { run_id: "r1", status: "queued", conversation_id: "c9" }],
              ["tool_call", { tool_call_id: "t1", name: "crm__run_sql", arguments: { q: "select 1" } }],
              ["tool_result", { tool_call_id: "t1", is_error: false, chars: 10 }],
              ["sources", { sources: [SOURCE], blocked: [] }],
              ["token", { text: "30 gün " }],
              ["token", { text: "[1]." }],
              ["done", { run_id: "r1", status: "completed", outcome_label: "answered" }],
            ])
          : undefined,
      (url) => (url === `${P}/conversations/c9/messages` ? json({ items: [] }) : undefined),
      (url) => (url === `${P}/runs/r1/sources/ch1` ? json({ chunk_id: "ch1", document_id: "d1", document_name: "hizmet.pdf", page: 3, breadcrumb: "Madde 9", text: "Fesih bildirimi 30 gün.", updated_at_source: "2024-05-01T00:00:00Z" }) : undefined),
    );
    renderAs("user", "edit", <ChatScreen projectId="p1" agentKey="asistan" conversationId={null} />, client());
    await screen.findByTestId("chat-welcome");
    fireEvent.change(screen.getByTestId("chat-input"), { target: { value: "Fesih süresi?" } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("chat-send"));
    });
    await waitFor(() => expect(screen.getByTestId("chat-live-answer").textContent).toBe("30 gün [1]."));
    const sent = fetchMock.mock.calls.find(([u]) => urlOf(u as RequestInfo) === `${P}/agents/asistan/runs`)!;
    expect(JSON.parse(String((sent[1] as RequestInit).body))).toEqual({ input: "Fesih süresi?", channel: "chat" });
    expect(screen.getByTestId("chat-tool-card").textContent).toContain("Running SQL");
    expect(replace).toHaveBeenCalledWith("/chat/asistan/c9");
    const card = screen.getByTestId("chat-source-card");
    expect(card.textContent).toContain("hizmet.pdf");
    expect(card.textContent).toContain("page 3");
    fireEvent.click(card);
    expect((await screen.findByTestId("chat-source-text")).textContent).toContain("Fesih bildirimi 30 gün.");
  });

  it("shows a stored conversation with the declined badge and its sources", async () => {
    serve((url) =>
      url === `${P}/conversations/c1/messages`
        ? json({ items: [msg({}), msg({ id: "m2", role: "assistant", content: "Bu bilgi belgelerde yok.", outcome_label: "declined", sources: [SOURCE] })] })
        : undefined,
    );
    renderAs("user", "edit", <ChatScreen projectId="p1" agentKey="asistan" conversationId="c1" />, client());
    const messages = await screen.findAllByTestId("chat-message");
    expect(messages.map((m) => m.dataset.role)).toEqual(["user", "assistant"]);
    expect(screen.getByTestId("chat-badge").dataset.kind).toBe("declined");
    expect(screen.getByTestId("chat-source-card").textContent).toContain("2024");
  });

  it("deletes the open conversation after confirmation and goes back to a new one", async () => {
    const fetchMock = serve(
      (url) => (url === `${P}/conversations/c1/messages` ? json({ items: [msg({})] }) : undefined),
      (url, init) => (url === `${P}/conversations/c1` && init?.method === "DELETE" ? new Response(null, { status: 204 }) : undefined),
    );
    renderAs("analyst", "read", <ChatScreen projectId="p1" agentKey="asistan" conversationId="c1" />, client());
    fireEvent.click(await screen.findByTestId("chat-conversation-delete"));
    await act(async () => {
      fireEvent.click(await screen.findByTestId("chat-delete-confirm"));
    });
    await waitFor(() => expect(fetchMock.mock.calls.some(([u, i]) => urlOf(u as RequestInfo) === `${P}/conversations/c1` && (i as RequestInit)?.method === "DELETE")).toBe(true));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/chat/asistan"));
  });

  it("keeps sending open in read-only access (chat is the read-only exception)", async () => {
    serve();
    renderAs("analyst", "read", <ChatScreen projectId="p1" agentKey="asistan" conversationId={null} />, client());
    await screen.findByTestId("chat-welcome");
    fireEvent.change(screen.getByTestId("chat-input"), { target: { value: "Merhaba" } });
    expect((screen.getByTestId("chat-send") as HTMLButtonElement).disabled).toBe(false);
  });

  it("says an agent is not available when it is not among the published ones", async () => {
    serve();
    renderAs("user", "edit", <ChatScreen projectId="p1" agentKey="gizli" conversationId={null} />, client());
    expect(await screen.findByTestId("chat-agent-unavailable")).toBeTruthy();
    expect(screen.queryByTestId("chat-input")).toBeNull();
  });

  it("shows why a cited chunk cannot be opened (no silent empty text)", async () => {
    serve(
      (url) =>
        url === `${P}/conversations/c1/messages`
          ? json({ items: [msg({}), msg({ id: "m2", role: "assistant", content: "30 gün [1].", sources: [SOURCE] })] })
          : undefined,
      (url) => (url === `${P}/runs/r1/sources/ch1` ? json({ error: { code: "source_not_visible", type: "permission_error", message: "x" } }, 403) : undefined),
    );
    renderAs("user", "edit", <ChatScreen projectId="p1" agentKey="asistan" conversationId="c1" />, client());
    fireEvent.click(await screen.findByTestId("chat-source-card"));
    const error = await screen.findByTestId("chat-source-error");
    expect(error.textContent).toContain("source_not_visible");
  });

  it("names a failed run with its code instead of an empty answer", async () => {
    serve((url) => (url === `${P}/conversations/c1/messages` ? json({ items: [msg({ run_status: "failed", error_code: "guardrail_block" })] }) : undefined));
    renderAs("user", "edit", <ChatScreen projectId="p1" agentKey="asistan" conversationId="c1" />, client());
    expect((await screen.findByTestId("chat-run-error")).textContent).toContain("guardrail_block");
  });
});
