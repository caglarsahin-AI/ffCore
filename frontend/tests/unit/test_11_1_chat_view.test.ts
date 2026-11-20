import { describe, expect, it } from "vitest";

import type { ChatMessage } from "@/lib/api/chat-queries";
import { answerBadge, chatPath, pendingRun, settledRun, toolActivity } from "@/lib/chat-view";
import { homePath } from "@/lib/navigation";

// 11-1: the chat's pure rules (K-11-0002). A message list is the server's truth; the live turn
// only bridges the time until the run's messages are stored.

function message(over: Partial<ChatMessage>): ChatMessage {
  return {
    id: "m1",
    role: "user",
    content: "Fesih süresi?",
    run_id: "r1",
    run_status: "completed",
    outcome_label: null,
    error_code: null,
    sources: null,
    feedback: null,
    low_confidence: null,
    created_at: "2026-11-20T10:00:00Z",
    ...over,
  };
}

describe("test_11_1_chat_view", () => {
  it("shows 'not found in the sources' for a declined answer, always", () => {
    expect(answerBadge(message({ role: "assistant", outcome_label: "declined" }))).toBe("declined");
    expect(answerBadge(message({ role: "assistant", outcome_label: "declined", low_confidence: true }))).toBe("declined");
  });

  it("shows low confidence only when the server computed it (badge off by default)", () => {
    expect(answerBadge(message({ role: "assistant", low_confidence: true }))).toBe("lowConfidence");
    expect(answerBadge(message({ role: "assistant", low_confidence: false }))).toBeNull();
    expect(answerBadge(message({ role: "assistant", low_confidence: null }))).toBeNull();
    expect(answerBadge(message({ role: "user", outcome_label: "declined" }))).toBeNull();
  });

  it("names the tool activity: documents, SQL, or the tool itself", () => {
    expect(toolActivity("search_documents")).toEqual({ key: "searchDocuments" });
    expect(toolActivity("crm__run_sql")).toEqual({ key: "runSql" });
    expect(toolActivity("run_sql")).toEqual({ key: "runSql" });
    expect(toolActivity("ticket_create")).toEqual({ key: "tool", name: "ticket_create" });
  });

  it("finds a run still going after a reload: the last user message without an answer", () => {
    expect(pendingRun([message({ run_status: "running" })])).toBe("r1");
    expect(pendingRun([message({ run_status: "waiting_approval" })])).toBe("r1");
    expect(pendingRun([message({ run_status: "completed" }), message({ id: "m2", role: "assistant" })])).toBeNull();
    expect(pendingRun([message({ run_status: "failed" })])).toBeNull();
    expect(pendingRun([])).toBeNull();
  });

  it("knows when the stored messages have caught up with the live run", () => {
    const stored = [message({}), message({ id: "m2", role: "assistant" })];
    expect(settledRun(stored, "r1")).toBe(true);
    expect(settledRun([message({ run_status: "running" })], "r1")).toBe(false);
    // A failed run stores no answer; its user message with a final status settles it.
    expect(settledRun([message({ run_status: "failed", error_code: "guardrail_block" })], "r1")).toBe(true);
    expect(settledRun(stored, "other")).toBe(false);
  });

  it("builds chat paths with encoded keys", () => {
    expect(chatPath()).toBe("/chat");
    expect(chatPath("hr assistant")).toBe("/chat/hr%20assistant");
    expect(chatPath("asistan", "c1")).toBe("/chat/asistan/c1");
  });

  it("sends a `user` member to the chat; other roles to their first console screen", () => {
    expect(homePath("user", false)).toBe("/chat");
    expect(homePath("analyst", false)).toBe("/overview");
    expect(homePath("admin", true)).toBe("/overview");
  });
});
