import { LocaleSwitcher } from "@/components/locale-switcher";
import { ProjectSwitcher } from "@/components/project-switcher";
import { ReadOnlyBadge } from "@/components/read-only-badge";
import { ThemeSwitcher } from "@/components/theme-switcher";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";

export function SiteHeader() {
  return (
    <header className="flex min-h-14 shrink-0 items-center gap-2 border-b bg-background">
      <div className="flex w-full flex-wrap items-center gap-3 px-4 py-2 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mx-1 h-4 data-vertical:self-auto" />
        <ProjectSwitcher />
        <div className="ml-auto flex flex-wrap items-center gap-3">
          <ReadOnlyBadge />
          <LocaleSwitcher />
          <ThemeSwitcher />
        </div>
      </div>
    </header>
  );
}
