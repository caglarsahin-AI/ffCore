import { describe, expect, it } from "vitest";

import {
  DOCUMENTS_POLL_MS,
  READINESS_REFRESH_MS,
  documentsFinished,
  documentsRefetchInterval,
  readinessNeedsRefresh,
} from "@/lib/knowledge";
import type { DocumentStatus } from "@/lib/knowledge";

describe("test_10bp1_16_polling", () => {
  it("polls the document list only while a document is still being processed", () => {
    expect(documentsRefetchInterval(undefined)).toBe(false);
    expect(documentsRefetchInterval([])).toBe(false);
    expect(documentsRefetchInterval([{ status: "indexed" }, { status: "failed" }])).toBe(false);
    expect(documentsRefetchInterval([{ status: "indexed" }, { status: "embedding" }])).toBe(DOCUMENTS_POLL_MS);
    expect(documentsRefetchInterval([{ status: "pending" }])).toBe(DOCUMENTS_POLL_MS);
  });

  it("refreshes the readiness page only while it is warming", () => {
    expect(readinessNeedsRefresh("warming")).toBe(true);
    expect(readinessNeedsRefresh("ready")).toBe(false);
    expect(readinessNeedsRefresh("not_ready")).toBe(false);
    expect(READINESS_REFRESH_MS).toBeGreaterThanOrEqual(2000);
  });
});

describe("test_10bp1_16_polling: finished documents", () => {
  it("reports a document that was in flight and is now final, and nothing else", () => {
    const doc = (id: string, status: DocumentStatus) => ({ id, status });
    expect(documentsFinished(undefined, [doc("a", "indexed")])).toBe(false);
    expect(documentsFinished([doc("a", "embedding")], [doc("a", "embedding")])).toBe(false);
    expect(documentsFinished([doc("a", "embedding")], [doc("a", "indexed")])).toBe(true);
    expect(documentsFinished([doc("a", "pending")], [doc("a", "failed")])).toBe(true);
    expect(documentsFinished([doc("a", "indexed")], [doc("a", "indexed"), doc("b", "pending")])).toBe(false);
    // A new document that is already final (e.g. Kapı 0 skip) changes the counts too.
    expect(documentsFinished([doc("a", "indexed")], [doc("a", "indexed"), doc("b", "skipped")])).toBe(true);
  });
});
