"use client";

import { PlusIcon } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { DisabledWithReason } from "@/components/disabled-with-reason";
import { ListState, Screen } from "@/components/screen";
import { useAccess, useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { ToolForm } from "@/components/tool-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { WriteGate } from "@/components/write-gate";
import { hasRole } from "@/lib/access";
import { useTools } from "@/lib/api/tools-queries";

// Tools the backend consumes (05a). Developers read them; registering and changing is admin-only.
export default function ToolsPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <ToolList key={projectId} projectId={projectId} />;
}

function ToolList({ projectId }: { projectId: string }) {
  const t = useTranslations("Tools");
  const tools = useTools(projectId);
  const { role } = useAccess(projectId);
  const [adding, setAdding] = useState(false);

  const addButton = (
    <Button onClick={() => setAdding(true)} disabled={adding} data-testid="primary-action">
      <PlusIcon />
      {t("add")}
    </Button>
  );
  const action = hasRole(role, "admin") ? (
    <WriteGate projectId={projectId}>{addButton}</WriteGate>
  ) : (
    <DisabledWithReason reason={t("needsAdmin")} needs="admin">
      {addButton}
    </DisabledWithReason>
  );

  return (
    <Screen title={t("title")} description={t("description")} action={action}>
      {adding && <ToolForm projectId={projectId} onDone={() => setAdding(false)} />}
      <ListState query={tools} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="tool-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("name")}</TableHead>
                <TableHead>{t("key")}</TableHead>
                <TableHead>{t("kind")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead>{t("lastError")}</TableHead>
                <TableHead className="text-right">{t("actionsCount")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((tool) => (
                <TableRow key={tool.id} data-testid={`tool-${tool.key}`}>
                  <TableCell>
                    <Link className="font-medium text-primary underline-offset-4 hover:underline" href={`/tools/${tool.id}`}>
                      {tool.name}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono">{tool.key}</TableCell>
                  <TableCell>{t(`kinds.${tool.kind}`)}</TableCell>
                  <TableCell>
                    <Badge variant={tool.status === "error" ? "destructive" : tool.status === "discovered" ? "secondary" : "outline"}>
                      {t(`statuses.${tool.status}`)}
                    </Badge>
                  </TableCell>
                  <TableCell className="font-mono text-sm">{tool.last_error_code ?? t("none")}</TableCell>
                  <TableCell className="text-right font-mono">{tool.actions.length}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
