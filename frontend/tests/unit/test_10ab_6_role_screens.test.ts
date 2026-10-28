import { describe, expect, it } from "vitest";

import { canOpen, itemForPath, visibleGroups } from "@/lib/navigation";

const keys = (role: Parameters<typeof visibleGroups>[0], superadmin: boolean) =>
  visibleGroups(role, superadmin).flatMap((group) => group.items.map((item) => item.key));

describe("test_10ab_6_role_screens", () => {
  it("hides tenant screens (backend require_superadmin) from a project admin", () => {
    const projectAdmin = keys("admin", false);
    expect(projectAdmin).toEqual(expect.arrayContaining(["projects", "models"]));
    for (const tenant of ["providers", "users", "audit"]) expect(projectAdmin).not.toContain(tenant);
  });

  it("shows tenant screens to a superadmin", () => {
    expect(keys("admin", true)).toEqual(expect.arrayContaining(["providers", "users", "audit"]));
  });

  it("guards routes with the same rule as the menu", () => {
    const providers = itemForPath("/providers")!;
    expect(canOpen(providers, "admin", false)).toBe(false);
    expect(canOpen(providers, "admin", true)).toBe(true);
    expect(canOpen(itemForPath("/projects")!, "analyst", false)).toBe(false);
  });
});
