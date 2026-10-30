"use client";

import { useFormatter, useTranslations } from "next-intl";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { editableVersion, rollbackTargets } from "@/lib/agent-definition";
import { useNewDraft, usePublish, useRollback } from "@/lib/api/agents-queries";
import type { Agent, AgentVersion } from "@/lib/api/agents-queries";

// Publish (brief 10 step 8): every save is a draft version; publishing makes it the version runs
// use; rollback goes back to a version published before. Unsaved changes block publishing.
export function VersionsTab({
  projectId,
  agent,
  versions,
  dirty,
}: {
  projectId: string;
  agent: Agent;
  versions: AgentVersion[];
  dirty: boolean;
}) {
  const t = useTranslations("Agents.wizard");
  const tState = useTranslations("State");
  const format = useFormatter();
  const report = useReportError();
  const publish = usePublish(projectId, agent.id);
  const rollback = useRollback(projectId, agent.id);
  const newDraft = useNewDraft(projectId, agent.id);
  const draft = editableVersion(versions);
  const latest = [...versions].sort((a, b) => b.version - a.version)[0];
  const targets = new Set(rollbackTargets(versions, agent.current_version_id).map((v) => v.id));
  const done = () => toast.success(tState("saved"));
  const when = (iso: string) => format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "short" });

  return (
    <div className="flex flex-col gap-4" data-testid="tab-versions">
      <div className="flex flex-wrap items-center gap-2">
        {draft ? (
          <WriteGate projectId={projectId}>
            <Button onClick={() => publish.mutate(draft.version, { onSuccess: done, onError: report })} disabled={dirty || publish.isPending} data-testid="agent-publish">
              {t("publishVersion", { version: draft.version })}
            </Button>
          </WriteGate>
        ) : (
          latest && (
            <WriteGate projectId={projectId}>
              <Button onClick={() => newDraft.mutate(latest.version, { onSuccess: done, onError: report })} disabled={newDraft.isPending} data-testid="agent-new-draft">
                {t("newDraft", { version: latest.version })}
              </Button>
            </WriteGate>
          )
        )}
        {dirty && <span className="text-sm text-muted-foreground">{t("saveBeforePublish")}</span>}
      </div>
      <Table data-testid="agent-versions">
        <TableHeader>
          <TableRow>
            <TableHead>{t("version")}</TableHead>
            <TableHead>{t("versionState")}</TableHead>
            <TableHead>{t("createdAt")}</TableHead>
            <TableHead>{t("publishedAt")}</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {[...versions]
            .sort((a, b) => b.version - a.version)
            .map((version) => (
              <TableRow key={version.id} data-testid={`version-${version.version}`}>
                <TableCell className="font-mono">{version.version}</TableCell>
                <TableCell>
                  {version.id === agent.current_version_id ? (
                    <Badge variant="secondary">{t("versionCurrent")}</Badge>
                  ) : version.published_at ? (
                    <Badge variant="outline">{t("versionPublished")}</Badge>
                  ) : (
                    <Badge variant="outline">{t("versionDraft")}</Badge>
                  )}
                </TableCell>
                <TableCell>{when(version.created_at)}</TableCell>
                <TableCell>{version.published_at ? when(version.published_at) : t("notPublished")}</TableCell>
                <TableCell className="text-right">
                  {targets.has(version.id) && (
                    <WriteGate projectId={projectId}>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => rollback.mutate(version.version, { onSuccess: done, onError: report })}
                        disabled={rollback.isPending}
                        data-testid="agent-rollback"
                      >
                        {t("rollbackTo", { version: version.version })}
                      </Button>
                    </WriteGate>
                  )}
                </TableCell>
              </TableRow>
            ))}
        </TableBody>
      </Table>
    </div>
  );
}
