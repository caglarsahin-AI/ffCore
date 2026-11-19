"use client";

import { PlusIcon } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { McpAdminGate } from "@/components/mcp/admin-gate";
import { McpServerForm } from "@/components/mcp/server-form";
import { statusVariant } from "@/components/mcp/server-status";
import { ListState, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useMcpServers } from "@/lib/api/mcp-servers-queries";

// Published MCP servers (05b, plan/05 A3): an OpenAPI document or a remote MCP server served at
// /mcp/<key>/. Developers read them; publishing and changing is a project admin's (backend Admin).
export default function McpServersPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <ServerList key={projectId} projectId={projectId} />;
}

function ServerList({ projectId }: { projectId: string }) {
  const t = useTranslations("McpServers");
  const servers = useMcpServers(projectId);
  const [adding, setAdding] = useState(false);

  const action = (
    <McpAdminGate projectId={projectId}>
      <Button onClick={() => setAdding(true)} disabled={adding} data-testid="primary-action" data-write="">
        <PlusIcon />
        {t("add")}
      </Button>
    </McpAdminGate>
  );

  return (
    <Screen title={t("title")} description={t("description")} action={action}>
      {adding && <McpServerForm projectId={projectId} onDone={() => setAdding(false)} />}
      <ListState query={servers} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="mcp-server-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("name")}</TableHead>
                <TableHead>{t("key")}</TableHead>
                <TableHead>{t("sourceKind")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead>{t("endpoint")}</TableHead>
                <TableHead className="text-right">{t("exposedCount")}</TableHead>
                <TableHead>{t("lastError")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((server) => (
                <TableRow key={server.id} data-testid={`mcp-server-${server.key}`}>
                  <TableCell>
                    <Link className="font-medium text-primary underline-offset-4 hover:underline" href={`/mcp-servers/${server.id}`}>
                      {server.name}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono">{server.key}</TableCell>
                  <TableCell>{t(`sourceKinds.${server.source_kind}`)}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant(server.status)}>{t(`statuses.${server.status}`)}</Badge>
                  </TableCell>
                  <TableCell className="font-mono text-sm">{server.endpoint_path}</TableCell>
                  <TableCell className="text-right font-mono" data-testid="mcp-server-exposed">
                    {`${server.exposed_operations.length} / ${server.operations.length}`}
                  </TableCell>
                  <TableCell className="font-mono text-sm">{server.last_error_code ?? t("none")}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
