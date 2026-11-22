// @vitest-environment jsdom
import { QueryClient } from "@tanstack/react-query";
import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MemoryTab } from "@/components/agent-wizard/memory-tab";
import { MemorySettingsForm } from "@/components/memory/settings-form";
import { MemoryStats } from "@/components/memory/stats-cards";

import { renderAs } from "./eval-support";

// 14-2 D6 (brief 14 "Yönetici kontrolü"): the project default and the agent's own memory settings
// (one form, `agent_id` for the agent's), saved on their own with PUT; the source says whose values
// are in use; without the installation's NER model memory cannot be turned on (S3); read access
// sees the values with the controls disabled. The statistics are numbers and kinds only.

const P = "/api/v1/projects/p1";
const SETTINGS = {
  enabled: false, allowed_kinds: ["profile", "preference", "fact", "decision"], max_items_per_user: 200, recall_top_k: 5,
  ttl_days: null, extraction_model: "memory-extract", agent_id: null, source: "default", ner_ready: true,
};
const MODELS = {
  data: [
    { key: "memory-extract", display_name: "Memory extract", category: "llm", is_active: true },
    { key: "chat-default", display_name: "Chat", category: "llm", is_active: true },
    { key: "embed", display_name: "Embed", category: "embedding", is_active: true },
  ],
};
const STATS = {
  users: [{ user_id: "u7", active: 4, archived: 1, by_kind: { preference: 3, profile: 1 }, used: 2, delete_events: 1 }],
  active: 4, archived: 1, by_kind: { preference: 3, profile: 1 }, use_rate: 0.5, delete_events: 1, opted_out_users: 2,
};
const MEMBERS = { data: [{ project_id: "p1", user_id: "u7", email: "ayse@example.org", full_name: "Ayşe Kaya", role: "user", access: "edit" }] };

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });
type Call = [string, RequestInit | undefined];

function serve(settings: Record<string, unknown> = SETTINGS) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith(`${P}/memories/settings`)) {
      if (init?.method === "PUT") {
        const agent = new URL(url, "http://x").searchParams.get("agent_id");
        return json({ ...JSON.parse(String(init.body)), agent_id: agent, source: agent ? "agent" : "project", ner_ready: true });
      }
      return json(settings);
    }
    if (url === `${P}/models`) return json(MODELS);
    if (url === `${P}/memories/stats`) return json(STATS);
    if (url === `${P}/members`) return json(MEMBERS);
    return json({ error: { code: "unexpected_test_call", type: "api_error", message: url } }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
const puts = (mock: ReturnType<typeof serve>) => (mock.mock.calls as Call[]).filter(([, i]) => i?.method === "PUT");

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("test_14_memory_settings", () => {
  it("saves the project default with PUT and says where the values come from", async () => {
    const mock = serve();
    renderAs("admin", "edit", <MemorySettingsForm projectId="p1" agentId={null} />, client());
    expect((await screen.findByTestId("memory-source")).textContent).toContain("default");
    fireEvent.click(screen.getByTestId("memory-enabled"));
    fireEvent.click(screen.getByLabelText("Decision"));
    fireEvent.change(screen.getByTestId("memory-max-items"), { target: { value: "50" } });
    fireEvent.change(screen.getByTestId("memory-ttl"), { target: { value: "90" } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("memory-save"));
    });
    await waitFor(() => expect(puts(mock)).toHaveLength(1));
    const [url, init] = puts(mock)[0];
    expect(String(url)).toBe(`${P}/memories/settings`);
    expect(JSON.parse(String(init?.body))).toEqual({
      enabled: true, allowed_kinds: ["profile", "preference", "fact"], max_items_per_user: 50, recall_top_k: 5, ttl_days: 90,
      extraction_model: "memory-extract",
    });
    expect(await screen.findByTestId("memory-saved")).toBeTruthy();
  });

  it("offers only the project's active chat models as the extraction model", async () => {
    serve();
    renderAs("admin", "edit", <MemorySettingsForm projectId="p1" agentId={null} />, client());
    const select = (await screen.findByTestId("memory-model")) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBe(2));
    expect(Array.from(select.options).map((o) => o.value)).toEqual(["memory-extract", "chat-default"]);
  });

  it("the agent tab saves the agent's own row", async () => {
    const mock = serve({ ...SETTINGS, enabled: true, source: "project" });
    renderAs("admin", "edit", <MemoryTab projectId="p1" agentId="a1" />, client());
    expect((await screen.findByTestId("memory-source")).textContent).toContain("project");
    await act(async () => {
      fireEvent.click(screen.getByTestId("memory-save"));
    });
    await waitFor(() => expect(puts(mock)).toHaveLength(1));
    expect(String(puts(mock)[0][0])).toBe(`${P}/memories/settings?agent_id=a1`);
  });

  it("the agent tab tells an analyst the settings are an administrator's, without reading them", () => {
    const mock = serve();
    renderAs("analyst", "edit", <MemoryTab projectId="p1" agentId="a1" />, client());
    expect(screen.getByTestId("memory-admin-only")).toBeTruthy();
    expect(mock).not.toHaveBeenCalled();
  });

  it("cannot turn memory on without the NER model and says why", async () => {
    serve({ ...SETTINGS, ner_ready: false });
    renderAs("admin", "edit", <MemorySettingsForm projectId="p1" agentId={null} />, client());
    const enabled = (await screen.findByTestId("memory-enabled")) as HTMLInputElement;
    expect(enabled.disabled).toBe(true);
    expect(screen.getByTestId("memory-ner-missing").textContent).toContain("NER");
  });

  it("read access sees the values with the controls disabled", async () => {
    serve({ ...SETTINGS, enabled: true, source: "project" });
    renderAs("admin", "read", <MemorySettingsForm projectId="p1" agentId={null} />, client());
    expect(((await screen.findByTestId("memory-enabled")) as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByTestId("memory-max-items") as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByTestId("memory-save") as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows a refused save's reason", async () => {
    const fetchMock = serve();
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === `${P}/models`) return json(MODELS);
      if (init?.method === "PUT") return json({ error: { code: "model_not_found", type: "invalid_request_error", message: "x" } }, 400);
      return json(SETTINGS);
    });
    renderAs("admin", "edit", <MemorySettingsForm projectId="p1" agentId={null} />, client());
    fireEvent.click(await screen.findByTestId("memory-enabled"));
    await act(async () => {
      fireEvent.click(screen.getByTestId("memory-save"));
    });
    expect((await screen.findByTestId("memory-error")).textContent).toContain("model_not_found");
  });
});

describe("test_14_memory_stats", () => {
  it("shows counts, kinds, use and delete numbers per member, never a text", async () => {
    serve();
    renderAs("admin", "read", <MemoryStats projectId="p1" />, client());
    expect((await screen.findByTestId("memory-stat-active")).textContent).toContain("4");
    expect(screen.getByTestId("memory-stat-use-rate").textContent).toContain("50");
    expect(screen.getByTestId("memory-stat-deletes").textContent).toContain("1");
    expect(screen.getByTestId("memory-stat-opted-out").textContent).toContain("2");
    const row = await screen.findByTestId("memory-stats-user");
    await waitFor(() => expect(row.textContent).toContain("Ayşe Kaya"));
    expect(row.textContent).toContain("Preference");
    expect(screen.getByTestId("memory-principle").textContent).toContain("cannot see");
  });
});
