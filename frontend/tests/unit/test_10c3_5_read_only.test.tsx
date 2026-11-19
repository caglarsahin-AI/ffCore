// @vitest-environment jsdom
import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import McpServersPage from "@/app/(console)/mcp-servers/page";
import McpServerPage from "@/app/(console)/mcp-servers/[serverId]/page";

import { renderGov, stubApi } from "./gov-support";
import { S, calls, operation, server } from "./mcp-support";

// 10c-3 D4 (plan/10 salt-okunur mod, R10.5, KARARLAR "10c-3 plan kararları" S1): the same screens
// for everyone who may open them. An admin in read mode sees every change control disabled with
// the read-only reason (WriteGate); a developer sees them disabled with the "admin only" reason;
// the operations table is read-only for both. Nothing is hidden.

vi.mock("next/navigation", () => ({
  useParams: () => ({ serverId: "s1" }),
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/mcp-servers/s1",
}));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const CONTROLS = ["mcp-publish", "mcp-test", "mcp-add-tool", "mcp-edit", "mcp-delete", "mcp-spec-replace-open", "mcp-discover", "mcp-ops-save"];

function stub() {
  stubApi({
    [`GET ${S}`]: { data: [server()] },
    [`GET ${S}/s1`]: server({ operations: [operation(), operation({ name: "createChart" })] }),
    [`GET ${S}/s1/calls`]: calls(),
  });
}

describe("test_10c3_5_read_only", () => {
  it("disables every change of an admin in read mode, with the read-only reason", async () => {
    stub();
    renderGov("admin", "read", <McpServerPage />);
    await screen.findByTestId("mcp-operations");
    for (const id of CONTROLS) {
      const control = screen.getByTestId(id) as HTMLButtonElement;
      expect(control.disabled, id).toBe(true);
      expect(control.closest("[data-read-only]"), id).not.toBeNull();
    }
    for (const box of within(screen.getByTestId("mcp-operations")).getAllByRole("checkbox")) expect((box as HTMLInputElement).disabled).toBe(true);
    for (const box of within(screen.getByTestId("mcp-operations")).getAllByRole("textbox")) expect((box as HTMLInputElement).disabled).toBe(true);
  });

  it("shows a developer the same page with every change disabled as admin-only", async () => {
    stub();
    renderGov("developer", "edit", <McpServerPage />);
    await screen.findByTestId("mcp-operations");
    for (const id of CONTROLS) {
      const control = screen.getByTestId(id) as HTMLButtonElement;
      expect(control.disabled, id).toBe(true);
      expect(control.closest("[data-needs-role='admin']"), id).not.toBeNull();
    }
    for (const box of within(screen.getByTestId("mcp-operations")).getAllByRole("checkbox")) expect((box as HTMLInputElement).disabled).toBe(true);
  });

  it("lets an admin in edit mode change the server", async () => {
    stub();
    renderGov("admin", "edit", <McpServerPage />);
    await screen.findByTestId("mcp-operations");
    for (const id of CONTROLS) expect((screen.getByTestId(id) as HTMLButtonElement).disabled, id).toBe(false);
  });

  it("disables publishing a server on the list for a developer and for read mode", async () => {
    stub();
    renderGov("developer", "edit", <McpServersPage />);
    await screen.findByTestId("mcp-server-table");
    expect((screen.getByTestId("primary-action") as HTMLButtonElement).disabled).toBe(true);
    cleanup();
    stub();
    renderGov("admin", "read", <McpServersPage />);
    await screen.findByTestId("mcp-server-table");
    expect((screen.getByTestId("primary-action") as HTMLButtonElement).disabled).toBe(true);
  });
});
