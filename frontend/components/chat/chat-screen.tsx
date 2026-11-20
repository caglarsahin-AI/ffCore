"use client";

import { useQueryClient } from "@tanstack/react-query";
import { MenuIcon, PlusIcon, SendIcon, Trash2Icon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { SourceCards } from "@/components/chat/source-cards";
import type { CitedSource } from "@/components/chat/source-cards";
import { ToolCallCard } from "@/components/chat/tool-call-card";
import { turnShownIn, useChatRun } from "@/components/chat/use-chat-run";
import { QueryError } from "@/components/screen";
import { useReportError } from "@/components/use-report-error";
import { AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { chatKeys, useChatAgents, useConversations, useDeleteConversation, useMessages } from "@/lib/api/chat-queries";
import type { ChatAgent, ChatMessage, Conversation } from "@/lib/api/chat-queries";
import { errorMessageKey } from "@/lib/api/errors";
import { answerBadge, chatPath, pendingRun, settledRun } from "@/lib/chat-view";
import type { RunView } from "@/lib/run-view";

// The end user chat (11): conversations on the left (a sheet on small screens), messages in the
// middle, the composer below. Sending and deleting one's own conversation stay open in read-only
// access (brief 11, backend read-only exception); there is no admin menu here.
export function ChatScreen({ projectId, agentKey, conversationId }: { projectId: string; agentKey: string; conversationId: string | null }) {
  const t = useTranslations("Chat");
  const agents = useChatAgents(projectId);
  if (agents.isPending) return <p className="p-6 text-sm text-muted-foreground" role="status">{t("loading")}</p>;
  if (agents.isError) return <div className="p-6"><QueryError error={agents.error} /></div>;
  const agent = agents.data.find((a) => a.key === agentKey);
  if (!agent) {
    return (
      <div className="mx-auto flex max-w-xl flex-col gap-3 p-6" data-testid="chat-agent-unavailable">
        <h1 className="text-lg font-semibold">{t("unavailableTitle")}</h1>
        <p className="text-sm text-muted-foreground">{t("unavailableBody", { key: agentKey })}</p>
        <Link href={chatPath()} className="text-sm text-primary underline-offset-4 hover:underline">
          {t("backToAgents")}
        </Link>
      </div>
    );
  }
  return <AgentChat projectId={projectId} agent={agent} conversationId={conversationId} />;
}

function AgentChat({ projectId, agent, conversationId }: { projectId: string; agent: ChatAgent; conversationId: string | null }) {
  const t = useTranslations("Chat");
  const router = useRouter();
  const queries = useQueryClient();
  const [listOpen, setListOpen] = useState(false);
  const conversations = useConversations(projectId);
  const messages = useMessages(projectId, conversationId);
  const run = useChatRun({
    projectId,
    agentKey: agent.key,
    onConversation: (id) => router.replace(chatPath(agent.key, id)),
    onSettle: () => {
      void queries.invalidateQueries({ queryKey: ["projects", projectId, "chat", "messages"] });
      void queries.invalidateQueries({ queryKey: chatKeys.conversations(projectId) });
    },
  });
  const stored = messages.data ?? [];
  const live = turnShownIn(run.turn, conversationId);
  const liveSettled = live && run.view.runId !== null && settledRun(stored, run.view.runId);

  // Another conversation opened while a run streams: stop following it (the run goes on).
  const { stop, resume } = run;
  useEffect(() => {
    if (run.turn !== null && !turnShownIn(run.turn, conversationId)) stop();
  }, [conversationId, run.turn, stop]);
  // A run still going after a reload: follow it again, once per run.
  const resumed = useRef<Set<string>>(new Set());
  const pending = conversationId ? pendingRun(stored) : null;
  useEffect(() => {
    if (pending && conversationId && run.turn === null && !resumed.current.has(pending)) {
      resumed.current.add(pending);
      resume(pending, conversationId);
    }
  }, [pending, conversationId, run.turn, resume]);

  const own = (conversations.data ?? []).filter((c) => c.agent_id === agent.id);
  const list = (
    <ConversationList
      projectId={projectId}
      agentKey={agent.key}
      conversations={own}
      error={conversations.isError ? conversations.error : null}
      activeId={conversationId}
      onNavigate={() => setListOpen(false)}
    />
  );

  return (
    <div className="flex min-h-0 flex-1" data-testid="chat-screen">
      <aside className="hidden w-72 shrink-0 flex-col border-r md:flex" aria-label={t("conversations")}>
        {list}
      </aside>
      <Sheet open={listOpen} onOpenChange={setListOpen}>
        <SheetContent side="left" className="p-0">
          <SheetTitle className="sr-only">{t("conversations")}</SheetTitle>
          {list}
        </SheetContent>
      </Sheet>
      <section className="flex min-w-0 flex-1 flex-col" aria-label={agent.name}>
        <div className="flex items-center gap-2 border-b px-4 py-2">
          <Button variant="ghost" size="icon-sm" className="md:hidden" onClick={() => setListOpen(true)} aria-label={t("openConversations")} data-testid="chat-open-list">
            <MenuIcon aria-hidden />
          </Button>
          <h1 className="truncate font-medium">{agent.name}</h1>
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-4" aria-live="polite">
          {conversationId === null && !live && <Welcome agent={agent} />}
          {conversationId !== null && messages.isPending && <p className="text-sm text-muted-foreground" role="status">{t("loading")}</p>}
          {messages.isError && <QueryError error={messages.error} />}
          {stored.map((message) => (
            <StoredMessage key={message.id} projectId={projectId} message={message} stored={stored} hideFailure={live && !liveSettled && message.run_id === run.view.runId} />
          ))}
          {live && !liveSettled && (
            <LiveTurn
              projectId={projectId}
              input={stored.some((m) => m.role === "user" && m.run_id === run.view.runId) ? null : run.turn!.input}
              view={run.view}
              stream={run.stream}
              ended={run.ended}
              startError={run.startError?.code ?? null}
              serverStatus={run.reading ? (run.server.data?.status ?? null) : null}
            />
          )}
        </div>
        <Composer busy={run.busy} onSend={(text) => run.send(text, conversationId)} />
      </section>
    </div>
  );
}

function Welcome({ agent }: { agent: ChatAgent }) {
  const t = useTranslations("Chat");
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-2 py-8 text-center" data-testid="chat-welcome">
      <p className="text-lg font-semibold">{t("welcomeTitle", { name: agent.name })}</p>
      {agent.description && <p className="text-sm text-muted-foreground">{agent.description}</p>}
    </div>
  );
}

function Bubble({ role, children, testId = "chat-message" }: { role: "user" | "assistant"; children: React.ReactNode; testId?: string }) {
  const user = role === "user";
  return (
    <div className={`flex ${user ? "justify-end" : "justify-start"}`} data-testid={testId} data-role={role}>
      <div className={`flex max-w-[85%] flex-col gap-2 rounded-2xl px-4 py-2 text-sm ${user ? "bg-primary text-primary-foreground" : "border bg-card text-card-foreground"}`}>
        {children}
      </div>
    </div>
  );
}

function StoredMessage({ projectId, message, stored, hideFailure }: { projectId: string; message: ChatMessage; stored: ChatMessage[]; hideFailure: boolean }) {
  const t = useTranslations("Chat");
  if (message.role === "user") {
    const answered = stored.some((m) => m.role === "assistant" && m.run_id === message.run_id);
    const failed = !answered && !hideFailure && message.run_status !== null && ["failed", "cancelled", "abandoned"].includes(message.run_status);
    return (
      <>
        <Bubble role="user">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </Bubble>
        {failed && (
          <p className="text-sm text-destructive" role="alert" data-testid="chat-run-error">
            {t("runFailed", { code: message.error_code ?? message.run_status ?? "" })}
          </p>
        )}
      </>
    );
  }
  const badge = answerBadge(message);
  return (
    <Bubble role="assistant">
      {badge && (
        <Badge variant={badge === "declined" ? "outline" : "secondary"} className="self-start" data-testid="chat-badge" data-kind={badge}>
          {t(`badges.${badge}`)}
        </Badge>
      )}
      <p className="whitespace-pre-wrap" data-testid="chat-answer">
        {message.content}
      </p>
      <SourceCards sources={(message.sources ?? []) as CitedSource[]} variant="chat" projectId={projectId} runId={message.run_id} />
    </Bubble>
  );
}

function LiveTurn({
  projectId,
  input,
  view,
  stream,
  ended,
  startError,
  serverStatus,
}: {
  projectId: string;
  input: string | null;
  view: RunView;
  stream: string | null;
  ended: string | null;
  startError: string | null;
  serverStatus: string | null;
}) {
  const t = useTranslations("Chat");
  const tErrors = useTranslations("Errors");
  const status =
    stream === "reconnecting"
      ? t("reconnecting")
      : ended === "lost"
        ? t("lost")
        : view.phase === "waiting_approval" || view.phase === "waiting_user" || view.phase === "starting" || view.phase === "running"
          ? t(`phases.${view.phase}`)
          : null;
  return (
    <>
      {input !== null && (
        <Bubble role="user">
          <p className="whitespace-pre-wrap">{input}</p>
        </Bubble>
      )}
      {startError ? (
        <p className="text-sm text-destructive" role="alert" data-testid="chat-start-error">
          {t("startFailed", { message: tErrors(errorMessageKey(startError)), code: startError })}
        </p>
      ) : (
        <Bubble role="assistant" testId="chat-live">
          {status && (
            <p className="text-xs text-muted-foreground" role="status" data-testid="chat-status" data-phase={view.phase}>
              {status}
            </p>
          )}
          {serverStatus && <p className="text-xs text-muted-foreground" data-testid="chat-server-status">{t("serverStatus", { status: serverStatus })}</p>}
          {view.tools.map((tool) => (
            <ToolCallCard key={tool.id} tool={tool} variant="chat" />
          ))}
          {view.answer && (
            <p className="whitespace-pre-wrap" data-testid="chat-live-answer">
              {view.answer}
            </p>
          )}
          {view.phase === "waiting_user" && view.question && <p className="font-medium" data-testid="chat-question">{view.question}</p>}
          <SourceCards sources={view.sources as CitedSource[]} variant="chat" projectId={projectId} runId={view.runId} />
          {view.error && (
            <p className="text-sm text-destructive" role="alert" data-testid="chat-run-error">
              {t("runFailed", { code: view.error.code })}
            </p>
          )}
        </Bubble>
      )}
    </>
  );
}

function Composer({ busy, onSend }: { busy: boolean; onSend: (text: string) => void }) {
  const t = useTranslations("Chat");
  const [text, setText] = useState("");
  function submit(event?: React.FormEvent) {
    event?.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    onSend(value);
    setText("");
  }
  return (
    <form className="flex items-end gap-2 border-t p-3" onSubmit={submit} noValidate>
      <label htmlFor="chat-input" className="sr-only">
        {t("inputLabel")}
      </label>
      <Textarea
        id="chat-input"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) submit(e);
        }}
        placeholder={t("inputPlaceholder")}
        className="max-h-40 min-h-11 flex-1 resize-none"
        data-testid="chat-input"
      />
      <Button type="submit" disabled={busy || !text.trim()} aria-label={t("send")} data-testid="chat-send">
        <SendIcon aria-hidden />
      </Button>
    </form>
  );
}

