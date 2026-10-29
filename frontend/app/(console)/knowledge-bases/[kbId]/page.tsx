"use client";

import { ArrowLeftIcon } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { DisabledWithReason } from "@/components/disabled-with-reason";
import { DocumentTable } from "@/components/document-table";
import { DocumentUpload } from "@/components/document-upload";
import { KnowledgeBaseForm } from "@/components/kb-form";
import { ReindexForm } from "@/components/reindex-form";
import { QueryError, Screen } from "@/components/screen";
import { SearchPanel } from "@/components/search-panel";
import { useAccess, useSession } from "@/components/session-provider";
import { StatusPage } from "@/components/status-page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { hasRole } from "@/lib/access";
import { useDeleteKnowledgeBase, useKnowledgeBase } from "@/lib/api/knowledge-queries";
import type { KnowledgeBase } from "@/lib/api/knowledge-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

export default function KnowledgeBasePage() {
  const { projectId } = useSession();
  const { kbId } = useParams<{ kbId: string }>();
  if (!projectId) return <StatusPage kind="selectProject" />;
  return <KnowledgeBaseDetail key={`${projectId}:${kbId}`} projectId={projectId} kbId={kbId} />;
}

function KnowledgeBaseDetail({ projectId, kbId }: { projectId: string; kbId: string }) {
  const t = useTranslations("KnowledgeBases");
  const tState = useTranslations("State");
  const query = useKnowledgeBase(projectId, kbId);
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
  return <Loaded projectId={projectId} knowledgeBase={query.data} />;
}

function Loaded({ projectId, knowledgeBase }: { projectId: string; knowledgeBase: KnowledgeBase }) {
  const t = useTranslations("KnowledgeBases");
  const tState = useTranslations("State");
  const router = useRouter();
  const remove = useDeleteKnowledgeBase(projectId);
  const report = useReportError();
  const { role } = useAccess(projectId);
  const [editing, setEditing] = useState(false);
  const isAdmin = hasRole(role, "admin");

  function onDelete() {
    if (!window.confirm(t("deleteConfirm", { name: knowledgeBase.name }))) return;
    remove.mutate(knowledgeBase.id, {
      onSuccess: () => {
        toast.success(tState("saved"));
        router.push("/knowledge-bases");
      },
      onError: report,
    });
  }

  // Changing or deleting a knowledge base is admin-only (04a); others see why.
  const gate = (control: React.ReactElement<{ disabled?: boolean }>) =>
    isAdmin ? (
      <WriteGate projectId={projectId}>{control}</WriteGate>
    ) : (
      <DisabledWithReason reason={t("needsAdmin")} needs="admin">
        {control}
      </DisabledWithReason>
    );

  const actions = (
    <div className="flex gap-2">
      {gate(
        <Button variant="outline" onClick={() => setEditing(true)} disabled={editing} data-testid="kb-edit">
          {t("edit")}
        </Button>,
      )}
      {gate(
        <Button variant="outline" onClick={onDelete} data-testid="kb-delete">
          {t("delete")}
        </Button>,
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <BackLink label={t("back")} />
      <Screen title={knowledgeBase.name} description={knowledgeBase.description ?? t("description")} action={actions}>
        <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-4" data-testid="kb-summary">
          <Fact label={t("key")} value={<span className="font-mono">{knowledgeBase.key}</span>} />
          <Fact label={t("status")} value={<Badge variant="secondary">{t(`statuses.${knowledgeBase.status}`)}</Badge>} />
          <Fact label={t("embedModel")} value={<span className="font-mono">{knowledgeBase.embed_model}</span>} />
          <Fact
            label={t("thresholdRule")}
            value={
              knowledgeBase.rerank
                ? t("thresholdRerank")
                : knowledgeBase.default_min_score == null
                  ? t("thresholdNone")
                  : t("thresholdMinScore", { score: knowledgeBase.default_min_score })
            }
          />
          <Fact label={t("documents")} value={<span className="font-mono">{knowledgeBase.document_count}</span>} />
          <Fact label={t("chunks")} value={<span className="font-mono">{knowledgeBase.chunk_count}</span>} />
          <Fact label={t("chunkSize")} value={<span className="font-mono">{knowledgeBase.chunk_size}</span>} />
          <Fact label={t("rerankModel")} value={<span className="font-mono">{knowledgeBase.rerank ? knowledgeBase.rerank_model : t("thresholdNone")}</span>} />
        </dl>
        {editing && <KnowledgeBaseForm projectId={projectId} knowledgeBase={knowledgeBase} onDone={() => setEditing(false)} />}
        <Tabs defaultValue="documents">
          <TabsList>
            <TabsTrigger value="documents">{t("tabs.documents")}</TabsTrigger>
            <TabsTrigger value="search">{t("tabs.search")}</TabsTrigger>
          </TabsList>
          <TabsContent value="documents" className="flex flex-col gap-4 pt-2">
            <DocumentUpload projectId={projectId} kbId={knowledgeBase.id} />
            <ReindexForm projectId={projectId} kbId={knowledgeBase.id} />
            <DocumentTable projectId={projectId} kbId={knowledgeBase.id} />
          </TabsContent>
          <TabsContent value="search" className="pt-2">
            <SearchPanel projectId={projectId} knowledgeBase={knowledgeBase} />
          </TabsContent>
        </Tabs>
      </Screen>
    </div>
  );
}

function BackLink({ label }: { label: string }) {
  return (
    <Link className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground" href="/knowledge-bases">
      <ArrowLeftIcon className="size-4" aria-hidden />
      {label}
    </Link>
  );
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
