"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { TextField } from "@/components/form-parts";
import { WriteGate } from "@/components/write-gate";
import { Button } from "@/components/ui/button";
import type { Decision } from "@/lib/api/approvals-queries";
import type { PendingApproval } from "@/lib/run-view";

// A run waiting for an approval (07), shared by the agent test panel (`variant="panel"`: arguments
// always visible, buttons behind the write gate, testids `test-*` as in 10b) and the chat
// (`variant="chat"`: arguments behind "Details"; who may not decide sees which role decides).
// `canDecide` is the caller's rule: chat = edit access and role >= assign_to (K-11-0005).
export function ApprovalPrompt({
  approval,
  projectId,
  variant,
  canDecide,
  approverRole,
  pending,
  onDecide,
}: {
  approval: PendingApproval;
  projectId: string;
  variant: "panel" | "chat";
  canDecide: boolean;
  approverRole: string;
  pending: boolean;
  onDecide: (decision: Decision, note: string | null) => void;
}) {
  const t = useTranslations("RunCards");
  const [note, setNote] = useState("");
  const id = variant === "panel" ? "test" : "chat";
  const args = <pre tabIndex={0} className="overflow-auto rounded bg-muted p-2 text-xs">{JSON.stringify(approval.arguments, null, 2)}</pre>;
  const decide = (decision: Decision) => {
    onDecide(decision, note.trim() || null);
    setNote("");
  };
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-primary p-3" role="group" aria-label={t("approvalTitle")} data-testid={`${id}-approval`}>
      <p className="text-sm font-medium">{t("approvalTitle")}</p>
      <p className="font-mono text-sm">{approval.action}</p>
      {variant === "panel" ? (
        args
      ) : (
        <details>
          <summary className="cursor-pointer text-xs text-muted-foreground">{t("details")}</summary>
          {args}
        </details>
      )}
      {approval.assignTo && <p className="text-sm text-muted-foreground">{t("approvalRole", { role: approverRole })}</p>}
      {!approval.approvalId ? (
        <p className="text-sm text-destructive" data-testid={`${id}-approval-no-id`}>
          {t("approvalNoId")}{" "}
          <Link href="/approvals" className="underline">
            {t("openApprovals")}
          </Link>
        </p>
      ) : canDecide ? (
        <>
          <TextField id={`${id}-approval-note`} label={t("approvalNote")} value={note} onChange={setNote} />
          <div className="flex gap-2">
            <WriteGate projectId={projectId}>
              <Button type="button" onClick={() => decide("approve")} disabled={pending} data-testid={`${id}-approve`}>
                {t("approve")}
              </Button>
            </WriteGate>
            <WriteGate projectId={projectId}>
              <Button type="button" variant="outline" onClick={() => decide("reject")} disabled={pending} data-testid={`${id}-reject`}>
                {t("reject")}
              </Button>
            </WriteGate>
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground" role="status" data-testid={`${id}-approval-waiting`}>
          {t("approvalWaiting", { role: approverRole })}
        </p>
      )}
    </div>
  );
}
