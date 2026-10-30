"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { DisabledWithReason } from "@/components/disabled-with-reason";
import { QueryError, Screen } from "@/components/screen";
import { useAccess, useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { ToolActions } from "@/components/tool-actions";
import { ToolForm } from "@/components/tool-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { hasRole } from "@/lib/access";
import { useDeleteTool, useDiscoverTool, useTool } from "@/lib/api/tools-queries";
import type { Tool, ToolAuthType } from "@/lib/api/tools-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

export default function ToolPage() {
  const { projectId } = useSession();
  const { toolId } = useParams<{ toolId: string }>();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <ToolDetail key={`${projectId}:${toolId}`} projectId={projectId} toolId={toolId} />;
}

function ToolDetail({ projectId, toolId }: { projectId: string; toolId: string }) {
  const t = useTranslations("Tools");
  const tState = useTranslations("State");
  const query = useTool(projectId, toolId);
  if (query.isPending || (query.isError && isUnauthenticated(query.error))) {
    return <p className="text-muted-foreground">{tState("loading")}</p>;
  }
  if (query.isError) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink label={t("back")} />
        <QueryError error={query.error} />
      </div>
    );
  }
  return <Loaded projectId={projectId} tool={query.data} />;
}

function Loaded({ projectId, tool }: { projectId: string; tool: Tool }) {
  const t = useTranslations("Tools");
  const tState = useTranslations("State");
  const router = useRouter();
  const remove = useDeleteTool(projectId);
  const discover = useDiscoverTool(projectId);
  const report = useReportError();
  const { role, canWrite } = useAccess(projectId);
  const format = useFormatter();
  const [editing, setEditing] = useState(false);
  const isAdmin = hasRole(role, "admin");

  function onDelete() {
    if (!window.confirm(t("deleteConfirm", { name: tool.name }))) return;
    remove.mutate(tool.id, {
      onSuccess: () => {
        toast.success(tState("saved"));
        router.push("/tools");
      },
      onError: report,
    });
  }

  function onDiscover() {
    discover.mutate(tool.id, {
      onSuccess: (found) => toast.success(t("discovered", { count: found?.actions.length ?? 0 })),
      onError: report,
    });
  }

  const gate = (control: React.ReactElement<{ disabled?: boolean }>) =>
    isAdmin ? (
      <WriteGate projectId={projectId}>{control}</WriteGate>
    ) : (
      <DisabledWithReason reason={t("needsAdmin")} needs="admin">
        {control}
      </DisabledWithReason>
    );

  const actions = (
    <div className="flex flex-wrap gap-2">
      {gate(
        <Button onClick={onDiscover} disabled={discover.isPending} data-testid="tool-discover">
          {t("discover")}
        </Button>,
      )}
      {gate(
        <Button variant="outline" onClick={() => setEditing(true)} disabled={editing} data-testid="tool-edit">
          {t("edit")}
        </Button>,
      )}
      {gate(
        <Button variant="outline" onClick={onDelete} data-testid="tool-delete">
          {t("delete")}
        </Button>,
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <BackLink label={t("back")} />
      <Screen title={tool.name} description={t("description")} action={actions}>
        <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4" data-testid="tool-summary">
          <Fact label={t("key")} value={<span className="font-mono">{tool.key}</span>} />
          <Fact label={t("kind")} value={t(`kinds.${tool.kind}`)} />
          <Fact
            label={t("status")}
            value={
              <Badge variant={tool.status === "error" ? "destructive" : "secondary"} data-testid="tool-status">
                {t(`statuses.${tool.status}`)}
              </Badge>
            }
          />
          <Fact label={t("authType")} value={t(`authTypes.${tool.auth.type as ToolAuthType}`)} />
          <Fact label={t("endpoint")} value={<span className="font-mono break-all">{tool.endpoint_url}</span>} />
          <Fact label={t("lastError")} value={<span className="font-mono" data-testid="tool-last-error">{tool.last_error_code ?? t("none")}</span>} />
          <Fact label={t("discoveredAt")} value={tool.discovered_at ? format.dateTime(new Date(tool.discovered_at), { dateStyle: "medium", timeStyle: "short" }) : t("never")} />
        </dl>
        {editing && <ToolForm projectId={projectId} tool={tool} onDone={() => setEditing(false)} />}
        <h2 className="text-lg font-medium">{t("actionsTitle")}</h2>
        <p className="text-sm text-muted-foreground">{t("actionsHint")}</p>
        <ToolActions projectId={projectId} tool={tool} canChange={isAdmin && canWrite} />
      </Screen>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function BackLink({ label }: { label: string }) {
  return (
    <Link href="/tools" className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline">
      <ArrowLeftIcon className="size-4" />
      {label}
    </Link>
  );
}
