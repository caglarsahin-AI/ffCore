"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { DisabledWithReason } from "@/components/disabled-with-reason";
import { FieldShell } from "@/components/form-parts";
import { useAccess } from "@/components/session-provider";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { WriteGate } from "@/components/write-gate";
import type { ApiError } from "@/lib/api/client";
import { parseGateFailure } from "@/lib/eval-gate";
import type { GateReason } from "@/lib/eval-gate";

// A publish refused by the exam gate (409 eval_gate_failed): each bound suite and why, read from
// the message (FOLLOWUP-176). Publishing past the gate is an admin's call with a reason (backend:
// 403 force_requires_admin, 422 force_reason_required); others see the control disabled with why.
export function GateFailure({
  projectId,
  error,
  pending,
  onForce,
}: {
  projectId: string;
  error: ApiError;
  pending: boolean;
  onForce: (reason: string) => void;
}) {
  const t = useTranslations("Evaluations.gate");
  const { role, canWrite } = useAccess(projectId);
  const [reason, setReason] = useState("");
  const failures = parseGateFailure(error.message);
  const trimmed = reason.trim();
  const isAdmin = role === "admin";

  const force = (
    <Button variant="destructive" disabled={!isAdmin || trimmed === "" || pending} onClick={() => onForce(trimmed)} data-testid="gate-force">
      {t("force")}
    </Button>
  );

  return (
    <section className="flex flex-col gap-3 rounded-xl border border-destructive/40 bg-card p-4" role="alert" data-testid="gate-failure">
      <p className="font-medium text-destructive">{t("title")}</p>
      {failures ? (
        <ul className="flex flex-col gap-1 text-sm">
          {failures.map((f) => (
            <li key={f.key} data-testid={`gate-suite-${f.key}`}>
              <span className="font-mono">{f.key}</span>
              {": "}
              {f.known ? t(`reasons.${f.reason as GateReason}`) : t("unknownReason")} <span className="font-mono text-muted-foreground">{`(${f.reason})`}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm font-mono" data-testid="gate-raw">
          {error.message}
        </p>
      )}
      <div className="flex flex-col gap-2 border-t pt-3">
        <p className="text-sm text-muted-foreground">{t("forceHint")}</p>
        <FieldShell id="gate-force-reason" label={t("reason")}>
          {(a11y) => (
            <Textarea {...a11y} value={reason} onChange={(e) => setReason(e.target.value)} disabled={!isAdmin || !canWrite} rows={2} />
          )}
        </FieldShell>
        <div>
          {isAdmin ? (
            <WriteGate projectId={projectId}>{force}</WriteGate>
          ) : (
            <DisabledWithReason reason={t("forceNeedsAdmin")} needs="admin">
              {force}
            </DisabledWithReason>
          )}
        </div>
      </div>
    </section>
  );
}
