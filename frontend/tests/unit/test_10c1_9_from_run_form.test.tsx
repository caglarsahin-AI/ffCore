// @vitest-environment jsdom
import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FromRunResult, fromRunBody, initialFromRunState } from "@/components/eval/from-run-form";

import { renderAs } from "./eval-support";

afterEach(cleanup);

describe("test_10c1_9_from_run_form", () => {
  it("sends only the expected fields that were filled, one list entry per line", () => {
    const state = initialFromRunState();
    state.answer = "  Thirty days.  ";
    state.mustContain = "30 days\n\n notice \n";
    state.style = "dolayli";
    expect(fromRunBody(state)).toEqual({
      ok: true,
      body: { expected: { answer: "Thirty days.", must_contain: ["30 days", "notice"] }, style: "dolayli", answerable: true },
    });
  });

  it("refuses a SQL result that is not a JSON list of rows and a body with no expectation for an answerable item", () => {
    const state = initialFromRunState();
    state.sqlResult = "{not json";
    expect(fromRunBody(state)).toEqual({ ok: false, errors: { sqlResult: "sqlResultInvalid" } });
    state.sqlResult = "";
    expect(fromRunBody(state)).toEqual({ ok: false, errors: { expected: "expectedRequired" } });
    state.answerable = false;
    expect(fromRunBody(state)).toEqual({ ok: true, body: { expected: {}, style: "dogrudan", answerable: false } });
    state.sqlResult = '[["a", 1]]';
    expect(fromRunBody(state)).toMatchObject({ ok: true, body: { expected: { sql_result: [["a", 1]] } } });
  });

  it("shows what was masked after saving", () => {
    renderAs("analyst", "edit", <FromRunResult result={{ item_id: "it-1", dataset: "alpha.sozlesme", run_id: "r1", masking: "regex", masked_fields: ["message", "answer"] }} />);
    expect(screen.getByTestId("from-run-masking").textContent).toMatch(/person names are stored as written/i);
    expect(screen.getByTestId("from-run-masked-fields").textContent).toContain("message");
    expect(screen.getByTestId("from-run-masked-fields").textContent).toContain("answer");
  });
});
