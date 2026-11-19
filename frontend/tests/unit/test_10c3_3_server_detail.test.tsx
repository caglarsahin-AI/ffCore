// @vitest-environment jsdom
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import McpServerPage from "@/app/(console)/mcp-servers/[serverId]/page";

import { refusal, renderGov, stubApi } from "./gov-support";
import { S, calls, operation, server } from "./mcp-support";

// 10c-3 D2: the server page. Operations of the document are listed with their method and path;
// one that cannot be published shows its reason and cannot be selected (exposable=false never
// hidden, ARCH-06). The admin selects operations, renames them for the model, saves, publishes,
// tests the upstream and adds the server to the tools. Replacing the document and discovering
// again keep the server page; a refused document shows the 05b message.

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

const OPS = [
  operation(),
  operation({ name: "createChart", method: "POST", path: "/api/v1/chart/", description: "Create a chart" }),
  operation({ name: "badPath", method: "GET", path: "/api/../admin", exposable: false, reason: "openapi_path_invalid" }),
  operation({ name: "odd", method: "GET", path: "/x", exposable: false, reason: "future_reason" }),
];

function stubServer(over: Record<string, unknown> = {}, extra: Record<string, unknown> = {}) {
  return stubApi({
    [`GET ${S}/s1`]: server({ operations: OPS, ...over }),
    [`GET ${S}/s1/calls`]: calls(),
    ...extra,
  });
}

