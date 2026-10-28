import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it, vi } from "vitest";

import { backendUrl } from "@/lib/backend";

const ROOT = fileURLToPath(new URL("../..", import.meta.url));

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(name) && !name.endsWith(".d.ts") ? [path] : [];
  });
}

afterEach(() => vi.unstubAllEnvs());

describe("test_10ab_11_same_origin", () => {
  it("fails loudly without FFCORE_BACKEND_URL instead of guessing an address", () => {
    vi.stubEnv("FFCORE_BACKEND_URL", "");
    expect(() => backendUrl()).toThrow(/FFCORE_BACKEND_URL/);
  });

  it("rejects a value that is not an http(s) origin", () => {
    vi.stubEnv("FFCORE_BACKEND_URL", "backend:8000");
    expect(() => backendUrl()).toThrow(/FFCORE_BACKEND_URL/);
  });

  it("rewrites /api/v1 to the backend, so the browser only sees the console origin", async () => {
    vi.stubEnv("FFCORE_BACKEND_URL", "http://backend:8000/");
    const config = (await import("@/next.config")).default;
    const rewrites = await config.rewrites!();
    expect(rewrites).toEqual([
      { source: "/api/v1/:path*", destination: "http://backend:8000/api/v1/:path*" },
    ]);
  });

  it("keeps absolute backend addresses out of browser code", () => {
    const offenders = ["app", "components", "lib"]
      .flatMap((dir) => sources(join(ROOT, dir)))
      .filter((path) => /https?:\/\/(?!www\.w3\.org)/.test(readFileSync(path, "utf8")));
    expect(offenders).toEqual([]);
  });
});
