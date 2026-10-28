import type { components } from "@/lib/api/schema";

export type Me = components["schemas"]["MeResponse"];

export const SESSION_COOKIE = "ffcore_session";

export type SessionResult =
  | { status: "signedIn"; me: Me & { role: NonNullable<Me["role"]>; access: NonNullable<Me["access"]> } }
  | { status: "noMembership"; me: Me }
  | { status: "signedOut" }
  | { status: "unavailable"; reason: string };

type Fetcher = (url: string, init: { headers: Record<string, string>; cache: "no-store" }) => Promise<Response>;

function sessionCookie(cookieHeader: string): string | null {
  for (const part of cookieHeader.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === SESSION_COOKIE && rest.length) return `${SESSION_COOKIE}=${rest.join("=")}`;
  }
  return null;
}

function isMe(body: unknown): body is Me {
  const me = body as Me;
  return (
    typeof me?.user?.id === "string" &&
    typeof me.user.is_superadmin === "boolean" &&
    Array.isArray(me.memberships) &&
    "role" in me &&
    "access" in me
  );
}

// Signed-in user from GET /auth/me. Only 401 means "signed out"; any other failure is reported
// as "unavailable" so a backend outage is never shown as a sign-in page (ARCH-06).
export async function readSession(base: string, cookieHeader: string, fetcher: Fetcher): Promise<SessionResult> {
  const cookie = sessionCookie(cookieHeader);
  if (!cookie) return { status: "signedOut" };
  let response: Response;
  try {
    response = await fetcher(`${base}/api/v1/auth/me`, { headers: { cookie }, cache: "no-store" });
  } catch (error) {
    return { status: "unavailable", reason: error instanceof Error ? error.message : String(error) };
  }
  if (response.status === 401) return { status: "signedOut" };
  if (!response.ok) return { status: "unavailable", reason: `GET /auth/me returned ${response.status}` };
  const body: unknown = await response.json().catch(() => null);
  if (!isMe(body)) return { status: "unavailable", reason: "GET /auth/me returned an unexpected body" };
  if (body.role === null || body.access === null) return { status: "noMembership", me: body };
  return { status: "signedIn", me: { ...body, role: body.role, access: body.access } };
}
