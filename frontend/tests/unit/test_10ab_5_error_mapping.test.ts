import { describe, expect, it, vi } from "vitest";

import { api, ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";
import en from "@/messages/en.json";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

const errorBody = (code: string, type = "permission_error") => ({ error: { message: `m-${code}`, type, code } });

describe("test_10ab_5_error_mapping", () => {
  it("maps every 403 code of the 03a contract to its own message", () => {
    expect(errorMessageKey("read_only_access")).toBe("readOnlyAccess");
    expect(errorMessageKey("insufficient_role")).toBe("insufficientRole");
    expect(errorMessageKey("cross_origin_forbidden")).toBe("crossOriginForbidden");
    expect(errorMessageKey("obo_project_scope")).toBe("oboProjectScope");
    expect(en.Errors.readOnlyAccess).toBe("Read-only access: your access mode does not allow changes here.");
  });

  it("does not hide an unknown code behind a known message", () => {
    expect(errorMessageKey("something_new")).toBe("unexpected");
  });

  it("turns an OpenAI-shaped 4xx body into ApiError with status and code", async () => {
    const fetcher = vi.fn(async () => json(403, errorBody("read_only_access")));
    const error = await api("POST", "/api/v1/projects", { key: "x", name: "X" }, fetcher).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 403, code: "read_only_access", message: "m-read_only_access" });
    expect(fetcher).toHaveBeenCalledWith("/api/v1/projects", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ key: "x", name: "X" }),
      credentials: "same-origin",
    });
  });

  it("reports a non-contract error body as unexpected_response instead of swallowing it", async () => {
    const fetcher = vi.fn(async () => new Response("<html>bad gateway</html>", { status: 502 }));
    const error = await api("GET", "/api/v1/projects", undefined, fetcher).catch((e) => e);
    expect(error).toMatchObject({ status: 502, code: "unexpected_response" });
  });

  it("returns undefined for 204 and the parsed body otherwise", async () => {
    expect(await api("DELETE", "/api/v1/x", undefined, async () => new Response(null, { status: 204 }))).toBeUndefined();
    expect(await api("GET", "/api/v1/x", undefined, async () => json(200, { data: [] }))).toEqual({ data: [] });
  });
});
