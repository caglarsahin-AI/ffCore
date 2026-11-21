"use client";

import { ThumbsDownIcon, ThumbsUpIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useVote } from "@/lib/api/chat-queries";
import type { ChatVote } from "@/lib/api/chat-queries";

// Helpful / not helpful on a stored answer (11-2): a thumb opens an optional note, Send posts the
// vote with it (one request per vote; a new vote replaces the earlier one, the audit keeps both).
// A platform mutation: read access sees the vote with the controls disabled and the reason.
export function MessageFeedback({ projectId, runId, stored }: { projectId: string; runId: string; stored: ChatVote | null }) {
  const t = useTranslations("Chat");
  const report = useReportError();
  const vote = useVote(projectId);
  const [chosen, setChosen] = useState<ChatVote | null>(null);
  const [note, setNote] = useState("");
  const [sent, setSent] = useState(false);
  const current = chosen ?? stored;

  function pick(value: ChatVote) {
    setChosen(value);
    setSent(false);
  }

  return (
    <div className="flex flex-col gap-2" data-testid="chat-feedback">
      <div className="flex items-center gap-1">
        <span className="sr-only">{t("voteLabel")}</span>
        <WriteGate projectId={projectId}>
          <Button type="button" variant="ghost" size="icon-sm" aria-label={t("voteUp")} aria-pressed={current === "correct"} disabled={vote.isPending} onClick={() => pick("correct")} data-testid="chat-vote-up">
            <ThumbsUpIcon aria-hidden className={current === "correct" ? "fill-current" : undefined} />
          </Button>
        </WriteGate>
        <WriteGate projectId={projectId}>
          <Button type="button" variant="ghost" size="icon-sm" aria-label={t("voteDown")} aria-pressed={current === "wrong"} disabled={vote.isPending} onClick={() => pick("wrong")} data-testid="chat-vote-down">
            <ThumbsDownIcon aria-hidden className={current === "wrong" ? "fill-current" : undefined} />
          </Button>
        </WriteGate>
      </div>
      {chosen !== null && !sent && (
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            vote.mutate({ runId, vote: chosen, note: note.trim() || null }, { onError: report, onSuccess: () => setSent(true) });
          }}
          noValidate
        >
          <label htmlFor={`chat-vote-note-${runId}`} className="text-xs text-muted-foreground">
            {t("voteNote")}
          </label>
          <Textarea id={`chat-vote-note-${runId}`} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} className="min-h-11 text-sm" data-testid="chat-vote-note" />
          <div>
            <Button type="submit" size="sm" variant="outline" disabled={vote.isPending} data-testid="chat-vote-send">
              {t("voteSend")}
            </Button>
          </div>
        </form>
      )}
      {sent && (
        <p className="text-xs text-muted-foreground" role="status" data-testid="chat-vote-thanks">
          {t("voteThanks")}
        </p>
      )}
    </div>
  );
}
