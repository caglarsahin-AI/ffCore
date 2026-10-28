import { describe, expect, it } from "vitest";

import { hasRole } from "@/lib/access";
import { itemForPath, visibleGroups } from "@/lib/navigation";

const keys = (role: Parameters<typeof visibleGroups>[0]) =>
  visibleGroups(role, true).flatMap((group) => group.items.map((item) => item.key));

describe("test_10a_5_role_menu_visibility", () => {
  it("orders roles user < analyst < developer < admin", () => {
    expect(hasRole("admin", "analyst")).toBe(true);
    expect(hasRole("analyst", "developer")).toBe(false);
    expect(hasRole("user", "analyst")).toBe(false);
  });

  it("hides admin screens from analyst", () => {
    const analyst = keys("analyst");
    expect(analyst).toEqual(
      expect.arrayContaining(["agents", "knowledgeBases", "evaluations", "approvals", "runs"]),
    );
    for (const hidden of ["providers", "models", "projects", "users", "tools", "quotas"]) {
      expect(analyst).not.toContain(hidden);
    }
  });

  it("adds developer screens on top of analyst", () => {
    const developer = keys("developer");
    for (const shown of ["tools", "mcpServers", "dataSources", "channels", "quotas", "guardrails"]) {
      expect(developer).toContain(shown);
    }
    expect(developer).not.toContain("providers");
  });

  it("shows every screen to admin and no group to user", () => {
    expect(keys("admin")).toContain("providers");
    expect(keys("admin")).toContain("projects");
    expect(visibleGroups("user", true)).toEqual([]);
  });

  it("maps nested paths to their owning item", () => {
    expect(itemForPath("/projects/42/members")?.key).toBe("projects");
    expect(itemForPath("/providers")?.minRole).toBe("admin");
    expect(itemForPath("/nope")).toBeNull();
  });
});
