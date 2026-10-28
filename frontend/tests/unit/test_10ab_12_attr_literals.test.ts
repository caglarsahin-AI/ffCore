import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const eslint = new ESLint({ cwd: process.cwd() });

async function ruleIds(code: string, filePath = "components/sample.tsx") {
  const [result] = await eslint.lintText(code, { filePath });
  return result.messages.map((m) => m.ruleId);
}

// FOLLOWUP-44: react/jsx-no-literals (ignoreProps) misses text in accessibility attributes.
describe("test_10ab_12_attr_literals", () => {
  it.each(["aria-label", "title", "placeholder", "alt"])("rejects a literal %s", async (attr) => {
    expect(await ruleIds(`export const A = () => <button ${attr}="Toggle Sidebar" />;`)).toContain(
      "no-restricted-syntax",
    );
  });

  it("accepts translated attributes and keeps the colour rule in the same files", async () => {
    expect(await ruleIds('export const A = ({ t }: { t: (k: string) => string }) => <button aria-label={t("x")} />;')).toEqual([]);
    expect(await ruleIds('export const A = () => <div className="bg-white" />;')).toContain("no-restricted-syntax");
  });

  it("finds no literal attribute text in the source tree (SidebarRail included)", async () => {
    const results = await eslint.lintFiles(["app", "components"]);
    const hits = results.flatMap((r) =>
      r.messages.filter((m) => m.ruleId === "no-restricted-syntax").map((m) => `${r.filePath}:${m.line}`),
    );
    expect(hits).toEqual([]);
  });
});