function ConversationList({
  projectId,
  agentKey,
  conversations,
  error,
  activeId,
  onNavigate,
}: {
  projectId: string;
  agentKey: string;
  conversations: Conversation[];
  error: Error | null;
  activeId: string | null;
  onNavigate: () => void;
}) {
  const t = useTranslations("Chat");
  const format = useFormatter();
  const router = useRouter();
  const report = useReportError();
  const remove = useDeleteConversation(projectId);
  const [confirming, setConfirming] = useState<Conversation | null>(null);

  async function onDelete() {
    const target = confirming;
    setConfirming(null);
    if (!target) return;
    try {
      await remove.mutateAsync(target.id);
      if (target.id === activeId) router.replace(chatPath(agentKey));
    } catch (e) {
      report(e);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-testid="chat-conversations">
      <div className="p-3">
        <Link href={chatPath(agentKey)} onClick={onNavigate} className="inline-flex w-full items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted" data-testid="chat-new">
          <PlusIcon className="size-4" aria-hidden />
          {t("newConversation")}
        </Link>
      </div>
      {error ? <div className="px-3"><QueryError error={error} compact /></div> : null}
      {!error && conversations.length === 0 && <p className="px-3 text-sm text-muted-foreground">{t("noConversations")}</p>}
      <ul className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-2 pb-3">
        {conversations.map((c) => (
          <li key={c.id} className={`group flex items-center gap-1 rounded-md ${c.id === activeId ? "bg-muted" : "hover:bg-muted/60"}`}>
            <Link href={chatPath(agentKey, c.id)} onClick={onNavigate} className="flex min-w-0 flex-1 flex-col px-2 py-1.5" aria-current={c.id === activeId ? "page" : undefined} data-testid="chat-conversation">
              <span className="truncate text-sm">{c.title || t("untitled")}</span>
              <span className="text-xs text-muted-foreground">{format.dateTime(new Date(c.last_message_at), { dateStyle: "medium", timeStyle: "short" })}</span>
            </Link>
            <Button variant="ghost" size="icon-sm" onClick={() => setConfirming(c)} aria-label={t("deleteConversation", { title: c.title })} data-testid="chat-conversation-delete">
              <Trash2Icon aria-hidden />
            </Button>
          </li>
        ))}
      </ul>
      <AlertDialog open={confirming !== null} onOpenChange={(next) => !next && setConfirming(null)}>
        <AlertDialogContent data-testid="chat-delete-dialog">
          <AlertDialogTitle>{t("deleteTitle")}</AlertDialogTitle>
          <AlertDialogDescription>{t("deleteBody")}</AlertDialogDescription>
          <AlertDialogFooter>
            <Button variant="outline" onClick={() => setConfirming(null)} autoFocus data-testid="chat-delete-cancel">
              {t("cancel")}
            </Button>
            <Button variant="destructive" onClick={() => void onDelete()} data-testid="chat-delete-confirm">
              {t("delete")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
