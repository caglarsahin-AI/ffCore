import type { Role } from "@/lib/access";
import { hasRole } from "@/lib/access";

// Console menu: groups, screens and the minimum role per screen (brief 10, R10.5).
// Single source for menu visibility and route guarding. `ready: false` screens belong
// to later packages (10b-poc, 10c) and render an explicit "coming soon" page.
export type NavItem = { key: string; href: string; minRole: Role; ready: boolean };
export type NavGroup = { key: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  {
    key: "overview",
    items: [{ key: "overview", href: "/overview", minRole: "analyst", ready: false }],
  },
  {
    key: "build",
    items: [
      { key: "providers", href: "/providers", minRole: "admin", ready: true },
      { key: "models", href: "/models", minRole: "admin", ready: true },
      { key: "knowledgeBases", href: "/knowledge-bases", minRole: "analyst", ready: false },
      { key: "dataSources", href: "/data-sources", minRole: "developer", ready: false },
      { key: "tools", href: "/tools", minRole: "developer", ready: false },
      { key: "mcpServers", href: "/mcp-servers", minRole: "developer", ready: false },
      { key: "agents", href: "/agents", minRole: "analyst", ready: false },
    ],
  },
  {
    key: "operate",
    items: [
      { key: "runs", href: "/runs", minRole: "analyst", ready: false },
      { key: "approvals", href: "/approvals", minRole: "analyst", ready: false },
      { key: "evaluations", href: "/evaluations", minRole: "analyst", ready: false },
      { key: "guardrails", href: "/guardrails", minRole: "developer", ready: false },
      { key: "channels", href: "/channels", minRole: "developer", ready: false },
      { key: "usage", href: "/usage", minRole: "admin", ready: false },
      { key: "systemStatus", href: "/system-status", minRole: "admin", ready: false },
    ],
  },
  {
    key: "admin",
    items: [
      { key: "projects", href: "/projects", minRole: "admin", ready: true },
      { key: "users", href: "/users", minRole: "admin", ready: false },
      { key: "apiKeys", href: "/api-keys", minRole: "admin", ready: false },
      { key: "quotas", href: "/quotas", minRole: "developer", ready: false },
      { key: "audit", href: "/audit", minRole: "admin", ready: false },
      { key: "retention", href: "/retention", minRole: "admin", ready: false },
      { key: "settings", href: "/settings", minRole: "admin", ready: false },
    ],
  },
];

export function visibleGroups(role: Role): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => hasRole(role, item.minRole)),
  })).filter((group) => group.items.length > 0);
}

// The nav item that owns a path ("/projects/42/members" → projects); null if none.
export function itemForPath(pathname: string): NavItem | null {
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (pathname === item.href || pathname.startsWith(`${item.href}/`)) return item;
    }
  }
  return null;
}
