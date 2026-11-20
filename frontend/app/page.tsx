import { redirect } from "next/navigation";

import { SessionStatusPage } from "@/components/session-status-page";
import { homePath } from "@/lib/navigation";
import { getSession } from "@/lib/session";

// Entry point: the first screen the role can open (`user`: the chat), or sign-in without a session.
export default async function Home() {
  const session = await getSession();
  if (session.status === "signedOut") redirect("/login");
  if (session.status !== "signedIn") return <SessionStatusPage session={session} />;
  const { role, user } = session.me;
  redirect(homePath(role, user.is_superadmin));
}
