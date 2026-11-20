"use client";

import { useEffect, useReducer, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import { reconnectRun, startRun, useRun } from "@/lib/api/runs-queries";
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
  const callbacks = useRef({ onConversation, onSettle });
  callbacks.current = { onConversation, onSettle };
  useEffect(() => () => abort.current?.abort(), []);

  const reading = view.runId !== null && (stream === "reconnecting" || (stream === null && ended === "lost"));
  const server = useRun(projectId, view.runId ?? "", { enabled: reading, pollWhileUnknown: true });
  const serverStatus = server.data?.status ?? null;
  // A lost stream whose run has ended on the server: the stored messages tell the rest.
  useEffect(() => {
    if (reading && serverStatus && !["queued", "running"].includes(serverStatus)) callbacks.current.onSettle();
  }, [reading, serverStatus]);

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
    void follow((signal) => reconnectRun(projectId, runId, null, signal), conversationId);
  }

  function stop() {
    abort.current?.abort();
    abort.current = null;
    setStream(null);
    setTurn(null);
    dispatch({ type: "reset" });
  }

  return { view, turn, stream, ended, startError, server, reading, send, resume, stop, busy: stream !== null };
}
