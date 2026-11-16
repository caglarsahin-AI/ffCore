import { describe, expect, it } from "vitest";

import { GATE_REASONS, parseGateFailure } from "@/lib/eval-gate";
import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

// 409 eval_gate_failed message (backend/ffcore/api/agents.py publish):
// "The exam gate refuses version N: <key>=<reason>, <key>=<reason>." (FOLLOWUP-176: read the message,
// no additive field asked for).
describe("test_10c1_4_eval_gate", () => {
  it("reads every suite and its reason from the message", () => {
    expect(parseGateFailure("The exam gate refuses version 3: sozlesme-33=not_passed, sql-set=stale_exam.")).toEqual([
      { key: "sozlesme-33", reason: "not_passed", known: true },
      { key: "sql-set", reason: "stale_exam", known: true },
    ]);
  });

  it("keeps a reason it does not know as written, marked unknown", () => {
    expect(parseGateFailure("The exam gate refuses version 1: a=brand_new.")).toEqual([{ key: "a", reason: "brand_new", known: false }]);
  });

  it("returns null when the message is not in that shape (the raw message is shown then)", () => {
    expect(parseGateFailure("Something else happened.")).toBeNull();
    expect(parseGateFailure("The exam gate refuses version 1: .")).toBeNull();
  });

  it("knows the six gate reasons of docs/evaluation.md and explains each in both languages", () => {
    expect([...GATE_REASONS].sort()).toEqual(["incomplete", "no_exam", "not_passed", "stale_exam", "stale_suite", "suite_not_gateable"]);
    for (const reason of GATE_REASONS) {
      expect(en.Evaluations.gate.reasons).toHaveProperty(reason);
      expect(tr.Evaluations.gate.reasons).toHaveProperty(reason);
    }
  });
});
