import { describe, expect, it } from "vitest";

import { NAV_ICONS } from "@/components/app-sidebar";
import { NAV_GROUPS } from "@/lib/navigation";

// 10c-2 e2e run 1: the new "alerts" menu item had no sidebar icon, so every console page failed
// to render (React: element type undefined). Every menu item needs its icon.
describe("test_10c2_9_nav_icons", () => {
  it("has an icon for every menu item", () => {
    for (const item of NAV_GROUPS.flatMap((g) => g.items)) expect(NAV_ICONS[item.key], item.key).toBeTruthy();
  });
});
