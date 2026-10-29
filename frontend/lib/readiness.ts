import type { components } from "@/lib/api/schema-04a";
import { READINESS_STATES } from "@/lib/knowledge";

type ReadyzOut = components["schemas"]["ReadyzOut"];
type Fetcher = (url: string, init: RequestInit) => Promise<Response>;

export type Readiness = { kind: "ok"; body: ReadyzOut } | { kind: "error"; detail: string };

function isReadyz(body: unknown): body is ReadyzOut {
  const value = body as ReadyzOut;
  return (
    typeof value === "object" &&
    value !== null &&
    (READINESS_STATES as readonly string[]).includes(value.status) &&
    Array.isArray(value.checks)
  );
}

// Server side only (system status page, K-10bp-0002 D1): /readyz answers 200 or 503 with the same
// body, both are results. Anything else is an error the page shows, never "ready" by default.
export async function readReadiness(base: string, fetcher: Fetcher = fetch): Promise<Readiness> {
  let response: Response;
  try {
    response = await fetcher(`${base}/readyz`, { cache: "no-store" });
  } catch (error) {
    return { kind: "error", detail: `GET /readyz failed: ${error instanceof Error ? error.message : String(error)}` };
  }
  const body: unknown = await response.json().catch(() => undefined);
  if ((response.ok || response.status === 503) && isReadyz(body)) return { kind: "ok", body };
  return { kind: "error", detail: `GET /readyz returned ${response.status} without the readiness body` };
}
