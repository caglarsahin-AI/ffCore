import { describe, expect, it } from "vitest";

import { initialRunView, reduceRunView } from "@/lib/run-view";
import type { RunStreamEvent } from "@/lib/sse";

const ev = (event: RunStreamEvent["event"], data: Record<string, unknown>, id = "1-0"): RunStreamEvent => ({ id, event, data });

function play(events: RunStreamEvent[]) {
  return events.reduce(reduceRunView, initialRunView());
}

describe("test_10bp2_18_run_view", () => {
  it("joins tokens into the answer and keeps the run id from the first progress event", () => {
    const view = play([ev("progress", { run_id: "r1" }), ev("token", { text: "Hel" }), ev("token", { text: "lo" })]);
    expect(view.runId).toBe("r1");
    expect(view.answer).toBe("Hello");
    expect(view.phase).toBe("running");
  });

  it("pairs a tool call with its result and keeps the masked arguments as sent", () => {
    const view = play([
      ev("tool_call", { tool_call_id: "c1", name: "db__run_sql", arguments: { sql: "[redacted]" }, needs_approval: false }),
      ev("tool_result", { tool_call_id: "c1", name: "db__run_sql", truncated: true, is_error: false, error_code: null, chars: 9000, ms: 40 }),
    ]);
    expect(view.tools).toEqual([
      {
        id: "c1",
        name: "db__run_sql",
        arguments: { sql: "[redacted]" },
        result: { truncated: true, isError: false, errorCode: null, chars: 9000, ms: 40 },
      },
    ]);
  });

  it("collects sources without duplicates", () => {
    const source = { n: 1, kb_key: "contracts", chunk_id: "k1", document_name: "a.pdf", page: 2, breadcrumb: "1 > 2" };
    const view = play([ev("sources", { sources: [source] }), ev("sources", { sources: [source, { ...source, n: 2, chunk_id: "k2" }] })]);
    expect(view.sources.map((s) => s.chunk_id)).toEqual(["k1", "k2"]);
  });

  it("waits on an approval with the approval id when the event carries it (07)", () => {
    const view = play([ev("approval_required", { action: "db__run_sql", arguments: { sql: "x" }, assign_to: "analyst", approval_id: "a1" })]);
    expect(view.phase).toBe("waiting_approval");
    expect(view.approval).toEqual({ action: "db__run_sql", arguments: { sql: "x" }, assignTo: "analyst", approvalId: "a1" });
  });

  it("waits on a question, and leaves a waiting phase when the run continues", () => {
    let view = play([ev("question", { question: "Which year?" })]);
    expect(view.phase).toBe("waiting_user");
    expect(view.question).toBe("Which year?");
    view = reduceRunView(view, ev("token", { text: "2025" }));
    expect(view.phase).toBe("running");
    expect(view.question).toBeNull();
  });

  it("ends with done or error, keeping the code and message of an error", () => {
    expect(play([ev("done", { status: "completed", outcome_label: "answered" })])).toMatchObject({ phase: "done", status: "completed", outcomeLabel: "answered" });
    expect(play([ev("error", { code: "limit_reached", status: "failed", message: "max_tool_calls" })])).toMatchObject({
      phase: "failed",
      status: "failed",
      error: { code: "limit_reached", message: "max_tool_calls" },
    });
  });

  it("records a fallback model and progress notes instead of dropping them", () => {
    const view = play([ev("fallback", { from: "a", to: "b" }), ev("progress", { stage: "output_buffered", reason: "guardrail_enforce" })]);
    expect(view.fallback).toEqual({ from: "a", to: "b" });
    expect(view.notes).toEqual([{ stage: "output_buffered", reason: "guardrail_enforce" }]);
  });
});
