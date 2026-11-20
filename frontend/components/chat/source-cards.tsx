"use client";

import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { useSourceChunk } from "@/lib/api/chat-queries";
import { readErrorCode } from "@/lib/api/runs-queries";
import { errorMessageKey } from "@/lib/api/errors";
import type { SourceCard } from "@/lib/run-view";

export type CitedSource = SourceCard & { document_id?: string; updated_at_source?: string | null };

// The sources a run cited, shared by the console test panel (10) and the end user chat (11).
// `panel`: name, page and breadcrumb (unchanged from 10b). `chat`: also the document's update
// date (brief 11, PayCore D5); a card opens the cited passage, read with the caller's ACL; a
// passage that cannot be read says why with its code (never an empty text).
export function SourceCards({ sources, variant, projectId, runId }: { sources: CitedSource[]; variant: "panel" | "chat"; projectId?: string; runId?: string | null }) {
  const t = useTranslations("RunCards");
  if (sources.length === 0) return null;
  if (variant === "panel") {
    return (
      <div className="flex flex-col gap-2" data-testid="test-sources">
        <span className="text-sm font-medium">{t("sources")}</span>
        {sources.map((source, i) => (
          <div key={source.chunk_id ?? i} className="rounded-lg border p-2 text-sm" data-testid="test-source-card">
            <p className="font-medium">{t("sourceTitle", { n: source.n ?? i + 1, name: source.document_name ?? source.kb_key ?? "" })}</p>
            <p className="text-muted-foreground">
              {source.page != null && t("sourcePage", { page: source.page })} {source.breadcrumb}
            </p>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2" data-testid="chat-sources">
      <span className="text-xs font-medium text-muted-foreground">{t("sources")}</span>
      <ul className="flex flex-col gap-2">
        {sources.map((source, i) => (
          <ChatSourceCard key={source.chunk_id ?? i} source={source} index={i} projectId={projectId ?? ""} runId={runId ?? null} />
        ))}
      </ul>
    </div>
  );
}

function ChatSourceCard({ source, index, projectId, runId }: { source: CitedSource; index: number; projectId: string; runId: string | null }) {
  const t = useTranslations("RunCards");
  const tErrors = useTranslations("Errors");
  const format = useFormatter();
  const [open, setOpen] = useState(false);
  const chunk = useSourceChunk(projectId, runId, source.chunk_id ?? null, open);
  const updated = source.updated_at_source ? format.dateTime(new Date(source.updated_at_source), { dateStyle: "medium" }) : null;
  const panelId = `source-${runId ?? "live"}-${source.chunk_id ?? index}`;
  return (
    <li className="rounded-lg border bg-card text-sm">
      <button
        type="button"
        className="flex w-full flex-col items-start gap-0.5 p-2 text-left hover:bg-muted/60 focus-visible:outline-2 focus-visible:outline-ring"
        aria-expanded={open}
        aria-controls={panelId}
        disabled={!source.chunk_id || !runId}
        onClick={() => setOpen((value) => !value)}
        data-testid="chat-source-card"
      >
        <span className="font-medium">{t("sourceTitle", { n: source.n ?? index + 1, name: source.document_name ?? source.kb_key ?? "" })}</span>
        <span className="text-muted-foreground">
          {[source.page != null ? t("sourcePage", { page: source.page }) : null, source.breadcrumb, updated ? t("sourceUpdated", { date: updated }) : null].filter(Boolean).join(" · ")}
        </span>
      </button>
      {open && (
        <div id={panelId} className="border-t p-2">
          {chunk.isPending && <p className="text-muted-foreground" role="status">{t("sourceLoading")}</p>}
          {chunk.isError && (
            <p className="text-destructive" role="alert" data-testid="chat-source-error">
              {t("sourceError", { message: tErrors(errorMessageKey(readErrorCode(chunk.error))), code: readErrorCode(chunk.error) })}
            </p>
          )}
          {chunk.data && (
            <p className="whitespace-pre-wrap" data-testid="chat-source-text">
              {chunk.data.text}
            </p>
          )}
        </div>
      )}
    </li>
  );
}
