import { cookies } from "next/headers";

import { parseSession } from "@/lib/access";
import type { Session } from "@/lib/access";

export const FAKE_SESSION_COOKIE = "ffcore_fake_session";

// Signed-in user's role and access mode.
// FAKE_API=1 (development and Playwright only): read from a fixture cookie "<role>:<access>",
// admin:edit when absent; a malformed cookie yields no session instead of a guessed role.
// Without FAKE_API there is no backend yet (GET /auth/me arrives in 10a-binding), so the
// console reports the session as unavailable rather than inventing one.
export async function getSession(): Promise<Session | null> {
  if (process.env.FAKE_API !== "1") return null;
  const value = (await cookies()).get(FAKE_SESSION_COOKIE)?.value ?? "admin:edit";
  return parseSession(value);
}
