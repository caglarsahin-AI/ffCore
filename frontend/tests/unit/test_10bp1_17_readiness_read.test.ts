import { describe, expect, it } from "vitest";

import { readReadiness } from "@/lib/readiness";

const body = {
  status: "not_ready",
  checks: [{ name: "warmup", status: "failed", code: "model_missing", detail: "BAAI/bge-m3 is not in /models" }],
};

function fetcher(status: number, payload: unknown) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fn = async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(typeof payload === "string" ? payload : JSON.stringify(payload), { status });
  };
  return { fn, calls };
}

describe("test_10bp1_17_readiness_read", () => {
  it("reads /readyz from the backend's internal address without caching", async () => {
    const { fn, calls } = fetcher(200, { status: "ready", checks: [] });
    await expect(readReadiness("http://backend:8000", fn)).resolves.toEqual({
      kind: "ok",
      body: { status: "ready", checks: [] },
    });
    expect(calls[0].url).toBe("http://backend:8000/readyz");
    expect(calls[0].init.cache).toBe("no-store");
  });

  it("keeps a 503 with the contract body as a readiness result, not an error", async () => {
    const { fn } = fetcher(503, body);
    await expect(readReadiness("http://backend:8000", fn)).resolves.toEqual({ kind: "ok", body });
  });

  it("fails loudly on a body outside the contract and on a network error", async () => {
    const html = fetcher(502, "<html>bad gateway</html>");
    await expect(readReadiness("http://backend:8000", html.fn)).resolves.toEqual({
      kind: "error",
      detail: "GET /readyz returned 502 without the readiness body",
    });
    const wrongState = fetcher(200, { status: "fine", checks: [] });
    await expect(readReadiness("http://backend:8000", wrongState.fn)).resolves.toMatchObject({ kind: "error" });
    const down = async () => {
      throw new TypeError("fetch failed");
    };
    await expect(readReadiness("http://backend:8000", down)).resolves.toEqual({
      kind: "error",
      detail: "GET /readyz failed: fetch failed",
    });
  });
});
