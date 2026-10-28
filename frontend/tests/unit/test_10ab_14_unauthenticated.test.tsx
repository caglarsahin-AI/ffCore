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
    for (const unsafe of [null, "", "//evil.example", "https://evil.example", "/\\evil.example", "projects"]) {
      expect(safeNext(unsafe)).toBe("/");
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
