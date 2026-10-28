import { PlugZapIcon, UserXIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import { SignOutButton } from "@/components/sign-out-button";
import type { SessionResult } from "@/lib/session-core";

type Props = { session: Extract<SessionResult, { status: "unavailable" | "noMembership" }> };

// Full-page states before the console can open: the backend did not answer (never shown as a
// sign-in page, ARCH-06) or the user belongs to no project yet.
export function SessionStatusPage({ session }: Props) {
  const t = useTranslations("Session");
  const tState = useTranslations("State");
  const unavailable = session.status === "unavailable";
  const Icon = unavailable ? PlugZapIcon : UserXIcon;
  return (
    <main className="min-h-screen bg-background p-6">
      <section
        className="mx-auto flex max-w-lg flex-col items-center gap-3 py-16 text-center"
        data-testid={`status-${session.status}`}
      >
        <Icon className="size-10 text-muted-foreground" aria-hidden />
        <h1 className="text-2xl font-semibold">{unavailable ? t("unavailableTitle") : t("noMembershipTitle")}</h1>
        <p className="text-muted-foreground">{unavailable ? t("unavailableBody") : t("noMembershipBody")}</p>
        {unavailable ? (
          <details className="text-sm text-muted-foreground">
            <summary className="cursor-pointer">{tState("details")}</summary>
            <pre className="mt-2 whitespace-pre-wrap">{session.reason}</pre>
          </details>
        ) : (
          <SignOutButton />
        )}
      </section>
    </main>
  );
}
