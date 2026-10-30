"use client";

import {
  ActivityIcon,
  ArchiveIcon,
  BarChart3Icon,
  BotIcon,
  CableIcon,
  CheckCheckIcon,
  CpuIcon,
  DatabaseIcon,
  FileClockIcon,
  FlaskConicalIcon,
  FolderKanbanIcon,
  GaugeIcon,
  KeyRoundIcon,
  LayoutDashboardIcon,
  LibraryIcon,
  ListChecksIcon,
  MessagesSquareIcon,
  ServerIcon,
  Settings2Icon,
  ShieldIcon,
  UsersIcon,
  WrenchIcon,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

import { NavUser } from "@/components/nav-user";
import { useAccess, useSession } from "@/components/session-provider";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { hasRole } from "@/lib/access";
import { usePendingApprovalCount } from "@/lib/api/approvals-queries";
import { visibleGroups } from "@/lib/navigation";

const ICONS: Record<string, LucideIcon> = {
  overview: LayoutDashboardIcon,
  providers: ServerIcon,
  models: CpuIcon,
  knowledgeBases: LibraryIcon,
  dataSources: DatabaseIcon,
  tools: WrenchIcon,
  mcpServers: CableIcon,
  agents: BotIcon,
  runs: ActivityIcon,
  approvals: CheckCheckIcon,
  evaluations: FlaskConicalIcon,
  guardrails: ShieldIcon,
  channels: MessagesSquareIcon,
  usage: BarChart3Icon,
  systemStatus: GaugeIcon,
  projects: FolderKanbanIcon,
  users: UsersIcon,
  apiKeys: KeyRoundIcon,
  quotas: ListChecksIcon,
  audit: FileClockIcon,
  retention: ArchiveIcon,
  settings: Settings2Icon,
};

// sidebar-07 layout: collapsible to icons, grouped menu filtered by role (brief 10).
export function AppSidebar() {
  const t = useTranslations("Nav");
  const tHome = useTranslations("Home");
  const tBrand = useTranslations("Brand");
  const { menuRole, isSuperadmin } = useAccess();
  const pathname = usePathname();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link href="/" />}>
              {/* Narrow FF crop: the full badge is unreadable at 32 px (assets/icons/README.md). */}
              <Image
                src="/brand/ffcore-icon-128.png"
                alt={tBrand("logoAlt")}
                width={32}
                height={32}
                priority
                className="size-8 shrink-0 rounded-lg"
                data-testid="sidebar-logo"
              />
              <span className="truncate font-semibold">{tHome("title")}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {visibleGroups(menuRole, isSuperadmin).map((group) => (
          <SidebarGroup key={group.key} data-testid={`nav-group-${group.key}`}>
            <SidebarGroupLabel>{t(`groups.${group.key}` as "groups.build")}</SidebarGroupLabel>
            <SidebarMenu>
              {group.items.map((item) => {
                const Icon = ICONS[item.key];
                const label = t(`items.${item.key}` as "items.projects");
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                return (
                  <SidebarMenuItem key={item.key}>
                    <SidebarMenuButton
                      isActive={active}
                      tooltip={label}
                      render={<Link href={item.href} data-testid={`nav-${item.key}`} />}
                    >
                      <Icon />
                      <span>{label}</span>
                    </SidebarMenuButton>
                    {item.key === "approvals" && <ApprovalBadge />}
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

// Pending approvals of the selected project (07 /approvals/count); hidden at zero. Analysts and up
// see the approvals menu, so the count is read only for them.
function ApprovalBadge() {
  const t = useTranslations("Approvals");
  const { projectId } = useSession();
  const { role } = useAccess();
  const count = usePendingApprovalCount(projectId, hasRole(role, "analyst"));
  if (!count.data) return null;
  return (
    <SidebarMenuBadge aria-label={t("pendingCount", { count: count.data })} data-testid="nav-approvals-badge">
      {count.data}
    </SidebarMenuBadge>
  );
}
