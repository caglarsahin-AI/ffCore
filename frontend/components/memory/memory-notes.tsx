"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { errorCode } from "@/components/memory/memory-error";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api/client";
import { useDeleteMemory, useMemoriesByIds } from "@/lib/api/memories-queries";
import type { RunEvent } from "@/lib/api/runs-queries";

// How often and how long a finished turn's extraction outcome is looked for (K-14-0020 S3). The
// job runs in the background after `done` and may wait for its model slot (brief 14 teknik notlar),
// so when the time is up the note says the items may appear later instead of going quiet.
export const NOTED_POLL_MS = 5_000;
export const NOTED_LIMIT_MS = 120_000;

type Extraction = { written?: string[]; skipped?: string; error?: string };

function memoryOn(events: RunEvent[]): boolean {
  return events.some((e) => e.type === "budget" && (e.payload as { memory?: string }).memory === "on");
}

function usedIds(events: RunEvent[]): string[] {
  const used = events.find((e) => e.type === "memory_used");
  return ((used?.payload as { items?: { id: string }[] } | undefined)?.items ?? []).map((i) => i.id);
}

function extraction(events: RunEvent[]): Extraction | null {
  const found = events.find((e) => e.type === "progress" && "memory_extraction" in (e.payload as object));
  return found ? ((found.payload as { memory_extraction: Extraction }).memory_extraction ?? null) : null;
}

// Under an answer (14-2 D5, K-14-0020 S2/S3). The run's events are read once the run has ended
// (`memory_used` and the extraction outcome never travel on the stream): "I took these into
// account" lists the owner's items by id (`GET /memories?ids=`), each with a one-click forget;
// `watch` (the turn just answered here) keeps reading until the extraction outcome is in and shows
// "I noted: … [Delete]". No memory for the run (off, opted out, none used): nothing is shown.
export function MemoryNotes({
  projectId,
  runId,
  watch,
  pollMs = NOTED_POLL_MS,
  limitMs = NOTED_LIMIT_MS,
}: {
  projectId: string;
  runId: string;
  watch: boolean;
  pollMs?: number;
  limitMs?: number;
}) {
  const t = useTranslations("memory.notes");
  const [expired, setExpired] = useState(false);
  const expiredRef = useRef(false);
  useEffect(() => {
    if (!watch) return;
    const timer = setTimeout(() => {
      expiredRef.current = true;
      setExpired(true);
    }, limitMs);
    return () => clearTimeout(timer);
  }, [watch, limitMs]);

  const events = useQuery({
    queryKey: ["projects", projectId, "run", runId, "memory-events"],
    queryFn: () => api<{ items: RunEvent[] }>("GET", `/api/v1/projects/${projectId}/runs/${runId}/events`).then((r) => r.items),
    staleTime: Infinity,
    refetchInterval: (q) => {
      const items = q.state.data;
      if (!watch || expiredRef.current || !items) return false;
      if (!memoryOn(items) || extraction(items) !== null) return false;
      return pollMs;
    },
  });

  const items = events.data ?? [];
  const used = usedIds(items);
  const outcome = extraction(items);
  const written = outcome?.written ?? [];
  const usedItems = useMemoriesByIds(projectId, used);
  const notedItems = useMemoriesByIds(projectId, written);

  if (events.isError) {
    return (
      <p className="text-xs text-muted-foreground" data-testid="memory-notes-error">
        {t("readFailed", { code: errorCode(events.error) })}
      </p>
    );
  }
  if (!events.isSuccess) return null;
  const waiting = watch && memoryOn(items) && outcome === null;
  return (
    <>
      <span hidden data-testid="memory-notes-read" />
      {used.length > 0 && <UsedNote projectId={projectId} count={used.length} items={usedItems.data ?? []} />}
      {written.length > 0 && (notedItems.data ?? []).length > 0 && <NotedLine projectId={projectId} items={notedItems.data ?? []} />}
      {waiting && expired && (
        <p className="text-xs text-muted-foreground" data-testid="memory-noted-later">
          {t("later")}
        </p>
      )}
    </>
  );
}

function UsedNote({ projectId, count, items }: { projectId: string; count: number; items: { id: string; text: string }[] }) {
  const t = useTranslations("memory.notes");
  const forget = useDeleteMemory(projectId);
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-col gap-1 rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground" data-testid="memory-used">
      <div className="flex items-center justify-between gap-2">
        <span>{t("used", { count })}</span>
        <Button variant="ghost" size="xs" aria-expanded={open} onClick={() => setOpen((o) => !o)} data-testid="memory-used-toggle">
          {open ? t("hide") : t("show")}
        </Button>
      </div>
      {open && (
        <ul className="flex flex-col gap-1">
          {items.map((item) => (
            <li key={item.id} className="flex items-start justify-between gap-2" data-testid="memory-used-item">
              <span className="whitespace-pre-wrap text-foreground">{item.text}</span>
              <Button variant="ghost" size="xs" disabled={forget.isPending} onClick={() => forget.mutate(item.id)} data-testid="memory-forget">
                {t("forget")}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function NotedLine({ projectId, items }: { projectId: string; items: { id: string; text: string }[] }) {
  const t = useTranslations("memory.notes");
  const remove = useDeleteMemory(projectId);
  return (
    <div className="flex flex-col gap-1 text-xs text-muted-foreground" role="status" data-testid="memory-noted">
      <span>{t("noted")}</span>
      <ul className="flex flex-col gap-1">
        {items.map((item) => (
          <li key={item.id} className="flex items-start justify-between gap-2" data-testid="memory-noted-item">
            <span className="whitespace-pre-wrap text-foreground">{item.text}</span>
            <Button variant="ghost" size="xs" disabled={remove.isPending} onClick={() => remove.mutate(item.id)} data-testid="memory-noted-delete">
              {t("notedDelete")}
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
