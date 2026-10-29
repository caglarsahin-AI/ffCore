"use client";

import { RefreshCwIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import { ListState } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { useDeleteDocument, useDocuments } from "@/lib/api/knowledge-queries";
import type { KbDocument } from "@/lib/api/knowledge-queries";
import { documentError, documentLayer, documentsRefetchInterval, gateReason } from "@/lib/knowledge";

const STATUS_VARIANT = {
  indexed: "secondary",
  skipped: "outline",
  failed: "destructive",
  timeout: "destructive",
} as const;

// Documents of one knowledge base: status, layer, each gate's decision with its reason, converter
// and time, chunks, version, access. Polls while a document is in flight (shown, not hidden).
export function DocumentTable({ projectId, kbId }: { projectId: string; kbId: string }) {
  const t = useTranslations("Documents");
  const tState = useTranslations("State");
  const documents = useDocuments(projectId, kbId);
  const remove = useDeleteDocument(projectId, kbId);
  const report = useReportError();

  function onDelete(document: KbDocument) {
    if (!window.confirm(t("deleteConfirm", { name: document.filename }))) return;
    remove.mutate(document.id, { onSuccess: () => toast.success(tState("saved")), onError: report });
  }

  return (
    <div className="flex flex-col gap-3">
      {documentsRefetchInterval(documents.data) !== false && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status" data-testid="documents-refreshing">
          <RefreshCwIcon className="size-4 animate-spin" aria-hidden />
          {t("refreshing")}
        </p>
      )}
      <ListState query={documents} empty={{ title: t("emptyTitle"), body: t("emptyBody") }}>
        {(rows) => (
          <Table data-testid="documents-table">
            <TableHeader>
              <TableRow>
                <TableHead>{t("file")}</TableHead>
                <TableHead>{t("status")}</TableHead>
                <TableHead>{t("layer")}</TableHead>
                <TableHead>{t("gates")}</TableHead>
                <TableHead>{t("converter")}</TableHead>
                <TableHead className="text-right">{t("chunks")}</TableHead>
                <TableHead className="text-right">{t("version")}</TableHead>
                <TableHead>{t("access")}</TableHead>
                <TableHead>
                  <span className="sr-only">{t("delete")}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((document) => (
                <DocumentRow key={document.id} document={document} projectId={projectId} onDelete={onDelete} />
              ))}
            </TableBody>
          </Table>
        )}
      </ListState>
    </div>
  );
}

function DocumentRow({
  document,
  projectId,
  onDelete,
}: {
  document: KbDocument;
  projectId: string;
  onDelete: (document: KbDocument) => void;
}) {
  const t = useTranslations("Documents");
  const tAccess = useTranslations("Access");
  const tStatus = useTranslations("SystemStatus");
  const variant = STATUS_VARIANT[document.status as keyof typeof STATUS_VARIANT] ?? "outline";
  const error = document.error ? documentError(document.error) : null;
  const open = document.acl_roles.length === 0 && document.acl_users.length === 0;
  return (
    <TableRow id={`doc-${document.id}`} data-testid={`document-${document.filename}`} data-status={document.status}>
      <TableCell className="max-w-64 align-top">
        <div className="flex flex-col gap-1">
          <span className="font-mono break-all">{document.filename}</span>
          {error && (
            <div className="flex flex-col gap-1 text-sm" role="alert" data-testid="document-error">
              <span className="font-medium text-destructive">
                {error.key ? tStatus(`codes.${error.key}`) : t("errorTitle")}
              </span>
              <details className="text-muted-foreground">
                <summary className="cursor-pointer">{t("details")}</summary>
                <pre className="mt-1 whitespace-pre-wrap">{document.error}</pre>
              </details>
            </div>
          )}
        </div>
      </TableCell>
      <TableCell className="align-top">
        <Badge variant={variant}>{t(`statuses.${document.status}`)}</Badge>
      </TableCell>
      <TableCell className="align-top font-mono">{t(`layers.${documentLayer(document)}`)}</TableCell>
      <TableCell className="align-top">
        <ul className="flex flex-col gap-1 text-sm" data-testid="gates">
          {([document.gate0, document.gate1, document.gate2] as const).map((gate, number) => (
            <li key={number} data-gate={number} data-gate-status={gate.status ?? "none"}>
              <span className="text-muted-foreground">{t("gate", { number })}</span>{" "}
              {gate.status ? t(`gateStatus.${gate.status}`) : t("gateNotRun")}
              {gate.reason && <GateReason reason={gate.reason} />}
            </li>
          ))}
        </ul>
        {document.duplicate_of && (
          <a className="text-sm text-primary underline-offset-4 hover:underline" href={`#doc-${document.duplicate_of}`} data-testid="duplicate-link">
            {t("duplicateLink")}
          </a>
        )}
      </TableCell>
      <TableCell className="align-top text-sm">
        {document.convert_engine && <span className="font-mono">{document.convert_engine}</span>}
        {document.convert_seconds != null && (
          <span className="block text-muted-foreground">{t("seconds", { seconds: document.convert_seconds.toFixed(1) })}</span>
        )}
      </TableCell>
      <TableCell className="text-right align-top font-mono">{document.chunk_count}</TableCell>
      <TableCell className="text-right align-top font-mono">{document.version}</TableCell>
      <TableCell className="align-top text-sm" data-testid="document-access">
        {open ? t("accessOpen") : [...document.acl_roles.map((role) => tAccess(`roles.${role}`)), ...document.acl_users].join(", ")}
      </TableCell>
      <TableCell className="text-right align-top">
        <WriteGate projectId={projectId}>
          <Button size="sm" variant="outline" onClick={() => onDelete(document)}>
            {t("delete")}
          </Button>
        </WriteGate>
      </TableCell>
    </TableRow>
  );
}

// Known reasons get a sentence; unknown ones show their code as it is (never a guess).
function GateReason({ reason }: { reason: string }) {
  const t = useTranslations("Documents");
  const parsed = gateReason(reason);
  const text = parsed.key ? t(`reasons.${parsed.key}`, { arg: parsed.arg ?? "" }) : t("unknownReason", { code: parsed.code });
  return (
    <span className="block text-muted-foreground" data-reason={parsed.code}>
      {text}
    </span>
  );
}
