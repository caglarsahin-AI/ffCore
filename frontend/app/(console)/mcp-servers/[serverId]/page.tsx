"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { McpAdminGate, useCanChangeMcp } from "@/components/mcp/admin-gate";
import { ConnectionTestResult } from "@/components/mcp/connection-test";
import { OperationsTable } from "@/components/mcp/operations-table";
import { McpServerForm } from "@/components/mcp/server-form";
import { statusVariant } from "@/components/mcp/server-status";
import { SpecReplaceForm } from "@/components/mcp/spec-replace-form";
import { QueryError, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useReportError } from "@/components/use-report-error";
import {
  useAddMcpServerTool,
  useDeleteMcpServer,
  useDiscoverMcpServer,
  useMcpServer,
  useTestMcpServer,
  useUpdateMcpServer,
} from "@/lib/api/mcp-servers-queries";
import type { McpServer, ServerStatus } from "@/lib/api/mcp-servers-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

export default function McpServerPage() {
  const { projectId } = useSession();
  const { serverId } = useParams<{ serverId: string }>();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <ServerDetail key={`${projectId}:${serverId}`} projectId={projectId} serverId={serverId} />;
}

function ServerDetail({ projectId, serverId }: { projectId: string; serverId: string }) {
  const t = useTranslations("McpServers");
  const tState = useTranslations("State");
  const query = useMcpServer(projectId, serverId);
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
  return <Loaded projectId={projectId} server={query.data} />;
}

// The next status the publish button sets: a draft or a stopped server is served, a served one stops.
const NEXT_STATUS: Record<ServerStatus, ServerStatus> = { draft: "active", disabled: "active", active: "disabled" };

// The operations editor starts again whenever the stored catalog, selection or aliases change.
const catalogKey = (server: McpServer) =>
  JSON.stringify([server.exposed_operations, server.operations.map((op) => [op.name, op.alias, op.alias_description, op.exposable])]);

