"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { TextField } from "@/components/form-parts";
import { QueryError, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useApproval, useDecideApproval } from "@/lib/api/approvals-queries";
import type { Approval, Decision } from "@/lib/api/approvals-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

export default function ApprovalPage() {
  const { projectId } = useSession();
  const { approvalId } = useParams<{ approvalId: string }>();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <ApprovalDetail key={`${projectId}:${approvalId}`} projectId={projectId} approvalId={approvalId} />;
}

function ApprovalDetail({ projectId, approvalId }: { projectId: string; approvalId: string }) {
  const t = useTranslations("Approvals");
  const tState = useTranslations("State");
  const query = useApproval(projectId, approvalId);
  if (query.isPending || (query.isError && isUnauthenticated(query.error))) {
    return <p className="text-muted-foreground">{tState("loading")}</p>;
  }
  if (query.isError) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink label={t("back")} />
        <QueryError error={query.error} />
      </div>
    );
  }
  return <Loaded projectId={projectId} approval={query.data} />;
}

// Decision (07): the buttons follow `can_decide` (session, edit access, role ≥ assigned_role); the
// backend checks again and its 403/409 codes are shown as messages. Arguments are the masked ones
// the guardrail stored; the raw values were never kept.
function Loaded({ projectId, approval }: { projectId: string; approval: Approval }) {
  const t = useTranslations("Approvals");
  const tState = useTranslations("State");
  const format = useFormatter();
  const decide = useDecideApproval(projectId);
  const report = useReportError();
  const [note, setNote] = useState("");
  const pending = approval.status === "pending";
  const when = (iso: string | null) => (iso ? format.dateTime(new Date(iso), { dateStyle: "medium", timeStyle: "medium" }) : t("none"));

  function onDecide(decision: Decision) {
    decide.mutate(
      { id: approval.id, decision, note: note.trim() || null },
      { onSuccess: () => toast.success(tState("saved")), onError: report },
    );
  }

  const decideButton = (decision: Decision) => {
    const button = (
      <Button
        variant={decision === "approve" ? "default" : "outline"}
        onClick={() => onDecide(decision)}
        disabled={decide.isPending || !approval.can_decide}
        data-testid={`approval-${decision}`}
      >
        {t(decision)}
      </Button>
    );
    return <WriteGate projectId={projectId}>{button}</WriteGate>;
  };

  return (
    <div className="flex flex-col gap-4">
      <BackLink label={t("back")} />
      <Screen title={approval.action} description={t("detailDescription")}>
        <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4" data-testid="approval-summary">
          <Fact label={t("status")} value={<Badge variant={pending ? "default" : "outline"} data-testid="approval-detail-status">{t(`statuses.${approval.status}`)}</Badge>} />
          <Fact label={t("assignedRole")} value={t(`roles.${approval.assigned_role}`)} />
          <Fact label={t("requested")} value={when(approval.requested_at)} />
          <Fact label={t("expires")} value={when(approval.expires_at)} />
          <Fact label={t("run")} value={<Link className="text-primary underline-offset-4 hover:underline" href={`/runs/${approval.run_id}`}>{t("openRun")}</Link>} />
          <Fact label={t("tool")} value={<span className="font-mono">{approval.tool_key ?? t("none")}</span>} />
          <Fact label={t("resolved")} value={when(approval.resolved_at)} />
          <Fact label={t("resolvedBy")} value={approval.resolved_by ?? t("none")} />
        </dl>
        <section className="flex flex-col gap-2">
          <h2 className="text-lg font-medium">{t("arguments")}</h2>
          <pre tabIndex={0} className="overflow-auto rounded-md border-2 border-primary bg-muted p-3 text-sm" data-testid="approval-arguments">
            {JSON.stringify(approval.arguments, null, 2)}
          </pre>
        </section>
        {approval.reason_from_model && (
          <section className="flex flex-col gap-1">
            <h2 className="text-lg font-medium">{t("reason")}</h2>
            <p className="text-sm whitespace-pre-wrap">{approval.reason_from_model}</p>
          </section>
        )}
        {approval.resolution_note && (
          <section className="flex flex-col gap-1">
            <h2 className="text-lg font-medium">{t("resolutionNote")}</h2>
            <p className="text-sm whitespace-pre-wrap">{approval.resolution_note}</p>
          </section>
        )}
        {pending && (
          <section className="flex flex-col gap-3" data-testid="approval-decision">
            {!approval.can_decide && (
              <p className="text-sm text-muted-foreground" data-testid="approval-cannot-decide">
                {t("cannotDecide", { role: t(`roles.${approval.assigned_role}`) })}
              </p>
            )}
            <fieldset disabled={!approval.can_decide} className="flex flex-col gap-3">
              <TextField id="approval-note" label={t("note")} hint={t("noteHint")} value={note} onChange={setNote} />
            </fieldset>
            <div className="flex gap-2">
              {decideButton("approve")}
              {decideButton("reject")}
            </div>
          </section>
        )}
      </Screen>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function BackLink({ label }: { label: string }) {
  return (
    <Link href="/approvals" className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline">
      <ArrowLeftIcon className="size-4" />
      {label}
    </Link>
  );
}
