import { describe, expect, it } from "vitest";

import { accessFor, selectedProject } from "@/lib/project";
import type { SignedInMe } from "@/lib/project";

const member = (over: Partial<SignedInMe> = {}): SignedInMe => ({
  user: { id: "u1", email: "a@example.org", full_name: "A", is_superadmin: false },
  role: "admin",
  access: "edit",
  memberships: [
    { project_id: "p-edit", project_key: "alpha", role: "admin", access: "edit" },
    { project_id: "p-read", project_key: "beta", role: "analyst", access: "read" },
  ],
  ...over,
});

describe("test_10ab_4_project_access", () => {
  it("takes write access from the selected project's membership, not the highest one", () => {
    expect(accessFor(member(), "p-read")).toEqual({ role: "analyst", access: "read" });
    expect(accessFor(member(), "p-edit")).toEqual({ role: "admin", access: "edit" });
  });

  it("uses the superadmin's own access mode in every project", () => {
    const superadmin = member({
      user: { id: "u1", email: "a@example.org", full_name: "A", is_superadmin: true },
      access: "read",
      memberships: [],
    });
    expect(accessFor(superadmin, "any-project")).toEqual({ role: "admin", access: "read" });
  });

  it("never picks a project on its own: unknown or missing selection is no selection", () => {
    expect(selectedProject(member(), "p-edit")).toBe("p-edit");
    expect(selectedProject(member(), "p-other")).toBeNull();
    expect(selectedProject(member(), undefined)).toBeNull();
  });

  it("falls back to the session's own role and access without a selected project", () => {
    expect(accessFor(member(), null)).toEqual({ role: "admin", access: "edit" });
  });
});
