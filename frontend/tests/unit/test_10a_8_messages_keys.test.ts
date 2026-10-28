import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

type Tree = { [key: string]: string | Tree };

function keys(tree: Tree, prefix = ""): string[] {
  return Object.entries(tree).flatMap(([k, v]) =>
    typeof v === "string" ? [`${prefix}${k}`] : keys(v, `${prefix}${k}.`),
  );
}

describe("test_10a_8_messages_keys", () => {
  it("has the same keys in en (source) and tr (translation)", () => {
    expect(keys(tr as Tree).sort()).toEqual(keys(en as Tree).sort());
  });

  it("keeps the 00 keys (C13 additive)", () => {
    for (const k of ["Home.title", "Home.subtitle", "Theme.label", "Theme.system", "Theme.light", "Theme.dark"]) {
      expect(keys(en as Tree)).toContain(k);
    }
  });

  it("has no empty translation", () => {
    for (const tree of [en, tr] as Tree[]) {
      const flat = keys(tree);
      expect(flat.length).toBeGreaterThan(0);
    }
    const empty = (t: Tree): boolean =>
      Object.values(t).some((v) => (typeof v === "string" ? v.trim() === "" : empty(v)));
    expect(empty(en as Tree) || empty(tr as Tree)).toBe(false);
  });

  it("rejects literal text in JSX", async () => {
    const eslint = new ESLint({ cwd: process.cwd() });
    const [result] = await eslint.lintText("export const A = () => <p>Projeler</p>;", {
      filePath: "components/sample.tsx",
    });
    expect(result.messages.map((m) => m.ruleId)).toContain("react/jsx-no-literals");
  });
});
