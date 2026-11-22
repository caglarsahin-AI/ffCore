// @vitest-environment jsdom
import { QueryClient } from "@tanstack/react-query";
import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MemoryPage } from "@/components/memory/memory-page";

import { renderAs } from "./eval-support";

// 14-2 D5 (brief 14 "Kullanıcı kontrolü"): the member's own memory page. The list shows kind, text,
// when it was learned and how often it was used; edit, delete, delete all (confirmed), remember
// this, and turning memory off and on (opt-out). Read access keeps it all open: memory is the
// member's own data (14-1, own-data exception).

const P = "/api/v1/projects/p1";
const ITEM = {
  id: "m1", kind: "preference", text: "Tabloları TL cinsinden isterim.", agent_id: null, status: "active", confidence: 1,
  source_run_id: null, supersedes_id: null, created_at: "2026-11-20T10:00:00Z", updated_at: "2026-11-20T10:00:00Z",
  last_used_at: "2026-11-21T10:00:00Z", use_count: 3,
};
const ARCHIVED = { ...ITEM, id: "m0", text: "Tablolar USD olsun.", status: "archived", use_count: 1 };

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });
type Call = [string, RequestInit | undefined];

function serve(over: (url: string, init?: RequestInit) => Response | null = () => null, state = { items: [ITEM, ARCHIVED], optedOut: false }) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const hit = over(url, init);
    if (hit) return hit;
    const method = init?.method ?? "GET";
    if (url === `${P}/memories` && method === "GET") return json({ items: state.items });
    if (url === `${P}/memories/opt-out` && method === "GET") return json({ opted_out: state.optedOut });
    return json({ error: { code: "unexpected_test_call", type: "api_error", message: `${method} ${url}` } }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}
const calls = (mock: ReturnType<typeof serve>) => (mock.mock.calls as Call[]).map(([u, i]) => `${i?.method ?? "GET"} ${String(u)}`);

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("test_14_memory_page", () => {
  it("lists the active items with kind, text, learned date and use count; archived ones apart", async () => {
    serve();
    renderAs("user", "edit", <MemoryPage projectId="p1" />, client());
    const row = await screen.findByTestId("memory-item");
    expect(row.getAttribute("data-id")).toBe("m1");
    expect(within(row).getByTestId("memory-item-text").textContent).toBe(ITEM.text);
    expect(within(row).getByTestId("memory-item-kind").textContent).toBe("Preference");
    expect(within(row).getByTestId("memory-item-uses").textContent).toContain("3");
    expect(within(row).getByTestId("memory-item-learned").textContent).not.toBe("");
    // Archived items are shown in their own collapsed section, not in the list.
    expect(screen.getAllByTestId("memory-item")).toHaveLength(1);
    expect(screen.getByTestId("memory-archived").textContent).toContain("1");
  });

  it("edits an item in place with PATCH", async () => {
    const mock = serve((url, init) =>
      url === `${P}/memories/m1` && init?.method === "PATCH" ? json({ ...ITEM, text: JSON.parse(String(init.body)).text }) : null,
    );
    renderAs("user", "edit", <MemoryPage projectId="p1" />, client());
    fireEvent.click(await screen.findByTestId("memory-item-edit"));
    fireEvent.change(screen.getByTestId("memory-item-edit-input"), { target: { value: "Tablolar TL olsun." } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("memory-item-edit-save"));
    });
    await waitFor(() => expect(calls(mock)).toContain(`PATCH ${P}/memories/m1`));
    const patch = (mock.mock.calls as Call[]).find(([u, i]) => String(u) === `${P}/memories/m1` && i?.method === "PATCH")!;
    expect(JSON.parse(String(patch[1]?.body))).toEqual({ text: "Tablolar TL olsun." });
  });

  it("deletes one item at once and every item only after the confirmation", async () => {
    const mock = serve((url, init) => (init?.method === "DELETE" && (url === `${P}/memories/m1` || url === `${P}/memories`) ? new Response(null, { status: 204 }) : null));
    renderAs("user", "edit", <MemoryPage projectId="p1" />, client());
    await act(async () => {
      fireEvent.click(await screen.findByTestId("memory-item-delete"));
    });
    await waitFor(() => expect(calls(mock)).toContain(`DELETE ${P}/memories/m1`));
    fireEvent.click(screen.getByTestId("memory-delete-all"));
    expect(calls(mock)).not.toContain(`DELETE ${P}/memories`);
    await act(async () => {
      fireEvent.click(screen.getByTestId("memory-delete-all-confirm"));
    });
    await waitFor(() => expect(calls(mock)).toContain(`DELETE ${P}/memories`));
  });

  it("remembers a text with POST and shows a refused text's reason", async () => {
    const mock = serve((url, init) => {
      if (url !== `${P}/memories` || init?.method !== "POST") return null;
      const text = JSON.parse(String(init.body)).text;
      return text.includes("13648065508")
        ? json({ error: { code: "memory_pii_blocked", type: "invalid_request_error", message: "x" } }, 400)
        : json({ ...ITEM, id: "m2", text }, 201);
    });
    renderAs("user", "edit", <MemoryPage projectId="p1" />, client());
    fireEvent.change(await screen.findByTestId("memory-remember-input"), { target: { value: "Raporları sabah isterim." } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("memory-remember-save"));
    });
    await waitFor(() => expect(calls(mock)).toContain(`POST ${P}/memories`));
    fireEvent.change(screen.getByTestId("memory-remember-input"), { target: { value: "TC 13648065508" } });
    await act(async () => {
      fireEvent.click(screen.getByTestId("memory-remember-save"));
    });
    const error = await screen.findByTestId("memory-error");
    expect(error.textContent).toContain("Personal data");
    expect(error.textContent).toContain("memory_pii_blocked");
  });

  it("turns memory off and on (opt-out) and says what off means", async () => {
    const state = { items: [ITEM], optedOut: false };
    const mock = serve((url, init) => {
      if (url !== `${P}/memories/opt-out`) return null;
      if (init?.method === "PUT") {
        state.optedOut = true;
        return json({ opted_out: true });
      }
      if (init?.method === "DELETE") {
        state.optedOut = false;
        return json({ opted_out: false });
      }
      return null;
    }, state);
    renderAs("user", "read", <MemoryPage projectId="p1" />, client());
    const toggle = await screen.findByTestId("memory-opt-out");
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    await act(async () => {
      fireEvent.click(toggle);
    });
    await waitFor(() => expect(calls(mock)).toContain(`PUT ${P}/memories/opt-out`));
    expect(await screen.findByTestId("memory-off-note")).toBeTruthy();
    await act(async () => {
      fireEvent.click(screen.getByTestId("memory-opt-out"));
    });
    await waitFor(() => expect(calls(mock)).toContain(`DELETE ${P}/memories/opt-out`));
  });

  it("says when there is nothing remembered yet", async () => {
    serve(() => null, { items: [], optedOut: false });
    renderAs("user", "edit", <MemoryPage projectId="p1" />, client());
    expect(await screen.findByTestId("memory-empty")).toBeTruthy();
    expect((screen.getByTestId("memory-delete-all") as HTMLButtonElement).disabled).toBe(true);
  });

  it("is in Turkish too", async () => {
    serve();
    renderAs("user", "edit", <MemoryPage projectId="p1" />, client(), "tr");
    const row = await screen.findByTestId("memory-item");
    expect(within(row).getByTestId("memory-item-kind").textContent).toBe("Tercih");
  });
});
