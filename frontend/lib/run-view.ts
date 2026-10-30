import type { RunStreamEvent } from "@/lib/sse";

// What the test panel shows of a run, folded from its C9 SSE events (06a runtime/graph.py and
// runner.py payloads). Pure; every event leaves a trace in the view, none is dropped silently.
export type ToolCard = {
  id: string;
  name: string;
  arguments: unknown;
  result: { truncated: boolean; isError: boolean; errorCode: string | null; chars: number | null; ms: number | null } | null;
};
export type SourceCard = {
  n?: number;
  kb_key?: string;
  chunk_id?: string;
  document_name?: string;
  page?: number | null;
  breadcrumb?: string | null;
  rerank_score?: number | null;
};
export type PendingApproval = { action: string; arguments: unknown; assignTo: string | null; approvalId: string | null };
export type RunPhase = "starting" | "running" | "waiting_approval" | "waiting_user" | "done" | "failed";

export type RunView = {
  runId: string | null;
  phase: RunPhase;
  answer: string;
  tools: ToolCard[];
  sources: SourceCard[];
  approval: PendingApproval | null;
  question: string | null;
  status: string | null;
  outcomeLabel: string | null;
  error: { code: string; message: string | null } | null;
  fallback: Record<string, unknown> | null;
  notes: Record<string, unknown>[];
};

export function initialRunView(): RunView {
  return {
    runId: null,
    phase: "starting",
    answer: "",
    tools: [],
    sources: [],
    approval: null,
    question: null,
    status: null,
    outcomeLabel: null,
    error: null,
    fallback: null,
    notes: [],
  };
}

const str = (value: unknown): string | null => (typeof value === "string" ? value : null);
const num = (value: unknown): number | null => (typeof value === "number" ? value : null);

// A run that continues after a wait goes back to running; the wait's prompt is cleared.
function running(view: RunView): RunView {
  return view.phase === "waiting_approval" || view.phase === "waiting_user" || view.phase === "starting"
    ? { ...view, phase: "running", approval: null, question: null }
    : view;
}

export function reduceRunView(view: RunView, event: RunStreamEvent): RunView {
  const d = event.data;
  switch (event.event) {
    case "progress": {
      const runId = view.runId ?? str(d.run_id);
      const rest = Object.fromEntries(Object.entries(d).filter(([key]) => key !== "run_id"));
      const notes = Object.keys(rest).length > 0 ? [...view.notes, rest] : view.notes;
      return { ...running(view), runId, notes };
    }
    case "token":
      return { ...running(view), answer: view.answer + (str(d.text) ?? "") };
    case "tool_call":
      return {
        ...running(view),
        tools: [...view.tools, { id: str(d.tool_call_id) ?? `call-${view.tools.length}`, name: str(d.name) ?? "", arguments: d.arguments, result: null }],
      };
    case "tool_result": {
      const result = { truncated: d.truncated === true, isError: d.is_error === true, errorCode: str(d.error_code), chars: num(d.chars), ms: num(d.ms) };
      const id = str(d.tool_call_id);
      const known = view.tools.some((tool) => tool.id === id);
      const tools = known
        ? view.tools.map((tool) => (tool.id === id ? { ...tool, result } : tool))
        : [...view.tools, { id: id ?? `call-${view.tools.length}`, name: str(d.name) ?? "", arguments: null, result }];
      return { ...running(view), tools };
    }
    case "sources": {
      const incoming = Array.isArray(d.sources) ? (d.sources as SourceCard[]) : [];
      const seen = new Set(view.sources.map((s) => s.chunk_id ?? `${s.kb_key}:${s.n}`));
      const fresh = incoming.filter((s) => !seen.has(s.chunk_id ?? `${s.kb_key}:${s.n}`));
      return { ...running(view), sources: [...view.sources, ...fresh] };
    }
    case "approval_required":
      return {
        ...view,
        phase: "waiting_approval",
        approval: { action: str(d.action) ?? "", arguments: d.arguments, assignTo: str(d.assign_to), approvalId: str(d.approval_id) },
      };
    case "question":
      return { ...view, phase: "waiting_user", question: str(d.question) ?? "" };
    case "fallback":
      return { ...view, fallback: d };
    case "done":
      return { ...view, phase: "done", runId: view.runId ?? str(d.run_id), status: str(d.status), outcomeLabel: str(d.outcome_label), approval: null, question: null };
    case "error":
      return { ...view, phase: "failed", status: str(d.status), error: { code: str(d.code) ?? "unexpected", message: str(d.message) }, approval: null, question: null };
  }
}
