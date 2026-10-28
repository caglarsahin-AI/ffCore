// Backend origin for the server side only: the Next.js rewrite (C6, same origin for the browser)
// and server components reading the session. Required; there is no default address (ARCH-10).
export function backendUrl(): string {
  const value = (process.env.FFCORE_BACKEND_URL ?? "").trim().replace(/\/+$/, "");
  if (!/^https?:\/\/[^/\s]+$/.test(value)) {
    throw new Error(
      `FFCORE_BACKEND_URL must be the backend origin (scheme://host:port), got "${value}". ` +
        "Compose sets it for the frontend and e2e services.",
    );
  }
  return value;
}
