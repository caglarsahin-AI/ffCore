import { getTranslations } from "next-intl/server";

import { ReadinessView } from "@/components/readiness-view";
import { Screen } from "@/components/screen";
import { StatusPage } from "@/components/status-page";
import { backendUrl } from "@/lib/backend";
import { canOpen, itemForPath } from "@/lib/navigation";
import { readReadiness } from "@/lib/readiness";
import { getSession } from "@/lib/session";

// System status (K-10bp-0002 D1): rendered on the server behind the console sign-in, reading
// /readyz from the backend's internal address. No browser route to /readyz: its detail names model
// paths. The role is checked here, before the backend is read, not only by the client RouteGuard.
export const dynamic = "force-dynamic";

export default async function SystemStatusPage() {
  const session = await getSession();
  const item = itemForPath("/system-status");
  // The console layout already sent signed-out users to /login; anything else is not allowed here.
  if (session.status !== "signedIn" || !item || !canOpen(item, session.me.role, session.me.user.is_superadmin)) {
    return <StatusPage kind="forbidden" />;
  }
  const t = await getTranslations("SystemStatus");
  const readiness = await readReadiness(backendUrl());
  return (
    <Screen title={t("title")} description={t("description")}>
      <ReadinessView readiness={readiness} />
    </Screen>
  );
}
