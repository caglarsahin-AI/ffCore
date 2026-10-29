import { describe, expect, it } from "vitest";

import { DOCUMENTS_POLL_MS, READINESS_REFRESH_MS, documentsRefetchInterval, readinessNeedsRefresh } from "@/lib/knowledge";

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
