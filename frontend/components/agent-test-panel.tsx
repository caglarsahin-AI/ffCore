"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useReducer, useRef, useState } from "react";

import { TextField } from "@/components/form-parts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import type { AgentDefinition } from "@/lib/agent-definition";
import { useDecideApproval } from "@/lib/api/approvals-queries";
import type { Decision } from "@/lib/api/approvals-queries";
import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";
import { answerQuestion, reconnectRun, startRun, useCancelRun } from "@/lib/api/runs-queries";
import { initialRunView, reduceRunView } from "@/lib/run-view";
import type { RunView } from "@/lib/run-view";
import { followRunStream } from "@/lib/sse";
import type { RunStreamEvent, StreamEnd, StreamState } from "@/lib/sse";

type Action = { type: "reset" } | { type: "event"; event: RunStreamEvent };

function reducer(view: RunView, action: Action): RunView {
  return action.type === "reset" ? initialRunView() : reduceRunView(view, action.event);
}

// Test panel (brief 10 step 7): one test run of the version being edited (channel=test), its
// event stream as it arrives, an inline approval that goes to the 07 decision endpoint (D1) and
// an answer box for ask_user. A dropped stream reconnects with Last-Event-ID; one that cannot be
// resumed says so (the run may still be going; see Runs).
export function AgentTestPanel({
  projectId,
  agentKey,
  version,
  definition,
  dirty,
}: {
  projectId: string;
  agentKey: string;
  version: number;
  definition: AgentDefinition;
  dirty: boolean;
}) {
  const t = useTranslations("TestPanel");
  const tErrors = useTranslations("Errors");
  const report = useReportError();
  const cancel = useCancelRun(projectId);
  const decide = useDecideApproval(projectId);
  const [view, dispatch] = useReducer(reducer, undefined, initialRunView);
  const [input, setInput] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [stream, setStream] = useState<StreamState | null>(null);
  const [ended, setEnded] = useState<StreamEnd | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [answer, setAnswer] = useState("");
  const lastId = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);

  const busy = stream !== null;
  const variables = definition.variables ?? [];

  async function follow(open: (signal: AbortSignal) => Promise<Response>) {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setEnded(null);
    try {
      const result = await followRunStream({
        open: () => open(controller.signal),
        reconnect: (runId, last) => reconnectRun(projectId, runId, last, controller.signal),
        onEvent: (event) => {
          if (event.id) lastId.current = event.id;
          dispatch({ type: "event", event });
        },
        onState: setStream,
        signal: controller.signal,
      });
      setEnded(result.ended);
    } catch (error) {
      if (error instanceof ApiError) setStartError(t("startFailed", { message: tErrors(errorMessageKey(error.code)), code: error.code }));
      else if (!controller.signal.aborted) setEnded("lost");
    } finally {
      if (abort.current === controller) setStream(null);
    }
  }

  function onStart(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!input.trim()) return;
    dispatch({ type: "reset" });
    setStartError(null);
    lastId.current = null;
    const given = Object.fromEntries(Object.entries(values).filter(([, v]) => v !== ""));
    void follow((signal) => startRun(projectId, agentKey, { input: input.trim(), variables: given, channel: "test", version }, signal));
  }

  async function onDecide(decision: Decision) {
    const runId = view.runId;
    const approvalId = view.approval?.approvalId;
    if (!runId || !approvalId) return;
    try {
      const decided = await decide.mutateAsync({ id: approvalId, decision, note: note.trim() || null });
      setNote("");
      void follow((signal) => reconnectRun(projectId, runId, decided.stream_after ?? lastId.current, signal));
    } catch (error) {
      report(error);
    }
  }

  async function onAnswer(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const runId = view.runId;
    if (!runId || !answer.trim()) return;
    try {
      await answerQuestion(projectId, runId, answer.trim());
      setAnswer("");
      void follow((signal) => reconnectRun(projectId, runId, lastId.current, signal));
    } catch (error) {
      report(error);
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-xl border bg-card p-4" aria-label={t("title")} data-testid="test-panel">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-medium">{t("title")}</h2>
        <Badge variant="outline">{t("version", { version })}</Badge>
      </div>
      {dirty && <p className="text-sm text-muted-foreground">{t("unsavedNote")}</p>}
      <form className="flex flex-col gap-3" onSubmit={onStart} noValidate>
        {variables.map((variable) => (
          <TextField
            key={variable.key}
            id={`test-var-${variable.key}`}
            label={variable.label || variable.key}
            hint={t("variableDefault", { value: variable.default || t("empty") })}
            value={values[variable.key] ?? ""}
            onChange={(value) => setValues((current) => ({ ...current, [variable.key]: value }))}
          />
        ))}
        <label htmlFor="test-input" className="text-sm font-medium">
          {t("message")}
        </label>
        <Textarea id="test-input" value={input} onChange={(e) => setInput(e.target.value)} className="min-h-20" data-testid="test-input" />
        <div className="flex gap-2">
          <WriteGate projectId={projectId}>
            <Button type="submit" disabled={busy || !input.trim()} data-testid="test-send">
              {t("send")}
            </Button>
          </WriteGate>
          {view.runId && (view.phase === "running" || view.phase === "waiting_approval" || view.phase === "waiting_user") && (
            <Button type="button" variant="outline" onClick={() => cancel.mutate(view.runId!, { onError: report })} data-testid="test-cancel">
              {t("cancel")}
            </Button>
          )}
        </div>
      </form>
      {startError && (
        <p className="text-sm text-destructive" role="alert" data-testid="test-start-error">
          {startError}
        </p>
      )}
      <StreamStatus view={view} stream={stream} ended={ended} />
      {view.notes.map((n, i) => (
        <p key={i} className="text-xs text-muted-foreground" data-testid="test-note">
          {t("note", { detail: JSON.stringify(n) })}
        </p>
      ))}
      {view.fallback && (
        <p className="text-sm text-muted-foreground" data-testid="test-fallback">
          {t("fallback", { detail: JSON.stringify(view.fallback) })}
        </p>
      )}
      {view.tools.map((tool) => (
        <div key={tool.id} className="flex flex-col gap-1 rounded-lg border p-3 text-sm" data-testid="test-tool-card">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono">{tool.name}</span>
            {tool.result === null ? (
              <Badge variant="outline">{t("toolPending")}</Badge>
            ) : (
              <Badge variant={tool.result.isError ? "destructive" : "secondary"}>{tool.result.isError ? t("toolError", { code: tool.result.errorCode ?? t("noCode") }) : t("toolDone")}</Badge>
            )}
            {tool.result?.truncated && <span className="text-muted-foreground">{t("toolTruncated", { chars: tool.result.chars ?? 0 })}</span>}
          </div>
          <pre tabIndex={0} className="overflow-auto rounded bg-muted p-2 text-xs" data-testid="test-tool-arguments">
            {JSON.stringify(tool.arguments, null, 2)}
          </pre>
        </div>
      ))}
      {view.approval && (
        <div className="flex flex-col gap-3 rounded-lg border border-primary p-3" role="group" aria-label={t("approvalTitle")} data-testid="test-approval">
          <p className="text-sm font-medium">{t("approvalTitle")}</p>
          <p className="font-mono text-sm">{view.approval.action}</p>
          <pre tabIndex={0} className="overflow-auto rounded bg-muted p-2 text-xs">{JSON.stringify(view.approval.arguments, null, 2)}</pre>
          {view.approval.assignTo && <p className="text-sm text-muted-foreground">{t("approvalRole", { role: view.approval.assignTo })}</p>}
          {view.approval.approvalId ? (
            <>
              <TextField id="test-approval-note" label={t("approvalNote")} value={note} onChange={setNote} />
              <div className="flex gap-2">
                <WriteGate projectId={projectId}>
                  <Button type="button" onClick={() => void onDecide("approve")} disabled={decide.isPending} data-testid="test-approve">
                    {t("approve")}
                  </Button>
                </WriteGate>
                <WriteGate projectId={projectId}>
                  <Button type="button" variant="outline" onClick={() => void onDecide("reject")} disabled={decide.isPending} data-testid="test-reject">
                    {t("reject")}
                  </Button>
                </WriteGate>
              </div>
            </>
          ) : (
            <p className="text-sm text-destructive" data-testid="test-approval-no-id">
              {t("approvalNoId")}{" "}
              <Link href="/approvals" className="underline">
                {t("openApprovals")}
              </Link>
            </p>
          )}
        </div>
      )}
      {view.phase === "waiting_user" && (
        <form className="flex flex-col gap-2 rounded-lg border border-primary p-3" onSubmit={onAnswer} noValidate data-testid="test-question">
          <p className="text-sm font-medium">{view.question}</p>
          <TextField id="test-answer" label={t("answer")} value={answer} onChange={setAnswer} />
          <div>
            <Button type="submit" disabled={!answer.trim()} data-testid="test-answer-send">
              {t("sendAnswer")}
            </Button>
          </div>
        </form>
      )}
      {view.answer && (
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium">{t("answerTitle")}</span>
          <p className="text-sm whitespace-pre-wrap" data-testid="test-answer-text">
            {view.answer}
          </p>
        </div>
      )}
      {view.sources.length > 0 && (
        <div className="flex flex-col gap-2" data-testid="test-sources">
          <span className="text-sm font-medium">{t("sources")}</span>
          {view.sources.map((source, i) => (
            <div key={source.chunk_id ?? i} className="rounded-lg border p-2 text-sm" data-testid="test-source-card">
              <p className="font-medium">{t("sourceTitle", { n: source.n ?? i + 1, name: source.document_name ?? source.kb_key ?? "" })}</p>
              <p className="text-muted-foreground">
                {source.page != null && t("sourcePage", { page: source.page })} {source.breadcrumb}
              </p>
            </div>
          ))}
        </div>
      )}
      {view.error && (
        <p className="text-sm text-destructive" role="alert" data-testid="test-error">
          {t("runError", { code: view.error.code, message: view.error.message ?? "" })}
        </p>
      )}
      {view.runId && (
        <Link href={`/runs/${view.runId}`} className="text-sm text-primary underline-offset-4 hover:underline" data-testid="test-run-link">
          {t("openRun")}
        </Link>
      )}
    </section>
  );
}

function StreamStatus({ view, stream, ended }: { view: RunView; stream: StreamState | null; ended: StreamEnd | null }) {
  const t = useTranslations("TestPanel");
  let text: string | null = null;
  if (stream === "reconnecting") text = t("reconnecting");
  else if (stream === "streaming") text = t(`phases.${view.phase}`);
  else if (ended === "lost") text = t("lost");
  else if (view.phase !== "starting") text = t(`phases.${view.phase}`);
  if (!text) return null;
  return (
    <p className="text-sm text-muted-foreground" role="status" data-testid="test-status" data-phase={view.phase} data-stream={stream ?? ended ?? ""}>
      {text}
    </p>
  );
}
