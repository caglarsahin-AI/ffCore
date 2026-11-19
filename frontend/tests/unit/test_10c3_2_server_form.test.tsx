// @vitest-environment jsdom
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import McpServersPage from "@/app/(console)/mcp-servers/page";
import { McpServerForm } from "@/components/mcp/server-form";

import { refusal, renderGov, stubApi } from "./gov-support";
import { S, server } from "./mcp-support";

// 10c-3 D2: an admin publishes an OpenAPI document as an MCP server (key, name, source, upstream
// address and identity, access, guardrail mode and policy, the document pasted or uploaded); a
// remote MCP server takes no document. Field-level 05b refusals land on their field; the
// document's path refusal (openapi_path_invalid) is shown with its message, never swallowed.

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/mcp-servers" }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label, { exact: true }), { target: { value } });
}

const SPEC = "openapi: 3.0.3\ninfo: {title: t, version: '1'}\npaths: {}\n";

describe("test_10c3_2_server_form", () => {
  it("lists the project's servers with source, status and published count", async () => {
    stubApi({ [`GET ${S}`]: { data: [server({ exposed_operations: ["listCharts"], status: "active" })] } });
    renderGov("developer", "edit", <McpServersPage />);
    const row = await screen.findByTestId("mcp-server-superset");
    expect(within(row).getByText("Superset")).toBeTruthy();
    expect(within(row).getByText("OpenAPI document")).toBeTruthy();
    expect(within(row).getByText("Active")).toBeTruthy();
    expect(within(row).getByText("/mcp/superset/")).toBeTruthy();
    expect(within(row).getByTestId("mcp-server-exposed").textContent).toBe("1 / 1");
  });

  it("creates an OpenAPI server with its document and the chosen settings", async () => {
    const calls = stubApi({ [`POST ${S}`]: server(), [`GET ${S}`]: { data: [] } });
    const done = vi.fn();
    renderGov("admin", "edit", <McpServerForm projectId="p1" onDone={done} />);
    fill("Key", "superset");
    fill("Name", "Superset");
    fill("Upstream address", "http://superset.example.com/api");
    fireEvent.change(screen.getByLabelText("Identity type"), { target: { value: "bearer" } });
    fill("Token", "s3cret");
    fireEvent.change(screen.getByLabelText("Who can call"), { target: { value: "token" } });
    fireEvent.change(screen.getByLabelText("Guardrail mode"), { target: { value: "enforce" } });
    fill("OpenAPI document", SPEC);
    fireEvent.submit(screen.getByTestId("mcp-server-form"));
    await waitFor(() => expect(done).toHaveBeenCalled());
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({
      key: "superset",
      name: "Superset",
      source_kind: "openapi",
      upstream_base_url: "http://superset.example.com/api",
      upstream_auth: { type: "bearer", token: "s3cret" },
      access: "token",
      guardrail_mode: "enforce",
      guardrail_policy_key: "default",
      spec: SPEC,
    });
  });

  it("reads an uploaded document into the form", async () => {
    stubApi({});
    renderGov("admin", "edit", <McpServerForm projectId="p1" onDone={vi.fn()} />);
    const file = new File([SPEC], "superset.yaml", { type: "application/yaml" });
    fireEvent.change(screen.getByLabelText("Upload a file"), { target: { files: [file] } });
    await waitFor(() => expect((screen.getByLabelText("OpenAPI document") as HTMLTextAreaElement).value).toBe(SPEC));
  });

  it("sends no document for a remote MCP server", async () => {
    const calls = stubApi({ [`POST ${S}`]: server({ source_kind: "remote_mcp" }), [`GET ${S}`]: { data: [] } });
    const done = vi.fn();
    renderGov("admin", "edit", <McpServerForm projectId="p1" onDone={done} />);
    fireEvent.change(screen.getByLabelText("Source"), { target: { value: "remote_mcp" } });
    expect(screen.queryByLabelText("OpenAPI document")).toBeNull();
    fill("Key", "desk");
    fill("Name", "Desk");
    fill("Upstream address", "http://ticket-desk:8000/mcp");
    fireEvent.submit(screen.getByTestId("mcp-server-form"));
    await waitFor(() => expect(done).toHaveBeenCalled());
    const body = calls.find((c) => c.method === "POST")?.body as Record<string, unknown>;
    expect(body.source_kind).toBe("remote_mcp");
    expect("spec" in body).toBe(false);
  });

  it("does not send an OpenAPI server without its document or an invalid key", async () => {
    const calls = stubApi({});
    renderGov("admin", "edit", <McpServerForm projectId="p1" onDone={vi.fn()} />);
    fill("Key", "Bad Key");
    fill("Name", "X");
    fill("Upstream address", "http://x.example.com");
    fireEvent.submit(screen.getByTestId("mcp-server-form"));
    expect(await screen.findByText("Use lowercase letters, digits and hyphens, starting with a letter (2 to 64 characters).")).toBeTruthy();
    expect(screen.getByText("An OpenAPI server needs its document. Paste or upload it.")).toBeTruthy();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
  });

  it("puts 05b refusals on their field: key taken, address refused, unsafe document path", async () => {
    let answer = refusal(409, "mcp_server_key_taken");
    stubApi({ [`POST ${S}`]: () => answer });
    renderGov("admin", "edit", <McpServerForm projectId="p1" onDone={vi.fn()} />);
    fill("Key", "superset");
    fill("Name", "Superset");
    fill("Upstream address", "http://superset.example.com/api");
    fill("OpenAPI document", SPEC);
    fireEvent.submit(screen.getByTestId("mcp-server-form"));
    expect(await screen.findByText(/This server key is already used in the installation/)).toBeTruthy();

    answer = refusal(422, "upstream_url_refused");
    fireEvent.submit(screen.getByTestId("mcp-server-form"));
    expect(await screen.findByText("This address belongs to a platform service and cannot be an upstream.")).toBeTruthy();

    answer = refusal(422, "openapi_path_invalid");
    fireEvent.submit(screen.getByTestId("mcp-server-form"));
    const error = await screen.findByTestId("mcp-spec-error");
    expect(error.textContent).toMatch(/A path in the document is not safe to call/);
  });

  it("keeps stored credentials on edit unless the identity is changed", async () => {
    const calls = stubApi({ [`PATCH ${S}/s1`]: server({ name: "Superset BI" }), [`GET ${S}`]: { data: [] } });
    const done = vi.fn();
    renderGov("admin", "edit", <McpServerForm projectId="p1" server={server() as never} onDone={done} />);
    expect((screen.getByLabelText("Key") as HTMLInputElement).disabled).toBe(true);
    expect(screen.queryByLabelText("OpenAPI document")).toBeNull();
    expect(screen.getByTestId("mcp-secret-kept")).toBeTruthy();
    fill("Name", "Superset BI");
    fireEvent.submit(screen.getByTestId("mcp-server-form"));
    await waitFor(() => expect(done).toHaveBeenCalled());
    expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({
      name: "Superset BI",
      upstream_base_url: "http://superset.example.com/api",
      access: "internal",
      guardrail_mode: "monitor",
      guardrail_policy_key: "default",
    });
  });
});
