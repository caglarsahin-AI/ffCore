import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";

import { SessionProvider } from "@/components/session-provider";
import type { AccessMode, Role } from "@/lib/access";
import type { EvalRun } from "@/lib/api/eval-queries";
import messages from "@/messages/en.json";

// Shared render for the 10c-1 component tests: one project "p1" (key "alpha") with the given role
// and access mode.
export function renderAs(role: Role, access: AccessMode, children: React.ReactNode, client = new QueryClient()) {
  const me = {
    user: { id: "u1", email: "a@example.org", full_name: "A", is_superadmin: false },
    role,
    access,
    memberships: [{ project_id: "p1", project_key: "alpha", role, access }],
  };
  return render(
    <QueryClientProvider client={client}>
      <NextIntlClientProvider locale="en" messages={messages} timeZone="UTC">
        <SessionProvider value={{ me, projectId: "p1" }}>{children}</SessionProvider>
      </NextIntlClientProvider>
    </QueryClientProvider>,
  );
}

export function evalRun(over: Partial<EvalRun> = {}): EvalRun {
  return {
    id: "e1",
    project_id: "p1",
    suite_id: "s1",
    agent_version_id: "v1",
    langfuse_run_name: "exam-e1",
    status: "completed",
    error_code: null,
    items: 4,
    scored: 2,
    summary: null,
    cost_usd: null,
    started_at: "2026-11-16T08:00:00Z",
    ended_at: "2026-11-16T08:01:00Z",
    created_at: "2026-11-16T08:00:00Z",
    ...over,
  };
}
