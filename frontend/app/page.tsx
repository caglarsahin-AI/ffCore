import { redirect } from "next/navigation";

import { visibleGroups } from "@/lib/navigation";
import { getSession } from "@/lib/session";

// Entry point: the first screen the role can open, or sign-in without a session.
export default async function Home() {
  const session = await getSession();
  if (!session) redirect("/login");
  const first = visibleGroups(session.role).flatMap((group) => group.items).find((item) => item.ready);
  redirect(first?.href ?? "/overview");
}
