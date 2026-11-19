// @vitest-environment jsdom
import { QueryClient } from "@tanstack/react-query";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvalItemsTable } from "@/components/eval/eval-items-table";
import { EVAL_ITEMS_PAGE } from "@/lib/api/eval-queries";

import { evalRun, renderAs } from "./eval-support";

// 10c-2 D8 (FOLLOWUP-185): the exam page shows every item, a page at a time, from
// GET …/eval-runs/{id}/items; the status filter and paging are the endpoint's own parameters.
// Not-run codes are shown as written next to their explanation; a failed read is an error, never
// an empty table.

const ITEMS = "/api/v1/projects/p1/eval-runs/e1/items";
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function row(item_id: string, over: Record<string, unknown> = {}) {
  return {
    item_id,
    style: "dogrudan",
    scored: true,
    passed: true,
    mean: 1,
    outcome: "answered",
    note: "",
    repeats_not_run: "",
    attempts: 1,
    run_ids: [`run-${item_id}`],
    scores: [{ name: "contains", value: 1, passed: true, status: "ok", comment: "" }],
    ...over,
  };
}

const PAGE = [
  row("q2", { passed: false, mean: 0.25, scores: [{ name: "contains", value: 0.25, passed: false, status: "ok", comment: "" }] }),
  row("q3", { passed: null, mean: null, outcome: null, note: "approval_required", scores: [] }),
  row("q1"),
  row("q4", { scored: false, passed: null, mean: null, outcome: null, attempts: 0, run_ids: [], scores: [] }),
];

function stub(answer: (url: URL) => Response) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => answer(new URL(typeof input === "string" ? input : input.toString(), "http://console")));
  vi.stubGlobal("fetch", fetchMock);
  return () => fetchMock.mock.calls.map(([input]) => new URL(String(input), "http://console")).filter((u) => u.pathname === ITEMS);
}

function render() {
  renderAs("analyst", "edit", <EvalItemsTable projectId="p1" run={evalRun()} />, new QueryClient({ defaultOptions: { queries: { retry: false } } }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("test_10c2_4_eval_items", () => {
  it("shows every item of the page with its result, scores, note and run link", async () => {
    const calls = stub(() => json({ data: PAGE, total: 4, limit: EVAL_ITEMS_PAGE, offset: 0 }));
    render();
    const table = await screen.findByTestId("eval-items");
    expect(calls()[0].searchParams.get("status")).toBe("all");
    expect(calls()[0].searchParams.get("limit")).toBe(String(EVAL_ITEMS_PAGE));
    expect(calls()[0].searchParams.get("offset")).toBe("0");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.dataset.item)).toEqual(["q2", "q3", "q1", "q4"]);
    expect(rows.map((r) => r.dataset.result)).toEqual(["failed", "not_run", "passed", "pending"]);
    expect(within(rows[0]).getByText(/contains/)).toBeTruthy();
    expect(within(rows[1]).getByText("approval_required")).toBeTruthy();
    expect(within(rows[1]).getByText(/does not wait for approvals/i)).toBeTruthy();
    expect(within(rows[2]).getByRole("link").getAttribute("href")).toBe("/runs/run-q1");
    expect(screen.getByTestId("eval-items-range").textContent).toContain("1–4 / 4");
  });

  it("asks the endpoint for the chosen status and starts again from the first page", async () => {
    const calls = stub((url) => json({ data: url.searchParams.get("status") === "failed" ? [PAGE[0]] : PAGE, total: 4, limit: EVAL_ITEMS_PAGE, offset: 0 }));
    render();
    await screen.findByTestId("eval-items");
    fireEvent.click(screen.getByTestId("eval-items-filter-failed"));
    await waitFor(() => expect(calls().at(-1)?.searchParams.get("status")).toBe("failed"));
    expect(screen.getByTestId("eval-items-filter-failed").getAttribute("aria-pressed")).toBe("true");
    await waitFor(() => expect(within(screen.getByTestId("eval-items")).getAllByRole("row")).toHaveLength(2));
  });

  it("pages with the endpoint's offset and stops at the last page", async () => {
    const total = EVAL_ITEMS_PAGE + 3;
    const calls = stub((url) => {
      const offset = Number(url.searchParams.get("offset"));
      const data = Array.from({ length: offset === 0 ? EVAL_ITEMS_PAGE : 3 }, (_, i) => row(`q${offset + i}`));
      return json({ data, total, limit: EVAL_ITEMS_PAGE, offset });
    });
    render();
    await screen.findByTestId("eval-items");
    expect((screen.getByTestId("eval-items-prev") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByTestId("eval-items-next"));
    await waitFor(() => expect(calls().at(-1)?.searchParams.get("offset")).toBe(String(EVAL_ITEMS_PAGE)));
    await waitFor(() => expect(screen.getByTestId("eval-items-range").textContent).toContain(`${EVAL_ITEMS_PAGE + 1}–${total} / ${total}`));
    expect((screen.getByTestId("eval-items-next") as HTMLButtonElement).disabled).toBe(true);
  });

  it("reports a failed read with its code instead of an empty table", async () => {
    stub(() => json({ error: { code: "eval_run_not_found", type: "not_found_error", message: "gone" } }, 404));
    render();
    const alert = await screen.findByTestId("query-error");
    expect(alert.textContent).toContain("eval_run_not_found");
    expect(screen.queryByTestId("eval-items")).toBeNull();
  });
});
