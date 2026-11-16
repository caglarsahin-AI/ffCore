"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { ExamList } from "@/components/eval/exam-list";
import { StartExam } from "@/components/eval/start-exam";
import { SuiteForm } from "@/components/eval/suite-form";
import { useProjectKey } from "@/components/eval/use-project-key";
import { QueryError } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useAgents } from "@/lib/api/agents-queries";
import { useDeleteSuite, useSuite, useUpdateSuite } from "@/lib/api/eval-queries";
import type { Suite, SuiteUpdate } from "@/lib/api/eval-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

// One suite: its settings, the exam start and its exams. Items live in the suite's Langfuse dataset
// (09 brief "Veri modeli"); the console adds them from a run ("Add to exam") and does not list
// them (K-10C1-0002 S2).
export default function SuitePage() {
  const { projectId } = useSession();
  const { suiteId } = useParams<{ suiteId: string }>();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <SuiteDetail key={`${projectId}:${suiteId}`} projectId={projectId} suiteId={suiteId} />;
}

function SuiteDetail({ projectId, suiteId }: { projectId: string; suiteId: string }) {
  const t = useTranslations("Evaluations");
  const tState = useTranslations("State");
  const suite = useSuite(projectId, suiteId);
  if (suite.isPending || (suite.isError && isUnauthenticated(suite.error))) return <p className="text-muted-foreground">{tState("loading")}</p>;
  if (suite.isError) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink label={t("back")} />
        <QueryError error={suite.error} />
      </div>
    );
  }
  return <Loaded projectId={projectId} suite={suite.data} />;
}

function Loaded({ projectId, suite }: { projectId: string; suite: Suite }) {
  const t = useTranslations("Evaluations");
  const tState = useTranslations("State");
  const router = useRouter();
  const report = useReportError();
  const agents = useAgents(projectId);
  const projectKey = useProjectKey(projectId);
  const update = useUpdateSuite(projectId, suite.id);
  const remove = useDeleteSuite(projectId);

  function onDelete() {
    if (!window.confirm(t("deleteConfirm", { name: suite.name }))) return;
    remove.mutate(suite.id, {
      onSuccess: () => {
        toast.success(tState("saved"));
        router.push("/evaluations");
      },
      onError: report,
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <BackLink label={t("back")} />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex max-w-2xl flex-col gap-1">
          <h1 className="text-2xl font-semibold" data-testid="suite-title">
            {suite.name}
          </h1>
          <p className="text-muted-foreground">{t("suiteDescription")}</p>
          <p className="text-sm">
            {t("datasetLabel")} <span className="font-mono break-all select-all" data-testid="suite-dataset">{suite.langfuse_dataset_name}</span>
          </p>
          <p className="text-sm text-muted-foreground">{t("itemsHint")}</p>
        </div>
        <WriteGate projectId={projectId}>
          <Button variant="outline" onClick={onDelete} disabled={remove.isPending} data-testid="suite-delete">
            {t("delete")}
          </Button>
        </WriteGate>
      </div>
      <StartExam projectId={projectId} suite={suite} />
      <ExamList projectId={projectId} suiteId={suite.id} />
      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">{t("settings")}</h2>
        <SuiteForm
          key={suite.updated_at}
          projectId={projectId}
          projectKey={projectKey ?? ""}
          agents={(agents.data ?? []).map((a) => ({ id: a.id, name: a.name }))}
          mode="update"
          initial={suite}
          pending={update.isPending}
          onSubmit={(body) => update.mutate(body as SuiteUpdate, { onSuccess: () => toast.success(tState("saved")), onError: report })}
        />
      </section>
    </div>
  );
}

function BackLink({ label }: { label: string }) {
  return (
    <Link href="/evaluations" className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline">
      <ArrowLeftIcon className="size-4" />
      {label}
    </Link>
  );
}
