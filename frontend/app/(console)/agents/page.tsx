"use client";

import { PlusIcon } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { AgentCreateForm } from "@/components/agent-create-form";
import { ListState, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { WriteGate } from "@/components/write-gate";
import { useAgents } from "@/lib/api/agents-queries";

// Agents of the project (06a). Analysts with edit access build, test and publish them.
export default function AgentsPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <AgentList key={projectId} projectId={projectId} />;
}

function AgentList({ projectId }: { projectId: string }) {
  const t = useTranslations("Agents");
  const agents = useAgents(projectId);
  const [adding, setAdding] = useState(false);

  const action = (
    <WriteGate projectId={projectId}>
      <Button onClick={() => setAdding(true)} disabled={adding} data-testid="primary-action">
        <PlusIcon />
        {t("add")}
      </Button>
    </WriteGate>
  );

  return (
    <Screen title={t("title")} description={t("description")} action={action}>
      {adding && <AgentCreateForm projectId={projectId} onCancel={() => setAdding(false)} />}
      <ListState query={agents} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="agent-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("name")}</TableHead>
                <TableHead>{t("key")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead className="text-right">{t("latestVersion")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((agent) => (
                <TableRow key={agent.id} data-testid={`agent-${agent.key}`}>
                  <TableCell>
                    <Link className="font-medium text-primary underline-offset-4 hover:underline" href={`/agents/${agent.id}`}>
                      {agent.name}
                    </Link>
                    {agent.description && <p className="text-sm text-muted-foreground">{agent.description}</p>}
                  </TableCell>
                  <TableCell className="font-mono">{agent.key}</TableCell>
                  <TableCell>
                    <Badge variant={agent.status === "published" ? "secondary" : "outline"} data-testid="agent-status">
                      {t(`statuses.${agent.status}`)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono">{agent.latest_version}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
