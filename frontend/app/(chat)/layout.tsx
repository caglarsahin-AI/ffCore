import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ChatHeader } from "@/components/chat/chat-header";
import { QueryProvider } from "@/components/query-provider";
import { SessionProvider } from "@/components/session-provider";
import { SessionStatusPage } from "@/components/session-status-page";
import { PROJECT_COOKIE, selectedProject } from "@/lib/project";
import { getSession } from "@/lib/session";

// The end user chat (11): same session and project choice as the console, no admin menu. Every
// member may open it (`user` included); the API decides what each call may do.
export default async function ChatLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (session.status === "signedOut") redirect("/login");
  if (session.status !== "signedIn") return <SessionStatusPage session={session} />;
  const projectId = selectedProject(session.me, (await cookies()).get(PROJECT_COOKIE)?.value);
  return (
    <SessionProvider value={{ me: session.me, projectId }}>
      <QueryProvider>
        <div className="flex h-dvh flex-col bg-background text-foreground">
          <ChatHeader />
          <main className="flex min-h-0 flex-1 flex-col">{children}</main>
        </div>
      </QueryProvider>
    </SessionProvider>
  );
}
