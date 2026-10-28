import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: { "@": fileURLToPath(new URL(".", import.meta.url)) } },
  // tsconfig keeps jsx "preserve" for Next.js; tests need the automatic runtime.
  oxc: { jsx: { runtime: "automatic" } },
  test: {
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    environment: "node",
    // The colour and literal-text rules run real ESLint; its first load takes ~5 s in a container.
    testTimeout: 30_000,
  },
});