function Loaded({ projectId, server }: { projectId: string; server: McpServer }) {
  const t = useTranslations("McpServers");
  const tState = useTranslations("State");
  const router = useRouter();
  const format = useFormatter();
  const report = useReportError();
  const canChange = useCanChangeMcp(projectId);
  const remove = useDeleteMcpServer(projectId);
  const update = useUpdateMcpServer(projectId);
  const discover = useDiscoverMcpServer(projectId);
  const test = useTestMcpServer(projectId);
  const addTool = useAddMcpServerTool(projectId);
  const [editing, setEditing] = useState(false);
  const [replacing, setReplacing] = useState(false);

  function onDelete() {
    if (!window.confirm(t("deleteConfirm", { name: server.name }))) return;
    remove.mutate(server.id, {
      onSuccess: () => {
        toast.success(tState("saved"));
        router.push("/mcp-servers");
      },
      onError: report,
    });
  }

  function onStatus() {
    update.mutate({ id: server.id, body: { status: NEXT_STATUS[server.status] } }, { onSuccess: () => toast.success(tState("saved")), onError: report });
  }

  function onDiscover() {
    discover.mutate(server.id, {
      onSuccess: (found) => toast.success(t("discovered", { count: found?.operations.length ?? 0 })),
      onError: report,
    });
  }

  const actions = (
    <div className="flex flex-wrap gap-2">
      <McpAdminGate projectId={projectId}>
        {server.status === "active" ? (
          <Button variant="outline" onClick={onStatus} disabled={update.isPending} data-testid="mcp-disable" data-write="">
            {t("disable")}
          </Button>
        ) : (
          <Button onClick={onStatus} disabled={update.isPending} data-testid="mcp-publish" data-write="">
            {server.status === "draft" ? t("publish") : t("enable")}
          </Button>
        )}
      </McpAdminGate>
      <McpAdminGate projectId={projectId}>
        <Button variant="outline" onClick={() => test.mutate(server.id, { onError: report })} disabled={test.isPending} data-testid="mcp-test" data-write="">
          {t("test")}
        </Button>
      </McpAdminGate>
      <McpAdminGate projectId={projectId}>
        <Button variant="outline" onClick={() => addTool.mutate(server.id, { onError: report })} disabled={addTool.isPending} data-testid="mcp-add-tool" data-write="">
          {t("addTool")}
        </Button>
      </McpAdminGate>
      <McpAdminGate projectId={projectId}>
        <Button variant="outline" onClick={() => setEditing(true)} disabled={editing} data-testid="mcp-edit" data-write="">
          {t("edit")}
        </Button>
      </McpAdminGate>
      <McpAdminGate projectId={projectId}>
        <Button variant="outline" onClick={onDelete} disabled={remove.isPending} data-testid="mcp-delete" data-write="">
          {t("delete")}
        </Button>
      </McpAdminGate>
    </div>
  );

  const when = (iso: string | null) => (iso ? format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "short" }) : t("never"));

  return (
    <div className="flex flex-col gap-4">
      <BackLink label={t("back")} />
      <Screen title={server.name} description={t("detailDescription")} action={actions}>
        <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4" data-testid="mcp-server-summary">
          <Fact label={t("key")} value={<span className="font-mono">{server.key}</span>} />
          <Fact label={t("sourceKind")} value={t(`sourceKinds.${server.source_kind}`)} />
          <Fact
            label={t("status")}
            value={
              <Badge variant={statusVariant(server.status)} data-testid="mcp-server-status">
                {t(`statuses.${server.status}`)}
              </Badge>
            }
          />
          <Fact label={t("endpoint")} value={<span className="font-mono break-all">{server.endpoint_path}</span>} />
          <Fact label={t("upstream")} value={<span className="font-mono break-all">{server.upstream_base_url}</span>} />
          <Fact label={t("authType")} value={t(`authTypes.${server.upstream_auth.type as "none"}`)} />
          <Fact label={t("access")} value={t(`accessModes.${server.access}`)} />
          <Fact label={t("guardrailMode")} value={`${t(`guardrailModes.${server.guardrail_mode}`)} · ${server.guardrail_policy_key}`} />
          <Fact label={t("discoveredAt")} value={when(server.discovered_at)} />
          <Fact label={t("lastError")} value={<span className="font-mono">{server.last_error_code ?? t("none")}</span>} />
        </dl>
        {test.data && <ConnectionTestResult result={test.data} />}
        {addTool.data && (
          <p className="text-sm" role="status">
            {t("toolAdded", { name: addTool.data.name })}{" "}
            <Link className="text-primary underline-offset-4 hover:underline" href={`/tools/${addTool.data.id}`} data-testid="mcp-added-tool">
              {t("openTool")}
            </Link>
          </p>
        )}
        {editing && <McpServerForm projectId={projectId} server={server} onDone={() => setEditing(false)} />}
        <Tabs defaultValue="operations">
          <TabsList>
            <TabsTrigger value="operations">{t("tabs.operations")}</TabsTrigger>
          </TabsList>
          <TabsContent value="operations" className="flex flex-col gap-4 pt-2">
            <div className="flex flex-wrap gap-2">
              {server.source_kind === "openapi" && (
                <McpAdminGate projectId={projectId}>
                  <Button variant="outline" onClick={() => setReplacing(true)} disabled={replacing} data-testid="mcp-spec-replace-open" data-write="">
                    {t("replaceSpec")}
                  </Button>
                </McpAdminGate>
              )}
              <McpAdminGate projectId={projectId}>
                <Button variant="outline" onClick={onDiscover} disabled={discover.isPending} data-testid="mcp-discover" data-write="">
                  {t(`discover.${server.source_kind}`)}
                </Button>
              </McpAdminGate>
            </div>
            {replacing && <SpecReplaceForm projectId={projectId} server={server} onDone={() => setReplacing(false)} />}
            <OperationsTable key={catalogKey(server)} projectId={projectId} server={server} canChange={canChange} />
          </TabsContent>
        </Tabs>
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
    <Link href="/mcp-servers" className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline">
      <ArrowLeftIcon className="size-4" />
      {label}
    </Link>
  );
}
