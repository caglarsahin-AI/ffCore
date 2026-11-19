import { readFileSync } from "node:fs";

import { apiCall, uniqueKey } from "./api";
import { fixture } from "./fixtures";

// 10c-3 e2e helpers. The Superset sample (13a) has 6 operations; the e2e service runs in
// frontend/, the repository is mounted at /work.
export const SAMPLE_SPEC_PATH = "../data/samples/openapi/superset.yaml";
export const SAMPLE_OPERATIONS = 6;

// An upstream that is only stored, never called: creating a server checks the address against the
// egress policy without resolving it. The stack allows it with EGRESS_ALLOWLIST on its command
// line (docs/onyuz.md "MCP servers (10c-3)").
export const PARKED_UPSTREAM = "http://superset.example.com/api";

export function sampleSpec(): string {
  return readFileSync(SAMPLE_SPEC_PATH, "utf-8");
}

// A document whose one path leaves the base path: 05b refuses it whole (422 openapi_path_invalid).
export const UNSAFE_SPEC = `openapi: "3.0.3"
info: {title: unsafe, version: "1"}
paths:
  /api/../admin:
    get:
      operationId: escape
      responses: {"200": {description: ok}}
`;

// Server keys are unique in the installation and at most 64 characters.
export function serverKey(name: string): string {
  return uniqueKey(name).slice(0, 60).replace(/-+$/, "");
}

// Setup through the API (what the test is not about): the sample published as a draft server.
export async function createSampleServer(name: string, upstream = PARKED_UPSTREAM) {
  return apiCall<{ id: string; key: string; operations: { name: string }[] }>("POST", `/projects/${fixture().alpha.id}/mcp-servers`, {
    key: serverKey(name),
    name: `E2E ${name}`,
    source_kind: "openapi",
    upstream_base_url: upstream,
    upstream_auth: { type: "none" },
    spec: sampleSpec(),
  });
}

// --- fake upstream (KARARLAR "10c-3 plan kararları" S2, C-10C3-0003 A) ---
// 05b refuses every platform service as an upstream (RESERVED_HOSTS), so the e2e run container
// serves a fake Superset itself. The container runs with a fixed name (`run --name`), the stack
// lists that name in ALLOWED_INTERNAL_HOSTS for the run only and the spec passes it in
// E2E_UPSTREAM_HOST (docs/onyuz.md "MCP servers (10c-3)"). Nothing of this exists in an installation.
// GET / answers 200 (connection test), GET /api/v1/chart/ answers a chart list (an ok call), any
// other path 404 (an error call, upstream_http_404).
export type FakeUpstream = { url: string; hits: string[]; close: () => Promise<void> };

export async function startFakeUpstream(): Promise<FakeUpstream> {
  const host = process.env.E2E_UPSTREAM_HOST;
  if (!host) throw new Error("E2E_UPSTREAM_HOST is not set: run the e2e container with --name and -e E2E_UPSTREAM_HOST (docs/onyuz.md)");
  const { createServer } = await import("node:http");
  const hits: string[] = [];
  const server = createServer((req, res) => {
    const path = (req.url ?? "/").split("?")[0];
    hits.push(`${req.method} ${path}`);
    const send = (status: number, body: unknown) => {
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify(body));
    };
    if (req.method === "GET" && path === "/") return send(200, { service: "fake-superset" });
    if (req.method === "GET" && path === "/api/v1/chart/") return send(200, { count: 1, result: [{ id: 1, slice_name: "Beds by ward" }] });
    return send(404, { message: "Not found" });
  });
  await new Promise<void>((resolve) => server.listen(0, "0.0.0.0", resolve));
  const address = server.address();
  if (address === null || typeof address === "string") throw new Error("fake upstream has no port");
  return {
    url: `http://${host}:${address.port}`,
    hits,
    close: () => new Promise<void>((resolve) => server.close(() => resolve())),
  };
}
