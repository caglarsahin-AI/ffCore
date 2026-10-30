"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { AgentWizard } from "@/components/agent-wizard/agent-wizard";
import { QueryError, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useAgent, useAgentVersions, useDeleteAgent } from "@/lib/api/agents-queries";
import type { Agent, AgentVersion } from "@/lib/api/agents-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

export default function AgentPage() {
  const { projectId } = useSession();
  const { agentId } = useParams<{ agentId: string }>();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <AgentDetail key={`${projectId}:${agentId}`} projectId={projectId} agentId={agentId} />;
}

function AgentDetail({ projectId, agentId }: { projectId: string; agentId: string }) {
  const t = useTranslations("Agents");
  const tState = useTranslations("State");
  const agent = useAgent(projectId, agentId);
  const versions = useAgentVersions(projectId, agentId);
  const waiting = (q: { isPending: boolean; isError: boolean; error: Error | null }) =>
    q.isPending || (q.isError && q.error !== null && isUnauthenticated(q.error));
  if (waiting(agent) || waiting(versions)) return <p className="text-muted-foreground">{tState("loading")}</p>;
  const failed = agent.error ?? versions.error;
  if (failed || !agent.data || !versions.data) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink label={t("back")} />
        {failed && <QueryError error={failed} />}
      </div>
    );
  }
  return <Loaded projectId={projectId} agent={agent.data} versions={versions.data} />;
}

function Loaded({ projectId, agent, versions }: { projectId: string; agent: Agent; versions: AgentVersion[] }) {
  const t = useTranslations("Agents");
  const tState = useTranslations("State");
  const router = useRouter();
  const remove = useDeleteAgent(projectId);
  const report = useReportError();

  function onDelete() {
    if (!window.confirm(t("deleteConfirm", { name: agent.name }))) return;
    remove.mutate(agent.id, {
      onSuccess: () => {
        toast.success(tState("saved"));
        router.push("/agents");
      },
      onError: report,
    });
  }

  const action = (
    <div className="flex items-center gap-2">
      <Badge variant={agent.status === "published" ? "secondary" : "outline"} data-testid="agent-detail-status">
        {t(`statuses.${agent.status}`)}
      </Badge>
      <WriteGate projectId={projectId}>
        <Button variant="outline" onClick={onDelete} data-testid="agent-delete">
          {t("delete")}
        </Button>
      </WriteGate>
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <BackLink label={t("back")} />
      <Screen title={agent.name} description={agent.description || t("description")} action={action}>
        <AgentWizard projectId={projectId} agent={agent} versions={versions} />
      </Screen>
    </div>
  );
}

function BackLink({ label }: { label: string }) {
  return (
    <Link href="/agents" className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline">
      <ArrowLeftIcon className="size-4" />
      {label}
    </Link>
  );
}
