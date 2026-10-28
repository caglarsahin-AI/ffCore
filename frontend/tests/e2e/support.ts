import type { BrowserContext, Page } from "@playwright/test";

export const THEMES = ["light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

// Main 10a screens; members uses a placeholder project id (no data in the fake API stage).
export const SCREENS = [
  { name: "login", path: "/login" },
  { name: "projects", path: "/projects" },
  { name: "members", path: "/projects/demo/members" },
  { name: "providers", path: "/providers" },
  { name: "models", path: "/models" },
  { name: "coming-soon", path: "/agents" },
  { name: "theme-preview", path: "/dev/theme" },
] as const;

export async function signIn(context: BrowserContext, baseURL: string, session = "admin:edit") {
  await context.addCookies([{ name: "ffcore_fake_session", value: session, url: baseURL }]);
}

export async function setLocale(context: BrowserContext, baseURL: string, locale: "en" | "tr") {
  await context.addCookies([{ name: "NEXT_LOCALE", value: locale, url: baseURL }]);
}

// next-themes reads its choice from localStorage["theme"].
export async function useTheme(page: Page, theme: Theme | "system") {
  await page.addInitScript((value) => window.localStorage.setItem("theme", value), theme);
}
