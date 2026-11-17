"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { FromRunForm } from "@/components/eval/from-run-form";

import { RunFeedback } from "@/components/run-feedback";
import { RunTimeline } from "@/components/run-timeline";
import { Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { errorMessageKey } from "@/lib/api/errors";
import { isLiveRun, isRunGone, readErrorCode, useCancelRun, useRun } from "@/lib/api/runs-queries";
import type { Run } from "@/lib/api/runs-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

export default function RunPage() {
  const { projectId } = useSession();
  const { runId } = useParams<{ runId: string }>();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <RunDetail key={`${projectId}:${runId}`} projectId={projectId} runId={runId} />;
}

// FOLLOWUP-192: a failed first read keeps reading (pollWhileUnknown) and says why; a run that is
// gone (404/410) stops; a failed refresh of a live run keeps the last answer and says it is stale.
function RunDetail({ projectId, runId }: { projectId: string; runId: string }) {
  const t = useTranslations("Runs");
  const tState = useTranslations("State");
  const query = useRun(projectId, runId, { pollWhileUnknown: true });
  if (query.isPending || (query.isError && isUnauthenticated(query.error))) {
    return <p className="text-muted-foreground">{tState("loading")}</p>;
  }
  const failure = query.isError ? <ReadError error={query.error} stale={query.data !== undefined} /> : null;
  if (query.data === undefined) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink label={t("back")} />
        {failure}
      </div>
    );
  }
  return <Loaded projectId={projectId} run={query.data} failure={failure} />;
}

function ReadError({ error, stale }: { error: Error; stale: boolean }) {
  const t = useTranslations("Runs");
  const tErrors = useTranslations("Errors");
  const code = readErrorCode(error);
  const key = isRunGone(error) ? "readGone" : stale ? "readStale" : "readRetrying";
  return (
    <p className="text-sm text-destructive" role="alert" data-testid="run-read-error" data-code={code}>
      {t(key, { message: tErrors(errorMessageKey(code)), code })}
    </p>
  );
}

function Loaded({ projectId, run, failure }: { projectId: string; run: Run; failure: React.ReactNode }) {
  const t = useTranslations("Runs");
  const format = useFormatter();
  const cancel = useCancelRun(projectId);
  const report = useReportError();
  const live = isLiveRun(run.status);
  const when = (iso: string | null) => (iso ? format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "medium" }) : t("none"));
  const ms = (value: number | null) => (value === null ? t("none") : t("ms", { value }));

  const action = live ? (
    <WriteGate projectId={projectId}>
      <Button variant="outline" onClick={() => cancel.mutate(run.id, { onError: report })} disabled={cancel.isPending} data-testid="run-cancel">
        {t("cancel")}
      </Button>
    </WriteGate>
  ) : undefined;

  return (
    <div className="flex flex-col gap-4">
      <BackLink label={t("back")} />
      {failure}
      <Screen title={t("runTitle")} description={run.input} action={action}>
        <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4" data-testid="run-summary">
          <Fact label={t("status")} value={<Badge variant={run.status === "failed" ? "destructive" : "secondary"} data-testid="run-detail-status">{t(`statuses.${run.status}`)}</Badge>} />
          <Fact label={t("channel")} value={t(`channels.${run.channel}`)} />
          <Fact label={t("outcome")} value={run.outcome_label ? t(`outcomes.${run.outcome_label}`) : t("none")} />
          <Fact label={t("errorCode")} value={<span className="font-mono">{run.error_code ?? t("none")}</span>} />
          <Fact label={t("started")} value={when(run.started_at)} />
          <Fact label={t("ended")} value={when(run.ended_at)} />
          <Fact label={t("tokens")} value={t("tokensValue", { input: run.tokens_in ?? 0, output: run.tokens_out ?? 0 })} />
          <Fact label={t("slowest")} value={run.slowest_step ?? t("none")} />
          <Fact label={t("modelTime")} value={ms(run.model_ms)} />
          <Fact label={t("toolTime")} value={ms(run.tool_ms)} />
          <Fact label={t("retrievalTime")} value={ms(run.retrieval_ms)} />
          <Fact label={t("queueWait")} value={ms(run.queue_wait_ms)} />
          {/* Varsayım 4: no Langfuse address is configured in the console, so the trace id is shown, not linked. */}
          <Fact label={t("trace")} value={<span className="font-mono break-all" data-testid="run-trace-id">{run.langfuse_trace_id ?? t("none")}</span>} />
        </dl>
        {run.output && (
          <section className="flex flex-col gap-1">
            <h2 className="text-lg font-medium">{t("output")}</h2>
            {run.partial && <p className="text-sm text-muted-foreground">{t("partial")}</p>}
            <p className="text-sm whitespace-pre-wrap" data-testid="run-output">
              {run.output}
            </p>
          </section>
        )}
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-medium">{t("feedbackTitle")}</h2>
          <RunFeedback projectId={projectId} run={run} />
        </section>
        <AddToExam projectId={projectId} run={run} />
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-medium">{t("timeline")}</h2>
          <RunTimeline projectId={projectId} runId={run.id} live={live} />
        </section>
      </Screen>
    </div>
  );
}

// "Add to exam" (09-2 from-run): only a completed run can become an exam item. Opening the form
// reads only; saving goes through WriteGate inside the form.
function AddToExam({ projectId, run }: { projectId: string; run: Run }) {
  const t = useTranslations("Evaluations.fromRun");
  const [open, setOpen] = useState(false);
  return (
    <section className="flex flex-col gap-2" data-testid="add-to-exam">
      <h2 className="text-lg font-medium">{t("title")}</h2>
      {run.status !== "completed" ? (
        <p className="text-sm text-muted-foreground">{t("onlyCompleted")}</p>
      ) : open ? (
        <FromRunForm projectId={projectId} runId={run.id} />
      ) : (
        <div>
          <Button variant="outline" onClick={() => setOpen(true)} data-testid="from-run-open">
            {t("open")}
          </Button>
        </div>
      )}
    </section>
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
    <Link href="/runs" className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline">
      <ArrowLeftIcon className="size-4" />
      {label}
    </Link>
  );
}
