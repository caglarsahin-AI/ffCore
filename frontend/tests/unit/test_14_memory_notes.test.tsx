// @vitest-environment jsdom
import { QueryClient } from "@tanstack/react-query";
import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MemoryNotes } from "@/components/memory/memory-notes";

import { renderAs } from "./eval-support";

// 14-2 D5 (K-14-0020 S2, S3): under an answer, "I took these into account" from the run's
// `memory_used` event (ids only; the texts come from the owner's `GET /memories?ids=`) with a
// one-click forget; after a live turn, "I noted: … [Delete]" from the extraction job's
// `progress.memory_extraction` event, read every few seconds for a while, with the delay said.

const P = "/api/v1/projects/p1";
const item = (id: string, text: string) => ({
  id, kind: "preference", text, agent_id: null, status: "active", confidence: 1, source_run_id: "r1", supersedes_id: null,
  created_at: "2026-11-20T10:00:00Z", updated_at: "2026-11-20T10:00:00Z", last_used_at: null, use_count: 1,
});
const event = (seq: number, type: string, payload: Record<string, unknown>) => ({ seq, ts: "2026-11-22T10:00:00Z", type, iteration: null, payload });
const BUDGET_ON = event(2, "budget", { memory: "on", phase: "planned" });
const USED = event(3, "memory_used", { items: [{ id: "m1", kind: "preference" }], dropped: [] });
const DONE = event(9, "done", {});

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });
type Call = [string, RequestInit | undefined];

function serve(events: () => unknown[], memories: Record<string, ReturnType<typeof item>>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url === `${P}/runs/r1/events`) return json({ items: events() });
    if (url.startsWith(`${P}/memories?`) && (init?.method ?? "GET") === "GET") {
      const ids = new URL(url, "http://x").searchParams.getAll("ids");
      return json({ items: ids.map((id) => memories[id]).filter(Boolean) });
    }
    if (init?.method === "DELETE" && url.startsWith(`${P}/memories/`)) {
      delete memories[url.split("/").pop()!];
      return new Response(null, { status: 204 });
    }
    return json({ error: { code: "unexpected_test_call", type: "api_error", message: url } }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("test_14_memory_notes", () => {
  it("shows the items the answer used and forgets one with a click", async () => {
    const memories = { m1: item("m1", "Tabloları TL cinsinden isterim.") };
    const mock = serve(() => [BUDGET_ON, USED, DONE], memories);
    renderAs("user", "edit", <MemoryNotes projectId="p1" runId="r1" watch={false} />, client());
    const note = await screen.findByTestId("memory-used");
    fireEvent.click(within(note).getByTestId("memory-used-toggle"));
    expect((await within(note).findByTestId("memory-used-item")).textContent).toContain("Tabloları TL cinsinden isterim.");
    const byIds = (mock.mock.calls as Call[]).find(([u]) => String(u).startsWith(`${P}/memories?`));
    expect(String(byIds![0])).toBe(`${P}/memories?ids=m1`);
    await act(async () => {
      fireEvent.click(within(note).getByTestId("memory-forget"));
    });
    await waitFor(() => expect((mock.mock.calls as Call[]).some(([u, i]) => String(u) === `${P}/memories/m1` && i?.method === "DELETE")).toBe(true));
    await waitFor(() => expect(screen.queryByTestId("memory-used-item")).toBeNull());
  });

  it("shows nothing when the run used no memory (memory off, opted out)", async () => {
    serve(() => [event(2, "budget", { memory: "opt_out" }), DONE], {});
    renderAs("user", "edit", <MemoryNotes projectId="p1" runId="r1" watch />, client());
    await waitFor(() => expect(screen.queryByTestId("memory-notes-read")).not.toBeNull());
    expect(screen.queryByTestId("memory-used")).toBeNull();
    expect(screen.queryByTestId("memory-noted")).toBeNull();
    expect(screen.queryByTestId("memory-noted-later")).toBeNull();
  });

  it("reads the run again until the extraction outcome arrives, then shows what was noted", async () => {
    const memories = { m1: item("m1", "Tabloları TL cinsinden isterim."), m2: item("m2", "Raporları sabah ister.") };
    let reads = 0;
    const mock = serve(() => {
      reads += 1;
      const base = [BUDGET_ON, USED, DONE];
      return reads < 2 ? base : [...base, event(10, "progress", { memory_extraction: { candidates: 1, written: ["m2"], archived: [], rejected: {} } })];
    }, memories);
    renderAs("user", "edit", <MemoryNotes projectId="p1" runId="r1" watch pollMs={20} limitMs={5000} />, client());
    const noted = await screen.findByTestId("memory-noted", {}, { timeout: 2000 });
    expect(within(noted).getByTestId("memory-noted-item").textContent).toContain("Raporları sabah ister.");
    await act(async () => {
      fireEvent.click(within(noted).getByTestId("memory-noted-delete"));
    });
    await waitFor(() => expect((mock.mock.calls as Call[]).some(([u, i]) => String(u) === `${P}/memories/m2` && i?.method === "DELETE")).toBe(true));
    const readsAtEnd = reads;
    await new Promise((r) => setTimeout(r, 100));
    expect(reads).toBe(readsAtEnd); // the outcome is in: no more reading
  });

  it("says nothing when the job wrote nothing or skipped", async () => {
    serve(() => [BUDGET_ON, DONE, event(10, "progress", { memory_extraction: { skipped: "memory_opted_out" } })], {});
    renderAs("user", "edit", <MemoryNotes projectId="p1" runId="r1" watch pollMs={20} limitMs={5000} />, client());
    await waitFor(() => expect(screen.queryByTestId("memory-notes-read")).not.toBeNull());
    expect(screen.queryByTestId("memory-noted")).toBeNull();
    expect(screen.queryByTestId("memory-noted-later")).toBeNull();
  });

  it("says that notes may come later when the job has not run within the time", async () => {
    let reads = 0;
    serve(() => {
      reads += 1;
      return [BUDGET_ON, DONE];
    }, {});
    renderAs("user", "edit", <MemoryNotes projectId="p1" runId="r1" watch pollMs={20} limitMs={150} />, client());
    expect(await screen.findByTestId("memory-noted-later", {}, { timeout: 2000 })).toBeTruthy();
    const readsAtEnd = reads;
    await new Promise((r) => setTimeout(r, 100));
    expect(reads).toBeLessThanOrEqual(readsAtEnd + 1);
  });

  it("does not read again for a stored answer (watch off)", async () => {
    let reads = 0;
    serve(() => {
      reads += 1;
      return [BUDGET_ON, DONE];
    }, {});
    renderAs("user", "edit", <MemoryNotes projectId="p1" runId="r1" watch={false} pollMs={20} limitMs={5000} />, client());
    await waitFor(() => expect(screen.queryByTestId("memory-notes-read")).not.toBeNull());
    await new Promise((r) => setTimeout(r, 100));
    expect(reads).toBe(1);
    expect(screen.queryByTestId("memory-noted-later")).toBeNull();
  });
});
