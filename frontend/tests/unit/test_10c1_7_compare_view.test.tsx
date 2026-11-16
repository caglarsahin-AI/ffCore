// @vitest-environment jsdom
import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CompareView } from "@/components/eval/compare-view";
import type { Compare } from "@/lib/api/eval-queries";

import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

import { renderAs } from "./eval-support";

afterEach(cleanup);

const diff = (a: number | null, b: number | null) => ({ a, b, delta: a === null || b === null ? null : b - a });
const compare: Compare = {
  a: "ea",
  b: "eb",
  suite_id: "s1",
  complete: { ea: true, eb: false },
  config_differs: true,
  summary: {
    pass_rate: diff(0.5, 0.75),
    scored: diff(4, 3),
    passed_items: diff(2, 3),
    scores: { contains: diff(0.5, 0.8) },
    outcomes: { answered: diff(2, 3) },
    not_run: { b: { approval_required: 1 } },
  },
  counts: { fixed: 1, regressed: 1, same: 0, not_comparable: 1, only_a: 0, only_b: 0 },
  items: [
    { item_id: "i1", style: "dogrudan", change: "fixed", a: { passed: false, mean: 0.2, outcome: "declined", note: "" }, b: { passed: true, mean: 0.9, outcome: "answered", note: "" }, mean_delta: 0.7 },
    { item_id: "i2", style: "dolayli", change: "regressed", a: { passed: true, mean: 0.9, outcome: "answered", note: "" }, b: { passed: false, mean: 0.1, outcome: "not_retrieved", note: "" }, mean_delta: -0.8 },
    { item_id: "i3", style: "dolayli", change: "not_comparable", a: { passed: null, mean: null, outcome: null, note: "approval_required" }, b: { passed: null, mean: null, outcome: null, note: "approval_required" }, mean_delta: null },
  ],
  worst: [
    { item_id: "i2", style: "dolayli", change: "regressed", a: { passed: true, mean: 0.9, outcome: "answered", note: "" }, b: { passed: false, mean: 0.1, outcome: "not_retrieved", note: "" }, mean_delta: -0.8 },
  ],
};

describe("test_10c1_7_compare_view", () => {
  it("warns when the configurations differ and shows each exam's completeness", () => {
    renderAs("analyst", "read", <CompareView compare={compare} />);
    expect(screen.getByTestId("compare-config-differs")).toBeTruthy();
    expect(screen.getByTestId("compare-complete-a").textContent).toMatch(/complete/i);
    expect(screen.getByTestId("compare-complete-b").textContent).toMatch(/incomplete/i);
  });

  it("shows the summary differences and every item with its change; not comparable stays not comparable", () => {
    renderAs("analyst", "read", <CompareView compare={compare} />);
    expect(within(screen.getByTestId("compare-summary")).getByText("contains")).toBeTruthy();
    const items = screen.getByTestId("compare-items");
    expect(within(items).getByTestId("compare-item-i1").textContent).toMatch(/fixed/i);
    expect(within(items).getByTestId("compare-item-i2").textContent).toMatch(/regressed/i);
    expect(within(items).getByTestId("compare-item-i3").textContent).toMatch(/not comparable/i);
    expect(within(screen.getByTestId("compare-worst")).getByText("i2")).toBeTruthy();
    expect(screen.getByTestId("compare-counts").textContent).toContain("1");
  });

  // R-10C1-0003 MINOR-2: codes read as on the exam screen: a known scorer, outcome or not-run code
  // is translated with the raw code beside it; an unknown code stays raw (nothing guessed).
  const coded: Compare = {
    ...compare,
    summary: {
      ...compare.summary,
      scores: { contains: diff(0.5, 0.8), my_scorer: diff(0.1, 0.2) },
      outcomes: { answered: diff(2, 3), weird_outcome: diff(0, 1) },
      not_run: { b: { approval_required: 1, "partial:waiting_user": 2, new_code: 1 } },
    },
    items: [
      ...compare.items,
      { item_id: "i4", style: "dogrudan", change: "same", a: { passed: true, mean: 1, outcome: "odd_outcome", note: "" }, b: { passed: true, mean: 1, outcome: "odd_outcome", note: "" }, mean_delta: 0 },
    ],
  };

  it("translates known codes in Turkish and keeps unknown codes raw", () => {
    renderAs("analyst", "read", <CompareView compare={coded} />, undefined, "tr");
    const summary = screen.getByTestId("compare-summary");
    expect(within(summary).getByText(tr.Evaluations.scorers.contains)).toBeTruthy();
    expect(within(summary).getByText("contains").className).toContain("font-mono");
    expect(within(summary).getByText("my_scorer").className).toContain("font-mono");
    expect(summary.textContent).toContain(tr.Evaluations.compare.outcomeRow.replace("{outcome}", tr.Evaluations.outcomes.answered));
    expect(within(summary).getByText("weird_outcome").className).toContain("font-mono");
    expect(summary.textContent).not.toContain("Outcome:");

    const notRun = screen.getByTestId("compare-not-run");
    expect(notRun.textContent).toContain(tr.Evaluations.notRun.approval_required);
    expect(notRun.textContent).toContain(tr.Evaluations.summary.partial.replace("{meaning}", tr.Evaluations.notRun.waiting_user));
    expect(notRun.textContent).toContain(tr.Evaluations.summary.unknownCode);
    expect(within(notRun).getByText("new_code").className).toContain("font-mono");
    expect(notRun.textContent).not.toMatch(/approval_required=1/);

    const items = screen.getByTestId("compare-items");
    expect(within(items).getByTestId("compare-item-i2").textContent).toContain(tr.Evaluations.outcomes.not_retrieved);
    expect(within(items).getByTestId("compare-item-i4").textContent).toContain("odd_outcome");
  });

  it("shows no empty not-run table for a side without codes", () => {
    renderAs("analyst", "read", <CompareView compare={{ ...compare, summary: { ...compare.summary, not_run: { a: {}, b: { approval_required: 1 } } } }} />);
    expect(screen.queryByTestId("compare-not-run-a")).toBeNull();
    expect(screen.getByTestId("compare-not-run-b")).toBeTruthy();
    cleanup();
    renderAs("analyst", "read", <CompareView compare={{ ...compare, summary: { ...compare.summary, not_run: { a: {}, b: {} } } }} />);
    expect(screen.queryByTestId("compare-not-run")).toBeNull();
  });

  it("uses the same words as the exam screen in English", () => {
    renderAs("analyst", "read", <CompareView compare={coded} />);
    const items = screen.getByTestId("compare-items");
    expect(within(items).getByTestId("compare-item-i1").textContent).toContain(en.Evaluations.outcomes.answered);
    expect(within(screen.getByTestId("compare-summary")).getByText(en.Evaluations.scorers.contains)).toBeTruthy();
  });
});

// R-10C1-0003 MINOR-1: `not_retrieved` means the right source did not come back, not that no
// search ran.
describe("test_10c1_7_compare_view outcome wording", () => {
  it("says Getirilmedi in Turkish", () => {
    expect(tr.Evaluations.outcomes.not_retrieved).toBe("Getirilmedi");
  });
});
