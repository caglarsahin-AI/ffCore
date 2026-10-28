// One behaviour for an ended session (401) everywhere: sign in again, then back to the page.

export function loginUrl(current: string): string {
  return `/login?next=${encodeURIComponent(current)}`;
}

// Only a path on this origin; anything else (absolute URL, protocol-relative, backslash trick)
// falls back to the start page, so "next" can never send the user elsewhere.
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.includes("\\")) return "/";
  return next;
}

export function goToLogin(): void {
  window.location.assign(loginUrl(`${window.location.pathname}${window.location.search}`));
}

export function isUnauthenticated(error: unknown): boolean {
  // invalid_credentials is a wrong password on the sign-in form, not an ended session.
  const e = error as { status?: number; code?: string };
  return e?.status === 401 && e.code !== "invalid_credentials";
}
