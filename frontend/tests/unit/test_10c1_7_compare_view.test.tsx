// @vitest-environment jsdom
import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CompareView } from "@/components/eval/compare-view";
import type { Compare } from "@/lib/api/eval-queries";

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
});
