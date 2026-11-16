"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { GateFailure } from "@/components/eval/gate-failure";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { editableVersion, rollbackTargets } from "@/lib/agent-definition";
import { useNewDraft, usePublish, useRollback } from "@/lib/api/agents-queries";
import type { Agent, AgentVersion } from "@/lib/api/agents-queries";
import { ApiError } from "@/lib/api/client";

// Publish (brief 10 step 8): every save is a draft version; publishing makes it the version runs
// use; rollback goes back to a version published before. Unsaved changes block publishing. A
// publish the exam gate refuses (409 eval_gate_failed) shows each suite and why, and an admin may
// publish past it with a reason (09-2); each version links to the exam that opened its gate.
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
  const [refused, setRefused] = useState<{ version: number; error: ApiError } | null>(null);
  const done = () => {
    setRefused(null);
    toast.success(tState("saved"));
  };
  const onPublishError = (version: number) => (error: unknown) => {
    if (error instanceof ApiError && error.code === "eval_gate_failed") return setRefused({ version, error });
    setRefused(null);
    report(error);
  };
  const when = (iso: string) => format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "short" });

  return (
    <div className="flex flex-col gap-4" data-testid="tab-versions">
      <div className="flex flex-wrap items-center gap-2">
        {draft ? (
          <WriteGate projectId={projectId}>
            <Button onClick={() => publish.mutate(draft.version, { onSuccess: done, onError: onPublishError(draft.version) })} disabled={dirty || publish.isPending} data-testid="agent-publish">
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
      {refused && (
        <GateFailure
          projectId={projectId}
          error={refused.error}
          pending={publish.isPending}
          onForce={(reason) =>
            publish.mutate({ version: refused.version, force: true, force_reason: reason }, { onSuccess: done, onError: onPublishError(refused.version) })
          }
        />
      )}
      <Table data-testid="agent-versions">
        <TableHeader>
          <TableRow>
            <TableHead>{t("version")}</TableHead>
            <TableHead>{t("versionState")}</TableHead>
            <TableHead>{t("createdAt")}</TableHead>
            <TableHead>{t("publishedAt")}</TableHead>
            <TableHead>{t("versionExam")}</TableHead>
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
                <TableCell data-testid="version-exam">
                  {version.eval_run_id ? (
                    <Link className="text-primary underline-offset-4 hover:underline" href={`/evaluations/runs/${version.eval_run_id}`}>
                      {t("versionExamLink")}
                    </Link>
                  ) : (
                    "—"
                  )}
                </TableCell>
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
