// @vitest-environment jsdom
import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SuiteForm, initialSuiteState, suiteBody } from "@/components/eval/suite-form";
import type { Suite } from "@/lib/api/eval-queries";

import { renderAs } from "./eval-support";

afterEach(cleanup);

const suite: Suite = {
  id: "s1",
  project_id: "p1",
  key: "sozlesme",
  name: "Contract set",
  agent_id: "a1",
  langfuse_dataset_name: "alpha.sozlesme",
  scorers: [{ name: "contains" }, { name: "llm_judge", pass_min: 4 }],
  pass_threshold: 0.85,
  repeat: 2,
  approve_tools: true,
  created_at: "",
  updated_at: "",
};

describe("test_10c1_5_suite_form: body", () => {
  it("builds a create body from the chosen scorers; blank optional values are left to the backend", () => {
    const state = initialSuiteState();
    state.key = "sozlesme";
    state.name = "Contract set";
    state.scorers.contains.on = true;
    state.scorers.llm_judge.on = true;
    state.scorers.llm_judge.pass_min = "4";
    const out = suiteBody(state, "create");
    expect(out).toEqual({
      ok: true,
      body: {
        key: "sozlesme",
        name: "Contract set",
        agent_id: null,
        scorers: [{ name: "contains" }, { name: "llm_judge", pass_min: 4 }],
        repeat: 1,
        approve_tools: false,
      },
    });
  });

  it("refuses a suite without scorers, a latency scorer without limits and out-of-range numbers", () => {
    const state = initialSuiteState();
    state.key = "k";
    state.name = "N";
    expect(suiteBody(state, "create")).toEqual({ ok: false, errors: { scorers: "scorersRequired" } });
    state.scorers.latency_cost.on = true;
    expect(suiteBody(state, "create")).toEqual({ ok: false, errors: { latency_cost: "latencyNeedsLimit" } });
    state.scorers.latency_cost.max_ms = "5000";
    state.passThreshold = "1.5";
    state.repeat = "11";
    expect(suiteBody(state, "create")).toEqual({ ok: false, errors: { passThreshold: "thresholdRange", repeat: "repeatRange" } });
  });

  it("reads a suite back and sends an update without key or dataset; an unbound agent is null", () => {
    const state = initialSuiteState(suite);
    expect(state.scorers.llm_judge).toMatchObject({ on: true, pass_min: "4" });
    state.agentId = "";
    const out = suiteBody(state, "update");
    expect(out).toEqual({
      ok: true,
      body: {
        name: "Contract set",
        agent_id: null,
        scorers: [{ name: "contains" }, { name: "llm_judge", pass_min: 4 }],
        pass_threshold: 0.85,
        repeat: 2,
        approve_tools: true,
      },
    });
  });
});

describe("test_10c1_5_suite_form: access", () => {
  const props = { projectId: "p1", projectKey: "alpha", agents: [{ id: "a1", name: "Contract Assistant" }], pending: false, onSubmit: vi.fn(), onCancel: vi.fn() };

  it("shows the approve_tools switch with its explanation and the default dataset name", () => {
    renderAs("analyst", "edit", <SuiteForm {...props} mode="create" />);
    expect(screen.getByLabelText(/wait for tool approvals/i)).toBeTruthy();
    expect(screen.getByTestId("suite-approve-tools-hint").textContent).toMatch(/never approves/i);
    expect(screen.getByTestId("suite-dataset-hint").textContent).toContain("alpha.");
    expect((screen.getByTestId("suite-save") as HTMLButtonElement).disabled).toBe(false);
  });

  it("is a read-only view in read mode: fields and Save disabled", () => {
    renderAs("analyst", "read", <SuiteForm {...props} mode="update" initial={suite} />);
    expect((screen.getByTestId("suite-save") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText(/^name$/i) as HTMLInputElement).disabled).toBe(true);
    expect(screen.getByTestId("suite-save").closest("[data-read-only]")).not.toBeNull();
  });
});
