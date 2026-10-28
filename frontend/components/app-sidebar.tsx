"use client";

import {
  ActivityIcon,
  ArchiveIcon,
  BarChart3Icon,
  BotIcon,
  BrainCircuitIcon,
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
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

import { NavUser } from "@/components/nav-user";
import { useAccess } from "@/components/session-provider";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
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
  const { menuRole, isSuperadmin } = useAccess();
  const pathname = usePathname();

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" render={<Link href="/" />}>
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <BrainCircuitIcon className="size-4" />
              </div>
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
