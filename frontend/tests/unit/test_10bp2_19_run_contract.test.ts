import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { RUN_STATUSES } from "@/lib/api/runs-queries";
import en from "@/messages/en.json";
import tr from "@/messages/tr.json";

// C9 lists (handbook/CONTRACTS.md): 8 run statuses and 18 run event types. Every one has a label in
// both languages; the console never maps an unknown value to a known one.
function c9List(name: string): string[] {
  const row = readFileSync("../handbook/CONTRACTS.md", "utf8")
    .split("\n")
    .find((line) => line.startsWith("| C9 |"));
  const match = new RegExp(`\`${name}\` \\(\\d+\\): ([^;]+);`).exec(row ?? "");
  return (match?.[1] ?? "").split(",").map((v) => v.replaceAll("`", "").trim());
}

describe("test_10bp2_19_run_contract", () => {
  it("knows the C9 run statuses and labels each in both languages", () => {
    const statuses = c9List("runs.status");
    expect(statuses).toHaveLength(8);
    expect([...RUN_STATUSES].sort()).toEqual([...statuses].sort());
    for (const status of statuses) {
      expect(en.Runs.statuses).toHaveProperty(status);
      expect(tr.Runs.statuses).toHaveProperty(status);
      expect(en.TestPanel.phases).toBeDefined();
    }
  });

  it("labels each of the 18 C9 run event types in both languages", () => {
    const types = c9List("run_events.type");
    expect(types).toHaveLength(18);
    expect(Object.keys(en.Runs.eventTypes).sort()).toEqual([...types].sort());
    expect(Object.keys(tr.Runs.eventTypes).sort()).toEqual([...types].sort());
  });
});
