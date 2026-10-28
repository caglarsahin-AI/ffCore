import { headers } from "next/headers";

import { backendUrl } from "@/lib/backend";
import { readSession } from "@/lib/session-core";
import type { SessionResult } from "@/lib/session-core";

// The console's one session boundary: GET /auth/me on the backend with the browser's cookie.
export async function getSession(): Promise<SessionResult> {
  return readSession(backendUrl(), (await headers()).get("cookie") ?? "", fetch);
}
