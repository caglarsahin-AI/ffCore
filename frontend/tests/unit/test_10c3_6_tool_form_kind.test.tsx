// @vitest-environment jsdom
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToolForm } from "@/components/tool-form";

import { P, renderGov, stubApi } from "./gov-support";

// 10c-3 D1 (05b S5, KARARLAR "05b plan kararları"): an OpenAPI document becomes a tool only as a
// published MCP server, so the tool form no longer offers the OpenAPI kind (the backend answers
// 422 openapi_tool_via_mcp_server); a registered tool is an MCP server.

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label, { exact: true }), { target: { value } });
}

describe("test_10c3_6_tool_form_kind", () => {
  it("offers no kind choice and registers an MCP server", async () => {
    const calls = stubApi({ [`POST ${P}/tools`]: { id: "t1" }, [`GET ${P}/tools`]: { data: [] } });
    const done = vi.fn();
    renderGov("admin", "edit", <ToolForm projectId="p1" onDone={done} />);
    expect(document.getElementById("tool-kind")).toBeNull();
    expect(screen.queryByRole("option", { name: "OpenAPI" })).toBeNull();
    fill("Key", "search");
    fill("Name", "Search");
    fill("Address", "http://mcp-search:8000/mcp");
    fireEvent.submit(screen.getByTestId("tool-form"));
    await waitFor(() => expect(done).toHaveBeenCalled());
    expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({ kind: "mcp", key: "search" });
  });
});
