"use client";

import { PlusIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { SuiteForm } from "@/components/eval/suite-form";
import { useProjectKey } from "@/components/eval/use-project-key";
import { ListState, Screen } from "@/components/screen";
import { useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useAgents } from "@/lib/api/agents-queries";
import { useCreateSuite, useSuites } from "@/lib/api/eval-queries";
import type { SuiteCreate } from "@/lib/api/eval-queries";

// Exam suites of the project (09). A suite names a Langfuse dataset, its scorers and threshold,
// and optionally the agent whose publish it gates. Analysts with edit access create and run them.
export default function EvaluationsPage() {
  const { projectId } = useSession();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <SuiteList key={projectId} projectId={projectId} />;
}

function SuiteList({ projectId }: { projectId: string }) {
  const t = useTranslations("Evaluations");
  const tState = useTranslations("State");
  const router = useRouter();
  const suites = useSuites(projectId);
  const agents = useAgents(projectId);
  const projectKey = useProjectKey(projectId);
  const create = useCreateSuite(projectId);
  const report = useReportError();
  const [adding, setAdding] = useState(false);
  const agentName = new Map((agents.data ?? []).map((a) => [a.id, a.name]));

  const action = (
    <WriteGate projectId={projectId}>
      <Button onClick={() => setAdding(true)} disabled={adding} data-testid="primary-action">
        <PlusIcon />
        {t("add")}
      </Button>
    </WriteGate>
  );

  return (
    <Screen title={t("title")} description={t("description")} action={action}>
      {adding && (
        <SuiteForm
          projectId={projectId}
          projectKey={projectKey ?? ""}
          agents={(agents.data ?? []).map((a) => ({ id: a.id, name: a.name }))}
          mode="create"
          pending={create.isPending}
          onCancel={() => setAdding(false)}
          onSubmit={(body) =>
            create.mutate(body as SuiteCreate, {
              onSuccess: (suite) => {
                toast.success(tState("saved"));
                router.push(`/evaluations/${suite.id}`);
              },
              onError: report,
            })
          }
        />
      )}
      <ListState query={suites} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="suite-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("name")}</TableHead>
                <TableHead>{t("agent")}</TableHead>
                <TableHead>{t("scorersCol")}</TableHead>
                <TableHead className="text-right">{t("threshold")}</TableHead>
                <TableHead className="text-right">{t("repeatCol")}</TableHead>
                <TableHead>{t("approvals")}</TableHead>
                <TableHead>{t("dataset")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((suite) => (
                <TableRow key={suite.id} data-testid={`suite-${suite.key}`}>
                  <TableCell>
                    <Link className="font-medium text-primary underline-offset-4 hover:underline" href={`/evaluations/${suite.id}`}>
                      {suite.name}
                    </Link>
                    <p className="font-mono text-xs text-muted-foreground">{suite.key}</p>
                  </TableCell>
                  <TableCell>{suite.agent_id ? (agentName.get(suite.agent_id) ?? <span className="font-mono text-xs">{suite.agent_id}</span>) : t("noGate")}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {suite.scorers.map((s) => (
                        <Badge key={String(s.name)} variant="outline" className="font-mono">
                          {String(s.name)}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right font-mono">{suite.pass_threshold}</TableCell>
                  <TableCell className="text-right font-mono">{suite.repeat}</TableCell>
                  <TableCell>{suite.approve_tools ? t("waitsApprovals") : t("noApprovals")}</TableCell>
                  <TableCell className="font-mono text-xs break-all">{suite.langfuse_dataset_name}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </Screen>
  );
}
