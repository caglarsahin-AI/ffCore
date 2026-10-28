import { describe, expect, it, vi } from "vitest";

import type { Me } from "@/lib/session-core";
import { readSession } from "@/lib/session-core";

const ME: Me = {
  user: { id: "u1", email: "a@example.org", full_name: "A", is_superadmin: false },
  role: "admin",
  access: "edit",
  memberships: [{ project_id: "p1", project_key: "demo", role: "admin", access: "edit" }],
};

const respond = (status: number, body: unknown) =>
  vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));

describe("test_10ab_7_session", () => {
  it("forwards only the session cookie to GET /auth/me", async () => {
    const fetcher = respond(200, ME);
    const result = await readSession("http://backend:8000", "ffcore_session=t; other=x", fetcher);
    expect(result).toEqual({ status: "signedIn", me: ME });
    expect(fetcher).toHaveBeenCalledWith("http://backend:8000/api/v1/auth/me", {
      headers: { cookie: "ffcore_session=t" },
      cache: "no-store",
    });
  });

  it("is signed out without a cookie, without calling the backend", async () => {
    const fetcher = respond(200, ME);
    expect(await readSession("http://backend:8000", "other=x", fetcher)).toEqual({ status: "signedOut" });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("is signed out on 401 (expired or revoked token)", async () => {
    const result = await readSession("http://backend:8000", "ffcore_session=t", respond(401, {}));
    expect(result).toEqual({ status: "signedOut" });
  });

  it("reports the backend as unavailable instead of pretending to be signed out", async () => {
    const down = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    for (const fetcher of [respond(500, {}), respond(200, { user: {} }), down]) {
      const result = await readSession("http://backend:8000", "ffcore_session=t", fetcher);
      expect(result.status).toBe("unavailable");
    }
  });

  it("separates a user without memberships from a signed-in member", async () => {
    const lonely = { ...ME, role: null, access: null, memberships: [] };
    const result = await readSession("http://backend:8000", "ffcore_session=t", respond(200, lonely));
    expect(result).toEqual({ status: "noMembership", me: lonely });
  });
});
