// @vitest-environment jsdom
import { useQuery } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QueryProvider } from "@/components/query-provider";
import { ApiError } from "@/lib/api/client";
import { goToLogin, loginUrl, safeNext } from "@/lib/login-redirect";

vi.mock("@/lib/login-redirect", async (original) => ({
  ...(await original<typeof import("@/lib/login-redirect")>()),
  goToLogin: vi.fn(),
}));

afterEach(cleanup);

// Review r1 MINOR-1: 401 behaves the same everywhere: back to sign-in, then back to the page.
describe("test_10ab_14_unauthenticated", () => {
  it("builds the sign-in address with the current page as next", () => {
    expect(loginUrl("/providers?tab=1")).toBe("/login?next=%2Fproviders%3Ftab%3D1");
  });

  it("follows only a same-origin relative next", () => {
    expect(safeNext("/projects/p1/members")).toBe("/projects/p1/members");
    expect(safeNext("/providers?tab=1#top")).toBe("/providers?tab=1#top");
  });

  // Review r2 MAJOR-1: the URL parser drops TAB/LF/CR, so "/\t/host" became "//host" (another origin).
  it.each([
    null,
    "",
    "//evil.example",
    "https://evil.example",
    "http:evil.example",
    "javascript:alert(1)",
    "/\\evil.example",
    "\\/evil.example",
    "projects",
    " /projects",
    "/\t/backend:8000/healthz",
    "/\n/backend:8000/healthz",
    "/\r/backend:8000/healthz",
    "/\u0000/evil.example",
    "/\u007f/evil.example",
    "/%09/backend:8000/healthz",
    "/%0A/backend:8000/healthz",
    "/%0d/backend:8000/healthz",
    "/..//evil.example",
    "/%5C/evil.example",
  ])("sends %j to the start page", (unsafe) => {
    expect(safeNext(unsafe)).toBe("/");
  });

  it("never returns a value that resolves to another origin", () => {
    const base = "http://localhost:3000";
    for (const value of ["/a", "/\t/x", "//x", "/%2F/x", "/..//x", "/./%5C/x"]) {
      expect(new URL(safeNext(value), base).origin).toBe(base);
    }
  });

  it("sends a 401 from any list query to sign-in", async () => {
    function Probe() {
      useQuery({
        queryKey: ["probe"],
        queryFn: async () => {
          throw new ApiError(401, "unauthenticated", "authentication_error", "Session ended.");
        },
      });
      return null;
    }
    render(
      <QueryProvider>
        <Probe />
      </QueryProvider>,
    );
    await vi.waitFor(() => expect(goToLogin).toHaveBeenCalledTimes(1));
  });
});
