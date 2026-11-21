"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { TextField } from "@/components/form-parts";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

// The agent's ask_user question (06a `question` event, FOLLOWUP-135), shared by the test panel
// (`variant="panel"`, testids `test-*` as in 10b) and the chat. The answer goes to 06a /resume,
// which is open to the run's own user in read access too.
export function QuestionBox({
  question,
  variant,
  pending,
  onAnswer,
}: {
  question: string;
  variant: "panel" | "chat";
  pending: boolean;
  onAnswer: (answer: string) => void;
}) {
  const t = useTranslations("RunCards");
  const [answer, setAnswer] = useState("");
  const id = variant === "panel" ? "test" : "chat";
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = answer.trim();
    if (!value || pending) return;
    onAnswer(value);
    setAnswer("");
  }
  return (
    <form className="flex flex-col gap-2 rounded-lg border border-primary p-3" onSubmit={submit} noValidate data-testid={`${id}-question`}>
      <p className="text-sm font-medium">{question}</p>
      {variant === "panel" ? (
        <TextField id="test-answer" label={t("answer")} value={answer} onChange={setAnswer} />
      ) : (
        <>
          <label htmlFor="chat-answer-input" className="text-sm">
            {t("answer")}
          </label>
          <Textarea id="chat-answer-input" value={answer} onChange={(e) => setAnswer(e.target.value)} className="min-h-11" data-testid="chat-answer-input" />
        </>
      )}
      <div>
        <Button type="submit" disabled={pending || !answer.trim()} data-testid={`${id}-answer-send`}>
          {t("sendAnswer")}
        </Button>
      </div>
    </form>
  );
}