describe("test_10c3_3_server_detail", () => {
  it("lists every operation, the unpublishable ones with their reason and no selection", async () => {
    stubServer();
    renderGov("admin", "edit", <McpServerPage />);
    const table = await screen.findByTestId("mcp-operations");
    expect(within(table).getAllByRole("row")).toHaveLength(OPS.length + 1);
    const bad = screen.getByTestId("mcp-op-badPath");
    expect(within(bad).getByTestId("mcp-op-reason").textContent).toMatch(/Its path is not safe to call/);
    expect((within(bad).getByRole("checkbox") as HTMLInputElement).disabled).toBe(true);
    // An unknown reason is shown as its code, not dropped.
    expect(within(screen.getByTestId("mcp-op-odd")).getByTestId("mcp-op-reason").textContent).toContain("future_reason");
    expect(screen.getByTestId("mcp-server-summary").textContent).toContain("/mcp/superset/");
  });

  it("saves the selection and the tool names, then publishes", async () => {
    const api = stubServer(
      {},
      {
        [`PATCH ${S}/s1`]: (c: { body: Record<string, unknown> }) =>
          server({ operations: OPS, exposed_operations: (c.body.exposed_operations as string[]) ?? ["createChart"], status: (c.body.status as string) ?? "draft" }),
      },
    );
    renderGov("admin", "edit", <McpServerPage />);
    await screen.findByTestId("mcp-operations");
    fireEvent.click(screen.getByLabelText("Publish createChart"));
    fireEvent.change(screen.getByLabelText("Tool name for createChart"), { target: { value: "create_chart" } });
    fireEvent.change(screen.getByLabelText("Tool description for createChart"), { target: { value: "Make a chart" } });
    fireEvent.click(screen.getByTestId("mcp-ops-save"));
    await waitFor(() => expect(api.filter((c) => c.method === "PATCH")).toHaveLength(1));
    expect(api.find((c) => c.method === "PATCH")?.body).toEqual({
      exposed_operations: ["createChart"],
      aliases: { createChart: { name: "create_chart", description: "Make a chart" } },
    });
    fireEvent.click(await screen.findByTestId("mcp-publish"));
    await waitFor(() => expect(api.filter((c) => c.method === "PATCH")).toHaveLength(2));
    expect(api.filter((c) => c.method === "PATCH")[1].body).toEqual({ status: "active" });
    await waitFor(() => expect(screen.getByTestId("mcp-server-status").textContent).toBe("Active"));
    expect(screen.getByTestId("mcp-disable")).toBeTruthy();
  });

  it("shows an alias conflict with its message and keeps the edits", async () => {
    stubServer({}, { [`PATCH ${S}/s1`]: refusal(422, "alias_conflict") });
    renderGov("admin", "edit", <McpServerPage />);
    await screen.findByTestId("mcp-operations");
    fireEvent.change(screen.getByLabelText("Tool name for createChart"), { target: { value: "listCharts" } });
    fireEvent.click(screen.getByTestId("mcp-ops-save"));
    expect(await screen.findByText(/Two operations would be shown to the model under the same tool name/)).toBeTruthy();
    expect((screen.getByLabelText("Tool name for createChart") as HTMLInputElement).value).toBe("listCharts");
  });

  it("tests the upstream and shows the answer", async () => {
    stubServer({}, { [`POST ${S}/s1/test`]: { reachable: true, status_code: 404, error_code: null, latency_ms: 12, tools: null } });
    renderGov("admin", "edit", <McpServerPage />);
    fireEvent.click(await screen.findByTestId("mcp-test"));
    const result = await screen.findByTestId("mcp-test-result");
    expect(result.textContent).toContain("Reachable");
    expect(result.textContent).toContain("HTTP 404");
    expect(result.textContent).toContain("12 ms");
  });

  it("shows an unreachable upstream with its code's message", async () => {
    stubServer({}, { [`POST ${S}/s1/test`]: { reachable: false, status_code: null, error_code: "egress_not_allowlisted", latency_ms: 1, tools: null } });
    renderGov("admin", "edit", <McpServerPage />);
    fireEvent.click(await screen.findByTestId("mcp-test"));
    const result = await screen.findByTestId("mcp-test-result");
    expect(result.textContent).toContain("Not reachable");
    expect(result.textContent).toContain("This address is not on the installation's outbound allow list.");
  });

  it("adds the server to the tools and links the new tool", async () => {
    stubServer({ status: "active", exposed_operations: ["listCharts"] }, { [`POST ${S}/s1/tools`]: { id: "t9", key: "superset", name: "Superset" } });
    renderGov("admin", "edit", <McpServerPage />);
    fireEvent.click(await screen.findByTestId("mcp-add-tool"));
    const link = await screen.findByTestId("mcp-added-tool");
    expect(link.getAttribute("href")).toBe("/tools/t9");
  });

  it("replaces the document and shows a refused one with its message", async () => {
    let answer: unknown = refusal(422, "openapi_path_invalid");
    const api = stubServer({}, { [`PUT ${S}/s1/spec`]: () => answer });
    renderGov("admin", "edit", <McpServerPage />);
    fireEvent.click(await screen.findByTestId("mcp-spec-replace-open"));
    fireEvent.change(screen.getByLabelText("OpenAPI document"), { target: { value: "openapi: 3.0.3" } });
    fireEvent.submit(screen.getByTestId("mcp-spec-replace"));
    expect((await screen.findByTestId("mcp-spec-error")).textContent).toMatch(/A path in the document is not safe to call/);
    answer = server({ operations: [operation()] });
    fireEvent.submit(screen.getByTestId("mcp-spec-replace"));
    await waitFor(() => expect(screen.queryByTestId("mcp-spec-replace")).toBeNull());
    expect(api.filter((c) => c.method === "PUT").at(-1)?.body).toEqual({ spec: "openapi: 3.0.3" });
    expect(within(screen.getByTestId("mcp-operations")).getAllByRole("row")).toHaveLength(2);
  });

  it("discovers a remote MCP server's tools; it takes no document", async () => {
    const api = stubServer({ source_kind: "remote_mcp", operations: [] }, { [`POST ${S}/s1/discover`]: server({ source_kind: "remote_mcp", operations: [operation({ name: "list_tickets", method: null, path: null })] }) });
    renderGov("admin", "edit", <McpServerPage />);
    await screen.findByTestId("mcp-server-summary");
    expect(screen.queryByTestId("mcp-spec-replace-open")).toBeNull();
    fireEvent.click(screen.getByTestId("mcp-discover"));
    expect(await screen.findByTestId("mcp-op-list_tickets")).toBeTruthy();
    expect(api.some((c) => c.method === "POST" && c.path.endsWith("/discover"))).toBe(true);
  });
});
