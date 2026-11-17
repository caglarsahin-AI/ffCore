"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { EvalItemsTable } from "@/components/eval/eval-items-table";
import { EvalSummaryView } from "@/components/eval/eval-summary-view";
import { QueryError, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { EVAL_RUN_STATUSES, evalKeys, isLiveEvalRun, openEvalStream, useCancelEvalRun, useEvalRun } from "@/lib/api/eval-queries";
import type { EvalRun, EvalRunStatus } from "@/lib/api/eval-queries";
import { followEvalStream, newestState } from "@/lib/eval-stream";
import type { EvalProgress } from "@/lib/eval-stream";
import { isUnauthenticated } from "@/lib/login-redirect";

export default function ExamPage() {
  const { projectId } = useSession();
  const { evalRunId } = useParams<{ evalRunId: string }>();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <ExamDetail key={`${projectId}:${evalRunId}`} projectId={projectId} evalRunId={evalRunId} />;
}

// "streaming": following the stream; "reconnecting": an attempt ended without done (dropped or
// silent for STALL_MS), the stream is being reopened and meanwhile the exam is read with GET every
// few seconds (K-10C1-0007); "lost": it could not be reopened, GET goes on; "done": the stream said
// the exam ended; "ended": the exam had ended before the page opened.
type StreamState = "streaming" | "reconnecting" | "lost" | "done" | "ended";

function ExamDetail({ projectId, evalRunId }: { projectId: string; evalRunId: string }) {
  const t = useTranslations("Evaluations");
  const tState = useTranslations("State");
  const [stream, setStream] = useState<StreamState | null>(null);
  const query = useEvalRun(projectId, evalRunId, stream === "reconnecting" || stream === "lost");
  if (query.isPending || (query.isError && isUnauthenticated(query.error))) return <p className="text-muted-foreground">{tState("loading")}</p>;
  // A failed re-read keeps the exam on screen (and the stream followed) with the error above it;
  // only a first read that failed has nothing to show.
  if (query.isError && !query.data) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink href="/evaluations" label={t("back")} />
        <QueryError error={query.error} />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4">
      {query.isError && <QueryError error={query.error} />}
      <Loaded projectId={projectId} run={query.data} runAt={query.dataUpdatedAt} stream={stream} setStream={setStream} />
    </div>
  );
}

function Loaded({ projectId, run, runAt, stream, setStream }: { projectId: string; run: EvalRun; runAt: number; stream: StreamState | null; setStream: (s: StreamState) => void }) {
  const t = useTranslations("Evaluations.exam");
  const tStatus = useTranslations("Evaluations.statuses");
  const tBack = useTranslations("Evaluations");
  const format = useFormatter();
  const client = useQueryClient();
  const report = useReportError();
  const cancel = useCancelEvalRun(projectId);
  // The last progress from the stream and when it arrived (compared with GET's dataUpdatedAt).
  const [heard, setHeard] = useState<{ progress: EvalProgress; at: number } | null>(null);
  const setProgress = (progress: EvalProgress) => setHeard({ progress, at: Date.now() });
  const live = isLiveEvalRun(run.status);

  // Follow the stream once, from the first render of a live exam; at its end the exam is read again
  // (the summary comes from GET, the stream carries only counts).
  useEffect(() => {
    if (!live) {
      setStream("ended");
      return;
    }
    const controller = new AbortController();
    setStream("streaming");
    void followEvalStream({
      open: (signal) => openEvalStream(projectId, run.id, signal),
      onProgress: setProgress,
      onDone: (done) => {
        setProgress(done);
        void client.invalidateQueries({ queryKey: evalKeys.run(projectId, run.id) });
      },
      // An event name the console does not know is noted and skipped (K-10C1-0002).
      onUnknown: (name) => console.warn(`eval stream: unknown event "${name}" ignored`),
      // Read the exam with GET at once and every few seconds until the stream speaks again.
      onReconnecting: () => {
        setStream("reconnecting");
        void client.invalidateQueries({ queryKey: evalKeys.run(projectId, run.id) });
      },
      onResumed: () => setStream("streaming"),
      signal: controller.signal,
    }).then((end) => {
      if (end === "done") setStream("done");
      if (end === "lost") setStream("lost");
    });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one stream per page, started once
  }, []);

  // Status and counts from whichever came last: the stream's progress or the GET read.
  const { status, items, scored } = newestState(run, runAt, heard?.progress ?? null, heard?.at ?? 0);
  const knownStatus = (EVAL_RUN_STATUSES as readonly string[]).includes(status) ? (status as EvalRunStatus) : null;
  const when = (iso: string | null) => (iso ? format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "medium" }) : t("none"));

  const action = live ? (
    <WriteGate projectId={projectId}>
      <Button variant="outline" onClick={() => cancel.mutate(run.id, { onError: report })} disabled={cancel.isPending} data-testid="eval-cancel">
        {t("cancel")}
      </Button>
    </WriteGate>
  ) : undefined;

  return (
    <div className="flex flex-col gap-4">
      <BackLink href={`/evaluations/${run.suite_id}`} label={tBack("backToSuite")} />
      <Screen title={t("title")} description={t("description")} action={action}>
        <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <Fact label={t("status")}>
            <Badge variant={status === "failed" ? "destructive" : "secondary"} data-testid="eval-status">
              {knownStatus ? tStatus(knownStatus) : <span className="font-mono">{status}</span>}
            </Badge>
          </Fact>
          <Fact label={t("progress")}>
            <span data-testid="eval-progress">{t("progressValue", { scored, items })}</span>
          </Fact>
          <Fact label={t("live")}>
            <span data-testid="eval-stream-state" data-state={stream ?? "ended"}>
              {t(`stream.${stream ?? "ended"}`)}
            </span>
          </Fact>
          <Fact label={t("langfuseRun")}>
            <span className="font-mono text-xs break-all">{run.langfuse_run_name}</span>
          </Fact>
          <Fact label={t("version")}>
            <span className="font-mono text-xs break-all">{run.agent_version_id}</span>
          </Fact>
          <Fact label={t("started")}>{when(run.started_at)}</Fact>
          <Fact label={t("ended")}>{when(run.ended_at)}</Fact>
        </dl>
        {live && items > 0 && (
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted" role="progressbar" aria-label={t("progress")} aria-valuemin={0} aria-valuemax={items} aria-valuenow={scored}>
            <div className="h-full bg-primary transition-all" style={{ width: `${Math.min(100, (scored / items) * 100)}%` }} />
          </div>
        )}
        {stream === "reconnecting" && <p className="text-sm text-muted-foreground">{t("streamReconnectingHint")}</p>}
        {stream === "lost" && <p className="text-sm text-muted-foreground">{t("streamLostHint")}</p>}
        <EvalSummaryView run={run} />
        <EvalItemsTable projectId={projectId} run={run} />
      </Screen>
    </div>
  );
}

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline">
      <ArrowLeftIcon className="size-4" />
      {label}
    </Link>
  );
}
