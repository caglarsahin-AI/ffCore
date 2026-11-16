import { describe, expect, it } from "vitest";

import { hasRole } from "@/lib/access";
import { errorMessageKey } from "@/lib/api/errors";
import { EVAL_RUN_STATUSES, SCORER_NAMES, isLiveEvalRun } from "@/lib/api/eval-queries";
import { NAV_GROUPS, canOpen } from "@/lib/navigation";
import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

// Codes the 09 backend answers with (api/eval.py, evaluation/from_run.py, api/agents.py publish
// gate). Each has its own message in both languages; an unknown one falls back to "unexpected".
const CODES = {
  suite_key_taken: "suiteKeyTaken",
  dataset_name_not_in_project: "datasetNameNotInProject",
  eval_threshold_not_configured: "evalThresholdNotConfigured",
  judge_model_not_configured: "judgeModelNotConfigured",
  version_not_of_suite_agent: "versionNotOfSuiteAgent",
  eval_plan_exceeds_tick: "evalPlanExceedsTick",
  eval_too_many_runs: "evalTooManyRuns",
  item_input_invalid: "itemInputInvalid",
  dataset_empty: "datasetEmpty",
  eval_run_finished: "evalRunFinished",
  eval_runs_not_comparable: "evalRunsNotComparable",
  run_input_blocked: "runInputBlocked",
  expected_would_be_masked: "expectedWouldBeMasked",
  ner_unavailable: "nerUnavailable",
  text_too_long: "textTooLong",
  langfuse_unreachable: "langfuseUnreachable",
  langfuse_not_configured: "langfuseNotConfigured",
  langfuse_request_failed: "langfuseRequestFailed",
  eval_gate_failed: "evalGateFailed",
  force_requires_admin: "forceRequiresAdmin",
  force_reason_required: "forceReasonRequired",
  force_reason_without_force: "forceReasonWithoutForce",
} as const;

describe("test_10c1_1_eval_contract", () => {
  it("maps every evaluation and publish-gate code to its own message in both languages", () => {
    for (const [code, key] of Object.entries(CODES)) {
      expect(errorMessageKey(code), code).toBe(key);
      expect(en.Errors, key).toHaveProperty(key);
      expect(tr.Errors, key).toHaveProperty(key);
    }
  });

  it("labels each exam status and scorer in both languages; only queued and running are live", () => {
    expect([...EVAL_RUN_STATUSES].sort()).toEqual(["cancelled", "completed", "failed", "queued", "running"]);
    for (const status of EVAL_RUN_STATUSES) {
      expect(en.Evaluations.statuses).toHaveProperty(status);
      expect(tr.Evaluations.statuses).toHaveProperty(status);
    }
    expect(EVAL_RUN_STATUSES.filter(isLiveEvalRun)).toEqual(["queued", "running"]);
    expect(SCORER_NAMES).toHaveLength(8);
    for (const scorer of SCORER_NAMES) {
      expect(en.Evaluations.scorers, scorer).toHaveProperty(scorer);
      expect(tr.Evaluations.scorers, scorer).toHaveProperty(scorer);
    }
  });

  it("has the same Evaluations message keys in both languages", () => {
    const keys = (value: unknown, prefix = ""): string[] =>
      value && typeof value === "object"
        ? Object.entries(value).flatMap(([k, v]) => keys(v, `${prefix}${k}.`))
        : [prefix.slice(0, -1)];
    expect(keys(tr.Evaluations).sort()).toEqual(keys(en.Evaluations).sort());
  });

  it("opens the Evaluations screen to analyst and above, never to user (R10.5, backend Reader=analyst)", () => {
    const item = NAV_GROUPS.flatMap((g) => g.items).find((i) => i.key === "evaluations")!;
    expect(item).toMatchObject({ href: "/evaluations", minRole: "analyst", ready: true });
    expect(canOpen(item, "user", false)).toBe(false);
    for (const role of ["analyst", "developer", "admin"] as const) expect(canOpen(item, role, false) && hasRole(role, "analyst")).toBe(true);
  });
});
