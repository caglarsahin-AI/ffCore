// Publish gate refusal (409 eval_gate_failed). The backend names each failing suite in the message
// as `<key>=<reason>` (backend/ffcore/api/agents.py publish; docs/evaluation.md "The publish gate").
// FOLLOWUP-176: the console reads the message; no extra field is asked for. A message in another
// shape gives null and the raw message is shown, never a guessed reason.

export const GATE_REASONS = ["no_exam", "stale_exam", "stale_suite", "not_passed", "incomplete", "suite_not_gateable"] as const;
export type GateReason = (typeof GATE_REASONS)[number];
export type GateFailure = { key: string; reason: string; known: boolean };

const KNOWN: ReadonlySet<string> = new Set(GATE_REASONS);
const LIST = /^The exam gate refuses version \d+: (.+)\.$/;
const PAIR = /^([a-z0-9][a-z0-9-]{0,62})=([a-z_]+)$/;

export function parseGateFailure(message: string): GateFailure[] | null {
  const list = LIST.exec(message.trim())?.[1];
  if (!list) return null;
  const failures: GateFailure[] = [];
  for (const part of list.split(", ")) {
    const pair = PAIR.exec(part.trim());
    if (!pair) return null;
    failures.push({ key: pair[1], reason: pair[2], known: KNOWN.has(pair[2]) });
  }
  return failures;
}
