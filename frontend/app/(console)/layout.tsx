import { AppSidebar } from "@/components/app-sidebar";
import { RouteGuard } from "@/components/route-guard";
import { SessionProvider } from "@/components/session-provider";
import { SiteHeader } from "@/components/site-header";
import { StatusPage } from "@/components/status-page";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { getSession } from "@/lib/session";

export default async function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (!session) {
    return (
      <main className="min-h-screen bg-background p-6">
        <StatusPage kind="sessionUnavailable" />
      </main>
    );
  }
  return (
    <SessionProvider session={session}>
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset>
          <SiteHeader />
          <div className="flex flex-1 flex-col p-4 lg:p-6">
            <RouteGuard>{children}</RouteGuard>
          </div>
        </SidebarInset>
      </SidebarProvider>
    </SessionProvider>
  );
}
