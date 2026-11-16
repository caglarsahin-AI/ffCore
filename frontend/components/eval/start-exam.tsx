"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { FieldShell, SELECT } from "@/components/form-parts";
import { QueryError } from "@/components/screen";
import { useAccess } from "@/components/session-provider";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { editableVersion } from "@/lib/agent-definition";
import { useAgentVersions, useAgents } from "@/lib/api/agents-queries";
import type { Agent, AgentVersion } from "@/lib/api/agents-queries";
import { useStartEvalRun } from "@/lib/api/eval-queries";
import type { Suite } from "@/lib/api/eval-queries";

// Start an exam (09 POST …/run?agent_version_id=). No `force` here. The agent is the suite's gated
// agent when it has one, else the user picks one. The version has a visible default (K-10C1-0002
// S4): the editable draft when there is one (the exam before a publish), else the published one;
// it is shown next to the button and can be changed. Refusals (422 eval_plan_exceeds_tick,
// eval_too_many_runs, item_input_invalid, 409 dataset_empty, ...) come back with their message.
export function defaultVersion(versions: readonly AgentVersion[], agent: Agent | undefined): AgentVersion | null {
  return editableVersion(versions) ?? versions.find((v) => v.id === agent?.current_version_id) ?? null;
}

export function StartExam({ projectId, suite }: { projectId: string; suite: Suite }) {
  const t = useTranslations("Evaluations.start");
  const agents = useAgents(projectId);
  const [picked, setPicked] = useState(suite.agent_id ?? "");
  const agentId = suite.agent_id ?? picked;

  if (agents.isError) return <QueryError error={agents.error} compact />;
  return (
    <section className="flex flex-col gap-3 rounded-xl border bg-card p-4" data-testid="start-exam-section">
      <h2 className="text-lg font-medium">{t("title")}</h2>
      <p className="text-sm text-muted-foreground">{t("hint")}</p>
      <FieldShell id="start-agent" label={t("agent")} hint={suite.agent_id ? t("agentFixed") : undefined}>
        {(a11y) => (
          <select {...a11y} className={SELECT} value={agentId} disabled={Boolean(suite.agent_id)} onChange={(e) => setPicked(e.target.value)}>
            <option value="">{agents.isPending ? t("loading") : t("chooseAgent")}</option>
            {(agents.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        )}
      </FieldShell>
      {agentId && <VersionPicker key={agentId} projectId={projectId} suite={suite} agent={agents.data?.find((a) => a.id === agentId)} agentId={agentId} />}
    </section>
  );
}

function VersionPicker({ projectId, suite, agent, agentId }: { projectId: string; suite: Suite; agent: Agent | undefined; agentId: string }) {
  const t = useTranslations("Evaluations.start");
  const router = useRouter();
  const report = useReportError();
  const { canWrite } = useAccess(projectId);
  const versions = useAgentVersions(projectId, agentId);
  const start = useStartEvalRun(projectId, suite.id);
  const [chosen, setChosen] = useState<string | null>(null);
  if (versions.isError) return <QueryError error={versions.error} compact />;
  const list = [...(versions.data ?? [])].sort((a, b) => b.version - a.version);
  const fallback = defaultVersion(list, agent);
  const versionId = chosen ?? fallback?.id ?? "";
  const version = list.find((v) => v.id === versionId);
  const label = (v: AgentVersion) =>
    v.id === agent?.current_version_id ? t("versionPublished", { version: v.version }) : v.published_at ? t("versionOld", { version: v.version }) : t("versionDraft", { version: v.version });

  return (
    <div className="flex flex-col gap-3">
      <FieldShell id="start-version" label={t("version")} hint={t("versionHint")}>
        {(a11y) => (
          <select {...a11y} className={SELECT} value={versionId} onChange={(e) => setChosen(e.target.value)} disabled={!canWrite}>
            {list.length === 0 && <option value="">{versions.isPending ? t("loading") : t("noVersions")}</option>}
            {list.map((v) => (
              <option key={v.id} value={v.id}>
                {label(v)}
              </option>
            ))}
          </select>
        )}
      </FieldShell>
      <div className="flex flex-wrap items-center gap-3">
        <WriteGate projectId={projectId}>
          <Button
            disabled={!version || start.isPending}
            data-testid="start-exam"
            onClick={() =>
              start.mutate(versionId, {
                onSuccess: (exam) => router.push(`/evaluations/runs/${exam.id}`),
                onError: report,
              })
            }
          >
            {t("start")}
          </Button>
        </WriteGate>
        <span className="text-sm text-muted-foreground" data-testid="start-version">
          {version ? label(version) : t("noVersions")}
        </span>
      </div>
    </div>
  );
}
