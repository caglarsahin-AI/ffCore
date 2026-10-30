import { describe, expect, it } from "vitest";

import { editableVersion, rollbackTargets } from "@/lib/agent-definition";

const v = (version: number, published_at: string | null, id = `v${version}`) => ({ id, version, published_at });

describe("test_10bp2_17_agent_versions", () => {
  it("edits the latest version only while it is a draft (a published version is never edited)", () => {
    expect(editableVersion([v(1, null)])?.version).toBe(1);
    expect(editableVersion([v(1, "2026-10-30T10:00:00Z"), v(2, null)])?.version).toBe(2);
    expect(editableVersion([v(2, "2026-10-30T10:00:00Z"), v(1, "2026-10-29T10:00:00Z")])).toBeNull();
    expect(editableVersion([])).toBeNull();
  });

  it("offers rollback only to versions published before, not to the current one", () => {
    const versions = [v(1, "2026-10-28T10:00:00Z"), v(2, null), v(3, "2026-10-30T10:00:00Z")];
    expect(rollbackTargets(versions, "v3").map((x) => x.version)).toEqual([1]);
    expect(rollbackTargets(versions, null).map((x) => x.version)).toEqual([3, 1]);
  });
});
