// One behaviour for an ended session (401) everywhere: sign in again, then back to the page.

export function loginUrl(current: string): string {
  return `/login?next=${encodeURIComponent(current)}`;
}

// Any origin works as the reference: only "same origin as the reference" matters. safeNext also
// runs on the server (login page), where there is no window.location.
const REFERENCE = "http://console.invalid";
// C0 controls and DEL, raw or percent-encoded: URL parsers drop TAB/LF/CR, so "/\t/host" would
// become "//host" (review 10a-binding r2). Backslash: browsers read it as "/".
const FORBIDDEN = /[\u0000-\u001f\u007f\\]|%(?:[01][0-9a-f]|7f|5c)/i;

// Only a path on this origin; anything else falls back to the start page, so "next" can never
// send the user elsewhere. The result is rebuilt from the parsed URL, never the raw value.
export function safeNext(next: string | null | undefined): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || FORBIDDEN.test(next)) return "/";
  let url: URL;
  try {
    url = new URL(next, REFERENCE);
  } catch {
    return "/";
  }
  // Dot segments can normalise to "//host" ("/..//x"); reused as a path that is another origin.
  if (url.origin !== REFERENCE || url.pathname.startsWith("//")) return "/";
  return `${url.pathname}${url.search}${url.hash}`;
}

export function goToLogin(): void {
  window.location.assign(loginUrl(`${window.location.pathname}${window.location.search}`));
}

export function isUnauthenticated(error: unknown): boolean {
  // invalid_credentials is a wrong password on the sign-in form, not an ended session.
  const e = error as { status?: number; code?: string };
  return e?.status === 401 && e.code !== "invalid_credentials";
}
