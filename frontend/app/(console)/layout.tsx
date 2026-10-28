import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AppSidebar } from "@/components/app-sidebar";
import { QueryProvider } from "@/components/query-provider";
import { RouteGuard } from "@/components/route-guard";
import { SessionProvider } from "@/components/session-provider";
import { SiteHeader } from "@/components/site-header";
import { SessionStatusPage } from "@/components/session-status-page";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { PROJECT_COOKIE, selectedProject } from "@/lib/project";
import { getSession } from "@/lib/session";

export default async function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (session.status === "signedOut") redirect("/login");
  if (session.status !== "signedIn") return <SessionStatusPage session={session} />;
  const projectId = selectedProject(session.me, (await cookies()).get(PROJECT_COOKIE)?.value);
  return (
    <SessionProvider value={{ me: session.me, projectId }}>
      <QueryProvider>
        <SidebarProvider>
          <AppSidebar />
          <SidebarInset>
            <SiteHeader />
            <div className="flex flex-1 flex-col p-4 lg:p-6">
              <RouteGuard>{children}</RouteGuard>
            </div>
          </SidebarInset>
        </SidebarProvider>
      </QueryProvider>
    </SessionProvider>
  );
}
