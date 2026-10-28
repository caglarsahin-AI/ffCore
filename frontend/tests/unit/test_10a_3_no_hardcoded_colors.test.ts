import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const eslint = new ESLint({ cwd: process.cwd() });

async function messagesFor(code: string, filePath = "components/sample.tsx") {
  const [result] = await eslint.lintText(code, { filePath });
  return result.messages.map((m) => m.ruleId);
}

describe("test_10a_3_no_hardcoded_colors", () => {
  it.each([
    'export const A = () => <div className="bg-white p-2" />;',
    'export const A = () => <div className="text-gray-900" />;',
    'export const A = () => <div style={{ color: "#fff" }} />;',
    'export const A = () => <div style={{ color: "rgb(0, 0, 0)" }} />;',
    "export const A = () => <div className={`border-slate-200 ${'x'}`} />;",
  ])("rejects %s", async (code) => {
    expect(await messagesFor(code)).toContain("no-restricted-syntax");
  });

  it("accepts token classes", async () => {
    const code = 'export const A = () => <div className="bg-background text-muted-foreground border-border" />;';
    expect(await messagesFor(code)).not.toContain("no-restricted-syntax");
  });

  it("finds no violation in the source tree", async () => {
    const results = await eslint.lintFiles(["app", "components", "lib", "hooks", "i18n"]);
    const hits = results.flatMap((r) =>
      r.messages.filter((m) => m.ruleId === "no-restricted-syntax").map((m) => `${r.filePath}:${m.line}`),
    );
    expect(hits).toEqual([]);
  });
});
