// @vitest-environment jsdom
import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { EvalSummaryView } from "@/components/eval/eval-summary-view";
import { OUTCOMES } from "@/lib/eval-summary";

import { evalRun, renderAs } from "./eval-support";

afterEach(cleanup);

const summary = {
  n: 4,
  scored: 2,
  not_run: { approval_required: 1, "partial:approval_rejected": 1, brand_new_reason: 1 },
  passed_items: 1,
  pass_rate: 0.5,
  pass_threshold: 0.85,
  passed: false,
  complete: false,
  scores: { contains: 0.75 },
  outcomes: Object.fromEntries(OUTCOMES.map((o) => [o, o === "answered" ? 2 : 0])),
  styles: { dogrudan: { n: 3, passed: 1, outcomes: { answered: 2 } } },
  worst: [{ item_id: "item-2", style: "dogrudan", outcome: "answered", passed: false, mean: 0.25, note: "" }],
  errors: { judge_out_of_time: 1, "advance_failed:ner_misconfigured": 1 },
  warm_cache: true,
  warmup_ms: 1200,
  latency_ms: { p50: 800, max: 2100 },
};

describe("test_10c1_6_eval_run_view", () => {
  it("shows failed, incomplete, n/N, not-run reasons and errors as written (nothing invented)", () => {
    renderAs("analyst", "edit", <EvalSummaryView run={evalRun({ summary })} />);
    expect(screen.getByTestId("eval-passed").textContent).toMatch(/not passed/i);
    expect(screen.getByTestId("eval-complete").textContent).toMatch(/incomplete/i);
    expect(screen.getByTestId("eval-scored").textContent).toContain("2 / 4");
    const notRun = screen.getByTestId("eval-not-run");
    expect(within(notRun).getByText("approval_required")).toBeTruthy();
    expect(within(notRun).getByText(/does not wait for approvals/i)).toBeTruthy();
    expect(within(notRun).getByText("partial:approval_rejected")).toBeTruthy();
    expect(within(notRun).getByText("brand_new_reason")).toBeTruthy();
    const errors = screen.getByTestId("eval-errors");
    expect(within(errors).getByText("judge_out_of_time")).toBeTruthy();
    expect(within(errors).getByText("advance_failed:ner_misconfigured")).toBeTruthy();
    expect(screen.getByTestId("eval-warmup").textContent).toContain("1,200");
  });

  // 10c-2 D8 (FOLLOWUP-185): the full item table (test_10c2_4) replaces the 10-worst stand-in.
  it("has no 10-worst stand-in table any more", () => {
    renderAs("analyst", "edit", <EvalSummaryView run={evalRun({ summary })} />);
    expect(screen.queryByTestId("eval-worst")).toBeNull();
    expect(screen.queryByTestId("eval-worst-note")).toBeNull();
  });

  it("fails loudly when the summary cannot be read, naming the field", () => {
    renderAs("analyst", "edit", <EvalSummaryView run={evalRun({ summary: { ...summary, complete: "yes" } })} />);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toMatch(/summary could not be read/i);
    expect(alert.textContent).toContain("complete");
  });

  it("says there is no summary yet for a live exam, and shows the error code of a failed one", () => {
    renderAs("analyst", "edit", <EvalSummaryView run={evalRun({ status: "running", summary: null })} />);
    expect(screen.getByTestId("eval-no-summary")).toBeTruthy();
    cleanup();
    renderAs("analyst", "edit", <EvalSummaryView run={evalRun({ status: "failed", error_code: "definition_changed", summary: null })} />);
    expect(screen.getByTestId("eval-error-code").textContent).toContain("definition_changed");
  });
});
