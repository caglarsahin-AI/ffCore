"use client";

import { usePathname } from "next/navigation";

import { useAccess } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { hasRole } from "@/lib/access";
import { itemForPath } from "@/lib/navigation";

// A screen outside the role renders "you do not have access" (brief 10). UI convenience only:
// the API enforces the role with 403.
export function RouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { role } = useAccess();
  const item = itemForPath(pathname);
  if (item && !hasRole(role, item.minRole)) return <StatusPage kind="forbidden" />;
  return children;
}
