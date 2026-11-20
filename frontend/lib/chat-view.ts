import type { ChatMessage } from "@/lib/api/chat-queries";
import { isLiveRun } from "@/lib/api/runs-queries";

// The end user chat's pure rules (11). The stored message list is the server's truth; a live turn
// only bridges the time until the run's messages are stored.

export type AnswerBadge = "declined" | "lowConfidence";

// `declined` (the model's own "not found") is always shown; low confidence only when the server
// computed it: the agent has show_confidence and a calibrated threshold (brief 11, K3).
export function answerBadge(message: Pick<ChatMessage, "role" | "outcome_label" | "low_confidence">): AnswerBadge | null {
  if (message.role !== "assistant") return null;
  if (message.outcome_label === "declined") return "declined";
  return message.low_confidence === true ? "lowConfidence" : null;
}

export const SEARCH_TOOL = "search_documents";
export type ToolActivity = { key: "searchDocuments" } | { key: "runSql" } | { key: "tool"; name: string };

// What a tool call is doing, in words for the end user ("Running SQL…"); unknown tools by name.
export function toolActivity(name: string): ToolActivity {
  if (name === SEARCH_TOOL) return { key: "searchDocuments" };
  if (name === "run_sql" || name.endsWith("__run_sql")) return { key: "runSql" };
  return { key: "tool", name };
}

// A run still going after a reload: the last message is a user message whose run is live.
export function pendingRun(messages: ChatMessage[]): string | null {
  const last = messages.at(-1);
  if (!last || last.role !== "user" || !last.run_id || !last.run_status) return null;
  return isLiveRun(last.run_status) ? last.run_id : null;
}

// The stored messages have caught up with a run: its answer is stored, or its user message shows
// a final status (a failed run stores no answer).
export function settledRun(messages: ChatMessage[], runId: string): boolean {
  if (messages.some((m) => m.role === "assistant" && m.run_id === runId)) return true;
  const asked = messages.find((m) => m.role === "user" && m.run_id === runId);
  return asked?.run_status != null && !isLiveRun(asked.run_status);
}

export function chatPath(agentKey?: string, conversationId?: string): string {
  if (!agentKey) return "/chat";
  const agent = `/chat/${encodeURIComponent(agentKey)}`;
  return conversationId ? `${agent}/${encodeURIComponent(conversationId)}` : agent;
}
