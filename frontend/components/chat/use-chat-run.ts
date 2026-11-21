"use client";

import { useEffect, useReducer, useRef, useState } from "react";

import { useDecideApproval } from "@/lib/api/approvals-queries";
import type { Decision } from "@/lib/api/approvals-queries";
import { ApiError } from "@/lib/api/client";
import { answerQuestion, reconnectRun, startRun, useRun } from "@/lib/api/runs-queries";
import { initialRunView, reduceRunView } from "@/lib/run-view";
import type { RunView } from "@/lib/run-view";
import { followRunStream } from "@/lib/sse";
import type { RunStreamEvent, StreamEnd, StreamState } from "@/lib/sse";

type Action = { type: "reset" } | { type: "event"; event: RunStreamEvent };

function reducer(view: RunView, action: Action): RunView {
  return action.type === "reset" ? initialRunView() : reduceRunView(view, action.event);
}

export type LiveTurn = {
  input: string | null; // null: a run resumed after a reload (its question is a stored message)
  startedIn: string | null; // the conversation open when it started (null: a new one)
  created: string | null; // the conversation the run belongs to, from its first event
};

// The live turn belongs on the screen of this conversation (before and after the URL switch).
export function turnShownIn(turn: LiveTurn | null, conversationId: string | null): boolean {
  return turn !== null && (turn.startedIn === conversationId || (turn.created !== null && turn.created === conversationId));
}

// One live run of the chat (11): start it (POST …/agents/{key}/runs, channel=chat) or resume one
// that is still going after a reload, follow its events with the 10b stream watchdog and
// Last-Event-ID reconnect (lib/sse.ts), and read the run with GET while the stream reconnects or
// is lost (FOLLOWUP-188 pattern). The stream ending (answer, error, wait or lost) calls `onSettle`
// so the stored messages are read again; the live turn is shown until they include the run.
// 11-2: a stream that ends waiting (approval_required, question) is not the end: the run is read
// every RUNS_POLL_MS (useRun) and, once the server says it moved on (someone else decided), the
// stream is followed again from the last event id. An own decision or answer reconnects at once
// (from the decision's `stream_after`). A failing read is shown, never a silent stop.
export function useChatRun({
  projectId,
  agentKey,
  onConversation,
  onSettle,
}: {
  projectId: string;
  agentKey: string;
  onConversation: (conversationId: string) => void;
  onSettle: () => void;
}) {
  const [view, dispatch] = useReducer(reducer, undefined, initialRunView);
  const [turn, setTurn] = useState<LiveTurn | null>(null);
  const [stream, setStream] = useState<StreamState | null>(null);
  const [ended, setEnded] = useState<StreamEnd | null>(null);
  const [startError, setStartError] = useState<ApiError | null>(null);
  const abort = useRef<AbortController | null>(null);
  const lastId = useRef<string | null>(null);
  const waitingSince = useRef(0);
  const decideApproval = useDecideApproval(projectId);
  const callbacks = useRef({ onConversation, onSettle });
  callbacks.current = { onConversation, onSettle };
  useEffect(() => () => abort.current?.abort(), []);

  const reading = view.runId !== null && (stream === "reconnecting" || (stream === null && ended === "lost"));
  const waitingPhase = view.phase === "waiting_approval" || view.phase === "waiting_user";
  const waiting = view.runId !== null && stream === null && ended !== "lost" && waitingPhase;
  const server = useRun(projectId, view.runId ?? "", { enabled: reading || waiting, pollWhileUnknown: true });
  const serverStatus = server.data?.status ?? null;
  // A lost stream whose run has ended on the server: the stored messages tell the rest.
  useEffect(() => {
    if (reading && serverStatus && !["queued", "running"].includes(serverStatus)) callbacks.current.onSettle();
  }, [reading, serverStatus]);

  // Waiting: a read made after the wait began says the run moved on: follow its stream again.
  const fresh = server.dataUpdatedAt > waitingSince.current;
  const movedOn = waiting && fresh && serverStatus !== null && serverStatus !== view.phase;
  const pollError = waiting && server.error ? server.error : null;
  useEffect(() => {
    if (movedOn && view.runId) {
      const runId = view.runId;
      void follow((signal) => reconnectRun(projectId, runId, lastId.current, signal), turn?.created ?? null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- follow/turn are read at the moment the run moves on
  }, [movedOn]);

  async function follow(open: (signal: AbortSignal) => Promise<Response>, known: string | null) {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setEnded(null);
    let conversation = known;
    try {
      const result = await followRunStream({
        open,
        reconnect: (runId, last, signal) => reconnectRun(projectId, runId, last, signal),
        onEvent: (event) => {
          if (event.id) lastId.current = event.id;
          const id = event.data.conversation_id;
          if (event.event === "progress" && conversation === null && typeof id === "string") {
            conversation = id;
            setTurn((current) => (current ? { ...current, created: id } : current));
            callbacks.current.onConversation(id);
          }
          dispatch({ type: "event", event });
        },
        onState: setStream,
        signal: controller.signal,
      });
      waitingSince.current = Date.now();
      setEnded(result.ended);
    } catch (error) {
      if (error instanceof ApiError) setStartError(error);
      else if (!controller.signal.aborted) setEnded("lost");
    } finally {
      if (abort.current === controller) {
        setStream(null);
        if (!controller.signal.aborted) callbacks.current.onSettle();
      }
    }
  }

  function send(input: string, conversationId: string | null) {
    dispatch({ type: "reset" });
    lastId.current = null;
    setStartError(null);
    setTurn({ input, startedIn: conversationId, created: conversationId });
    const body = conversationId ? { input, channel: "chat" as const, conversation_id: conversationId } : { input, channel: "chat" as const };
    void follow((signal) => startRun(projectId, agentKey, body, signal), conversationId);
  }

  // A run still going after a reload: replay its events from the start (no Last-Event-ID).
  function resume(runId: string, conversationId: string) {
    dispatch({ type: "reset" });
    setStartError(null);
    setTurn({ input: null, startedIn: conversationId, created: conversationId });
    lastId.current = null;
    void follow((signal) => reconnectRun(projectId, runId, null, signal), conversationId);
  }

  // An own approval decision (07): the run goes on from the decision's stream_after.
  async function decide(decision: Decision, note: string | null) {
    const runId = view.runId;
    const approvalId = view.approval?.approvalId;
    if (!runId || !approvalId) return;
    const decided = await decideApproval.mutateAsync({ id: approvalId, decision, note });
    void follow((signal) => reconnectRun(projectId, runId, decided.stream_after ?? lastId.current, signal), turn?.created ?? null);
  }

  // An own answer to the agent's question (06a /resume, FOLLOWUP-135).
  async function answer(text: string) {
    const runId = view.runId;
    if (!runId) return;
    await answerQuestion(projectId, runId, text);
    void follow((signal) => reconnectRun(projectId, runId, lastId.current, signal), turn?.created ?? null);
  }

  function stop() {
    abort.current?.abort();
    abort.current = null;
    setStream(null);
    setTurn(null);
    dispatch({ type: "reset" });
  }

  return {
    view,
    turn,
    stream,
    ended,
    startError,
    server,
    reading,
    waiting,
    pollError,
    deciding: decideApproval.isPending,
    send,
    resume,
    stop,
    decide,
    answer,
    busy: stream !== null,
  };
}
