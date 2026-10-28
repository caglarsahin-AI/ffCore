import { expect } from "@playwright/test";
import type { BrowserContext, Page } from "@playwright/test";

import { PASSWORD, fixture } from "./fixtures";

export const THEMES = ["light", "dark"] as const;
export type Theme = (typeof THEMES)[number];

// Main 10a screens. Paths that need run data (project id) are resolved inside the test, because
// test files are listed before global-setup.ts has created the fixture.
export const SCREENS = [
  { name: "login", signedIn: false, path: () => "/login" },
  { name: "projects", signedIn: true, path: () => "/projects" },
  { name: "members", signedIn: true, path: () => `/projects/${fixture().alpha.id}/members` },
  { name: "providers", signedIn: true, path: () => "/providers" },
  { name: "models", signedIn: true, path: () => "/models" },
  { name: "coming-soon", signedIn: true, path: () => "/agents" },
  { name: "theme-preview", signedIn: false, path: () => "/dev/theme" },
] as const;

// Superadmin with project alpha selected: every 10a screen shows real data.
export async function openScreen(page: Page, context: BrowserContext, baseURL: string, screen: (typeof SCREENS)[number]) {
  if (screen.signedIn) {
    await signIn(page, fixture().superadmin.email);
    await selectProject(context, baseURL, fixture().alpha.id);
  }
  await page.goto(screen.path());
  await page.waitForLoadState("networkidle");
}

// Sign in through the real form (POST /auth/login via the console origin, C6).
export async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").or(page.getByLabel("E-posta")).fill(email);
  await page.locator("#password").fill(PASSWORD);
  await page.locator('form[data-testid="login-form"] button[type="submit"]').click();
  await expect(page).not.toHaveURL(/\/login$/);
}

export async function selectProject(context: BrowserContext, baseURL: string, projectId: string) {
  await context.addCookies([{ name: "ffcore_project", value: projectId, url: baseURL }]);
}

export async function setLocale(context: BrowserContext, baseURL: string, locale: "en" | "tr") {
  await context.addCookies([{ name: "NEXT_LOCALE", value: locale, url: baseURL }]);
}

// next-themes reads its choice from localStorage["theme"].
export async function useTheme(page: Page, theme: Theme | "system") {
  await page.addInitScript((value) => window.localStorage.setItem("theme", value), theme);
}
