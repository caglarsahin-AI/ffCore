// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MemberForm } from "@/components/member-form";
import { ProjectSwitcher } from "@/components/project-switcher";
import { QueryProvider } from "@/components/query-provider";
import { SessionProvider } from "@/components/session-provider";
import type { SignedInMe } from "@/lib/project";
import messages from "@/messages/en.json";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/projects",
}));

// Review r1 MAJOR-1: a failed helper query must not look like an empty option list (ARCH-06).
const superadmin: SignedInMe = {
  user: { id: "u1", email: "a@example.org", full_name: "A", is_superadmin: true },
  role: "admin",
  access: "edit",
  memberships: [],
};
const member: SignedInMe = {
  ...superadmin,
  user: { ...superadmin.user, is_superadmin: false },
  memberships: [{ project_id: "p1", project_key: "alpha", role: "admin", access: "edit" }],
};

function renderWith(ui: React.ReactNode, me: SignedInMe = superadmin) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <SessionProvider value={{ me, projectId: "p1" }}>
        <QueryProvider>{ui}</QueryProvider>
      </SessionProvider>
    </NextIntlClientProvider>,
  );
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const unavailable = () => json(503, { error: { message: "users store down", type: "api_error", code: "users_unavailable" } });

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("test_10ab_13_query_states: member form user list", () => {
  it("shows the error code instead of offering an empty user list", async () => {
    fetchMock.mockImplementation(async () => unavailable());
    renderWith(<MemberForm projectId="p1" existing={[]} />);
    const error = await screen.findByTestId("query-error");
    expect(error.textContent).toContain("users_unavailable");
    expect(document.getElementById("member-user")).toBeNull();
  });

  it("keeps the picker disabled while loading", () => {
    fetchMock.mockImplementation(() => new Promise(() => {}));
    renderWith(<MemberForm projectId="p1" existing={[]} />);
    const picker = document.getElementById("member-user") as HTMLSelectElement;
    expect(picker.disabled).toBe(true);
    expect(picker.textContent).toContain(messages.State.loading);
  });

  it("says so when there is really nobody left to add", async () => {
    fetchMock.mockImplementation(async () => json(200, { data: [] }));
    renderWith(<MemberForm projectId="p1" existing={[]} />);
    expect((await screen.findByTestId("member-no-candidates")).textContent).toBe(messages.Members.noCandidates);
  });
});

describe("test_10ab_13_query_states: project switcher", () => {
  it("shows the error code instead of an empty project list (superadmin)", async () => {
    fetchMock.mockImplementation(async () => unavailable());
    renderWith(<ProjectSwitcher />);
    expect((await screen.findByTestId("query-error")).textContent).toContain("users_unavailable");
    expect(screen.queryByTestId("project-switcher")).toBeNull();
  });

  it("uses the memberships of a member without asking the API", async () => {
    renderWith(<ProjectSwitcher />, member);
    await waitFor(() => expect(screen.getByTestId("project-switcher")).toBeTruthy());
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
