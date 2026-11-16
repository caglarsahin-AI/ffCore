"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Suspense } from "react";

import { CompareView } from "@/components/eval/compare-view";
import { QueryError, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { useCompare } from "@/lib/api/eval-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

// Two exams side by side (09 GET /eval-runs/compare?a=&b=). A pair the backend cannot compare
// (422 eval_runs_not_comparable) is shown with its message and code, never as an empty comparison.
export default function ComparePage() {
  return (
    <Suspense>
      <CompareRoute />
    </Suspense>
  );
}

function CompareRoute() {
  const { projectId } = useSession();
  const params = useSearchParams();
  if (!projectId) return <StatusPage kind="selectProject" />;
  const a = params.get("a");
  const b = params.get("b");
  return <Compare key={`${projectId}:${a}:${b}`} projectId={projectId} a={a} b={b} />;
}

function Compare({ projectId, a, b }: { projectId: string; a: string | null; b: string | null }) {
  const t = useTranslations("Evaluations.compare");
  const tState = useTranslations("State");
  const tBack = useTranslations("Evaluations");
  const query = useCompare(projectId, a, b);
  let body: React.ReactNode;
  if (!a || !b) body = <p className="text-muted-foreground" data-testid="compare-missing">{t("missing")}</p>;
  else if (query.isPending || (query.isError && isUnauthenticated(query.error))) body = <p className="text-muted-foreground">{tState("loading")}</p>;
  else if (query.isError) body = <QueryError error={query.error} />;
  else body = <CompareView compare={query.data} />;
  return (
    <div className="flex flex-col gap-4">
      <Link
        href={query.data ? `/evaluations/${query.data.suite_id}` : "/evaluations"}
        className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline"
      >
        <ArrowLeftIcon className="size-4" />
        {query.data ? tBack("backToSuite") : tBack("back")}
      </Link>
      <Screen title={t("title")} description={t("description")}>
        {body}
      </Screen>
    </div>
  );
}
