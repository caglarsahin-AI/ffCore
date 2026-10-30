"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { TextField } from "@/components/form-parts";
import { useAccess } from "@/components/session-provider";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useGiveFeedback } from "@/lib/api/runs-queries";
import type { FeedbackVote, Run } from "@/lib/api/runs-queries";

const VOTES = ["correct", "partial", "wrong"] as const satisfies readonly FeedbackVote[];
const RADIO = "size-4 accent-primary disabled:opacity-50";

// Expert feedback (F9 PoC-lite): a vote and a note on a completed run, with edit access (06a
// POST /runs/{id}/feedback; stored on the answer and sent to Langfuse as expert_feedback).
export function RunFeedback({ projectId, run }: { projectId: string; run: Run }) {
  const t = useTranslations("Runs");
  const tState = useTranslations("State");
  const { canWrite } = useAccess(projectId);
  const give = useGiveFeedback(projectId);
  const report = useReportError();
  const given = (run.feedback ?? null) as { vote?: FeedbackVote; note?: string | null } | null;
  const [vote, setVote] = useState<FeedbackVote | null>(given?.vote ?? null);
  const [note, setNote] = useState(given?.note ?? "");

  if (run.status !== "completed") {
    return <p className="text-sm text-muted-foreground">{t("feedbackOnlyCompleted")}</p>;
  }

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!vote) return;
    give.mutate({ runId: run.id, vote, note: note.trim() || null }, { onSuccess: () => toast.success(tState("saved")), onError: report });
  }

  return (
    <form className="flex flex-col gap-3" onSubmit={onSubmit} noValidate data-testid="run-feedback">
      {given?.vote && (
        <p className="text-sm" data-testid="run-feedback-given">
          {t("feedbackGivenAs", { vote: t(`votes.${given.vote}`) })}
        </p>
      )}
      <fieldset disabled={!canWrite} className="flex flex-col gap-3">
        <legend className="mb-1 text-sm font-medium">{t("vote")}</legend>
        <div className="flex flex-wrap gap-6">
          {VOTES.map((value) => (
            <label key={value} className="flex items-center gap-2 text-sm">
              <input type="radio" name="vote" className={RADIO} checked={vote === value} onChange={() => setVote(value)} data-testid={`vote-${value}`} />
              {t(`votes.${value}`)}
            </label>
          ))}
        </div>
        <TextField id="feedback-note" label={t("feedbackNote")} value={note} onChange={setNote} />
      </fieldset>
      <div>
        <WriteGate projectId={projectId}>
          <Button type="submit" disabled={!vote || give.isPending} data-testid="run-feedback-save">
            {t("feedbackSave")}
          </Button>
        </WriteGate>
      </div>
    </form>
  );
}
