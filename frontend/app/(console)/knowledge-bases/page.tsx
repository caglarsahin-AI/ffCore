"use client";

import { PlusIcon } from "lucide-react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { DisabledWithReason } from "@/components/disabled-with-reason";
import { KnowledgeBaseForm } from "@/components/kb-form";
import { ListState, Screen } from "@/components/screen";
import { useAccess, useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { WriteGate } from "@/components/write-gate";
import { hasRole } from "@/lib/access";
import { useKnowledgeBases } from "@/lib/api/knowledge-queries";

// Knowledge bases belong to a project (04a).
export default function KnowledgeBasesPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  // Keyed by project: switching projects drops an open form and its state (10a-formlar kalıbı).
  return <KnowledgeBaseList key={projectId} projectId={projectId} />;
}

function KnowledgeBaseList({ projectId }: { projectId: string }) {
  const t = useTranslations("KnowledgeBases");
  const bases = useKnowledgeBases(projectId);
  const { role } = useAccess(projectId);
  const [adding, setAdding] = useState(false);

  const addButton = (
    <Button onClick={() => setAdding(true)} disabled={adding} data-testid="primary-action">
      <PlusIcon />
      {t("add")}
    </Button>
  );
  // Creating a knowledge base is admin-only in 04a; other roles see why the button is off.
  const action = hasRole(role, "admin") ? (
    <WriteGate projectId={projectId}>{addButton}</WriteGate>
  ) : (
    <DisabledWithReason reason={t("needsAdmin")} needs="admin">
      {addButton}
    </DisabledWithReason>
  );

  return (
    <Screen title={t("title")} description={t("description")} action={action}>
      {adding && <KnowledgeBaseForm projectId={projectId} onDone={() => setAdding(false)} />}
      <ListState query={bases} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="kb-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("name")}</TableHead>
                <TableHead>{t("key")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead className="text-right">{t("documents")}</TableHead>
                <TableHead className="text-right">{t("chunks")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((kb) => (
                <TableRow key={kb.id} data-testid={`kb-${kb.key}`}>
                  <TableCell>
                    <Link className="font-medium text-primary underline-offset-4 hover:underline" href={`/knowledge-bases/${kb.id}`}>
                      {kb.name}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono">{kb.key}</TableCell>
                  <TableCell>
                    <Badge variant={kb.status === "active" ? "secondary" : "outline"}>{t(`statuses.${kb.status}`)}</Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono">{kb.document_count}</TableCell>
                  <TableCell className="text-right font-mono" data-testid="kb-row-chunks">
                    {kb.chunk_count}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
