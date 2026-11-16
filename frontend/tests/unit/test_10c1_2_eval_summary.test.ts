import { describe, expect, it } from "vitest";

import { NOT_RUN_CODES, OUTCOMES, describeError, describeNotRun, readSummary } from "@/lib/eval-summary";
import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

// The shape backend/ffcore/evaluation/engine.py summarize() writes (EvalRunOut.summary is untyped
// in 09.yaml; K-10C1-0002 S3: a narrow reader, fail-loud when the shape does not hold).
const SUMMARY = {
  n: 4,
  scored: 2,
  not_run: { approval_required: 1, "partial:approval_rejected": 1 },
  passed_items: 1,
  pass_rate: 0.5,
  pass_threshold: 0.85,
  passed: false,
  complete: false,
  scores: { contains: 0.75, cites_source: 0.5 },
  outcomes: Object.fromEntries(OUTCOMES.map((o) => [o, o === "answered" ? 2 : 0])),
  styles: { dogrudan: { n: 3, passed: 1, outcomes: { answered: 2 } }, dolayli: { n: 1, passed: 0, outcomes: {} } },
  worst: [{ item_id: "i-2", style: "dogrudan", outcome: "answered", passed: false, mean: 0.25, note: "" }],
  errors: { judge_out_of_time: 1, "advance_failed:ner_misconfigured": 1 },
  warm_cache: true,
  warmup_ms: 1200,
  latency_ms: { p50: 800, max: 2100 },
};

describe("test_10c1_2_eval_summary: reader", () => {
  it("reads the engine summary as written, keeping not_run, errors and complete=false", () => {
    const read = readSummary(SUMMARY);
    expect(read.ok).toBe(true);
    if (!read.ok) return;
    expect(read.summary.complete).toBe(false);
    expect(read.summary.not_run).toEqual(SUMMARY.not_run);
    expect(read.summary.errors).toEqual(SUMMARY.errors);
    expect(read.summary.worst).toHaveLength(1);
    expect(read.summary.latency_ms).toEqual({ p50: 800, max: 2100 });
  });

  it("accepts a summary without latency (no item finished) as null, never zero", () => {
    const read = readSummary({ ...SUMMARY, latency_ms: null, warmup_ms: null });
    expect(read.ok && read.summary.latency_ms).toBeNull();
    expect(read.ok && read.summary.warmup_ms).toBeNull();
  });

  it("fails loudly with the path of the field that does not hold, instead of an empty summary", () => {
    const missing = readSummary({ ...SUMMARY, complete: undefined });
    expect(missing).toEqual({ ok: false, reason: expect.stringContaining("complete") });
    const wrong = readSummary({ ...SUMMARY, not_run: { approval_required: "one" } });
    expect(wrong).toEqual({ ok: false, reason: expect.stringContaining("not_run") });
    expect(readSummary("text").ok).toBe(false);
  });

  it("keeps a field it does not know (additive backend field) without failing", () => {
    expect(readSummary({ ...SUMMARY, formula_comparison: {} }).ok).toBe(true);
  });
});

describe("test_10c1_2_eval_summary: reasons", () => {
  it("describes known not_run codes, partial repeats and leaves unknown codes raw", () => {
    expect(describeNotRun("approval_required")).toEqual({ code: "approval_required", key: "approval_required", partial: false });
    expect(describeNotRun("partial:approval_rejected")).toEqual({ code: "partial:approval_rejected", key: "approval_rejected", partial: true });
    expect(describeNotRun("brand_new_reason")).toEqual({ code: "brand_new_reason", key: null, partial: false });
    for (const code of NOT_RUN_CODES) {
      expect(en.Evaluations.notRun, code).toHaveProperty(code);
      expect(tr.Evaluations.notRun, code).toHaveProperty(code);
    }
  });

  it("groups errors by their kind and keeps the code", () => {
    expect(describeError("judge_out_of_time")).toEqual({ code: "judge_out_of_time", kind: "judgeOutOfTime", detail: null });
    expect(describeError("judge_failed:timeout")).toEqual({ code: "judge_failed:timeout", kind: "judgeFailed", detail: "timeout" });
    expect(describeError("advance_failed:ner_misconfigured")).toEqual({ code: "advance_failed:ner_misconfigured", kind: "advanceFailed", detail: "ner_misconfigured" });
    expect(describeError("whatever")).toEqual({ code: "whatever", kind: null, detail: null });
    for (const kind of ["judgeOutOfTime", "judgeFailed", "advanceFailed"]) {
      expect(en.Evaluations.errorKinds).toHaveProperty(kind);
      expect(tr.Evaluations.errorKinds).toHaveProperty(kind);
    }
  });

  it("labels each of the 8 outcomes in both languages", () => {
    expect(OUTCOMES).toHaveLength(8);
    for (const o of OUTCOMES) {
      expect(en.Evaluations.outcomes).toHaveProperty(o);
      expect(tr.Evaluations.outcomes).toHaveProperty(o);
    }
  });
});
