"use client";

import { BotIcon } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { QueryError } from "@/components/screen";
import { useChatAgents } from "@/lib/api/chat-queries";
import { chatPath } from "@/lib/chat-view";

// The chat's start page (11): the project's published agents. No project selected: say so and
// point at the project selector in the top bar; nothing is chosen automatically (ARCH-10).
export function ChatHome({ projectId }: { projectId: string | null }) {
  const t = useTranslations("Chat");
  if (projectId === null) {
    return (
      <div className="mx-auto flex w-full max-w-xl flex-col gap-2 p-6" data-testid="chat-no-project">
        <h1 className="text-lg font-semibold">{t("noProjectTitle")}</h1>
        <p className="text-sm text-muted-foreground">{t("noProjectBody")}</p>
      </div>
    );
  }
  return <AgentPicker projectId={projectId} />;
}

function AgentPicker({ projectId }: { projectId: string }) {
  const t = useTranslations("Chat");
  const agents = useChatAgents(projectId);
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4 sm:p-6">
      <h1 className="text-lg font-semibold">{t("agentsTitle")}</h1>
      {agents.isPending && (
        <p className="text-sm text-muted-foreground" role="status">
          {t("loading")}
        </p>
      )}
      {agents.isError && <QueryError error={agents.error} />}
      {agents.isSuccess && agents.data.length === 0 && (
        <p className="text-sm text-muted-foreground" data-testid="chat-no-agents">
          {t("noAgents")}
        </p>
      )}
      {agents.isSuccess && agents.data.length > 0 && (
        <ul className="grid gap-3 sm:grid-cols-2">
          {agents.data.map((agent) => (
            <li key={agent.id}>
              <Link
                href={chatPath(agent.key)}
                className="flex h-full gap-3 rounded-xl border bg-card p-4 text-card-foreground hover:bg-muted/60 focus-visible:outline-2 focus-visible:outline-ring"
                data-testid="chat-agent"
              >
                <BotIcon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
                <span className="flex min-w-0 flex-col gap-1">
                  <span className="font-medium">{agent.name}</span>
                  {agent.description && <span className="text-sm text-muted-foreground">{agent.description}</span>}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
