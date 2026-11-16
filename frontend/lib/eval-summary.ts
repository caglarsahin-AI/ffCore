import { z } from "zod";

// Reader for EvalRunOut.summary. 09.yaml leaves it untyped (additionalProperties), so this narrow
// schema follows backend/ffcore/evaluation/engine.py summarize(); a summary that does not hold is
// reported with the failing field (K-10C1-0002 S3: fail-loud, never an empty summary).
// FOLLOWUP-185 asks for an `EvalSummary` schema in the contract; then this file goes.

// Item diagnosis (09 brief "Aşama bazlı teşhis"; engine.py OUTCOMES).
export const OUTCOMES = [
  "not_retrieved",
  "below_rerank_floor",
  "not_reranked",
  "declined",
  "below_threshold",
  "answered",
  "unanswerable_held",
  "unanswerable_answered",
] as const;

// Why an item (or a repeat, as `partial:<code>`) was not run: runner.py, scorers.CHECK_NOT_MADE,
// engine.ITEM_NOT_RUN, docs/evaluation.md. An unknown code is shown as written.
export const NOT_RUN_CODES = [
  "approval_required",
  "approval_rejected",
  "approval_expired",
  "waiting_user",
  "ner_unavailable",
  "sql_reread_failed",
  "tool_removed",
] as const;
export type NotRunCode = (typeof NOT_RUN_CODES)[number];

const count = z.number().int().nonnegative();
const counts = z.record(z.string(), count);
const worstItem = z.object({
  item_id: z.string(),
  style: z.string(),
  outcome: z.string().nullable(),
  passed: z.boolean().nullable(),
  mean: z.number().nullable(),
  note: z.string().nullable(),
});

const schema = z.looseObject({
  n: count,
  scored: count,
  not_run: counts,
  passed_items: count,
  pass_rate: z.number(),
  pass_threshold: z.number(),
  passed: z.boolean(),
  complete: z.boolean(),
  scores: z.record(z.string(), z.number()),
  outcomes: counts,
  styles: z.record(z.string(), z.looseObject({ n: count, passed: count, outcomes: counts })),
  worst: z.array(worstItem),
  errors: counts,
  warm_cache: z.boolean(),
  warmup_ms: z.number().nullable(),
  latency_ms: z.object({ p50: z.number(), max: z.number() }).nullable(),
});

export type EvalSummary = z.infer<typeof schema>;
export type WorstItem = z.infer<typeof worstItem>;
export type SummaryRead = { ok: true; summary: EvalSummary } | { ok: false; reason: string };

export function readSummary(raw: unknown): SummaryRead {
  const parsed = schema.safeParse(raw);
  if (parsed.success) return { ok: true, summary: parsed.data };
  const reason = parsed.error.issues
    .map((issue) => `${issue.path.map(String).join(".") || "summary"}: ${issue.message}`)
    .join("; ");
  return { ok: false, reason };
}

const KNOWN_NOT_RUN: ReadonlySet<string> = new Set(NOT_RUN_CODES);

// `key` is the message key for a known code (also inside `partial:`), null for an unknown one.
export function describeNotRun(code: string): { code: string; key: NotRunCode | null; partial: boolean } {
  const partial = code.startsWith("partial:");
  const inner = partial ? code.slice("partial:".length) : code;
  return { code, key: KNOWN_NOT_RUN.has(inner) ? (inner as NotRunCode) : null, partial };
}

export type ErrorKind = "judgeOutOfTime" | "judgeFailed" | "advanceFailed";

// summary.errors codes: `judge_out_of_time`, `judge_failed:<cause>`, `advance_failed:<cause>`, or a
// scorer's own error comment (shown raw).
export function describeError(code: string): { code: string; kind: ErrorKind | null; detail: string | null } {
  if (code === "judge_out_of_time") return { code, kind: "judgeOutOfTime", detail: null };
  for (const [prefix, kind] of [
    ["judge_failed:", "judgeFailed"],
    ["advance_failed:", "advanceFailed"],
  ] as const) {
    if (code.startsWith(prefix)) return { code, kind, detail: code.slice(prefix.length) };
  }
  return { code, kind: null, detail: null };
}
