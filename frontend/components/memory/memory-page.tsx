"use client";

import { PencilIcon, Trash2Icon } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { MemoryError } from "@/components/memory/memory-error";
import { QueryError } from "@/components/screen";
import { AlertDialog, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  useDeleteAllMemories,
  useDeleteMemory,
  useMemories,
  useOptOut,
  useRemember,
  useSetOptOut,
  useUpdateMemory,
} from "@/lib/api/memories-queries";
import type { Memory } from "@/lib/api/memories-queries";

const TEXT_MAX = 500;

// The member's own memory (14-2 D5; brief 14 "Kullanıcı kontrolü"): the active items with kind,
// text, when they were learned and how often they were used; edit, delete (at once, for good, S6),
// delete all (confirmed), remember this, and memory off/on for the member (opt-out). Read access
// keeps all of it open: memory is the member's own data (14-1). Archived items (superseded or over
// the limit) are listed apart; they are not used in answers.
export function MemoryPage({ projectId }: { projectId: string }) {
  const t = useTranslations("memory.page");
  const items = useMemories(projectId);
  const optOut = useOptOut(projectId);
  const setOptOut = useSetOptOut(projectId);
  const deleteAll = useDeleteAllMemories(projectId);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const all = items.data ?? [];
  const active = all.filter((m) => m.status === "active");
  const archived = all.filter((m) => m.status === "archived");
  const on = optOut.data === false;

  function run<T>(promise: Promise<T>) {
    setError(null);
    promise.catch(setError);
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-4 sm:p-6" data-testid="memory-page">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("intro")}</p>
      </div>

      <div className="flex flex-col gap-2 rounded-lg border p-4">
        <div className="flex items-center justify-between gap-3">
          <Label htmlFor="memory-opt-out">{t("optOutLabel")}</Label>
          {optOut.isSuccess && (
            <button
              id="memory-opt-out"
              type="button"
              role="switch"
              aria-checked={on}
              disabled={setOptOut.isPending}
              onClick={() => run(setOptOut.mutateAsync(on))}
              className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors disabled:opacity-50 ${on ? "bg-primary" : "bg-muted"}`}
              data-testid="memory-opt-out"
            >
              <span className={`inline-block size-4 rounded-full bg-background shadow transition-transform ${on ? "translate-x-6" : "translate-x-1"}`} />
            </button>
          )}
        </div>
        {optOut.isError && <QueryError error={optOut.error} compact />}
        <p className="text-sm text-muted-foreground">{t("optOutHint")}</p>
        {optOut.data === true && (
          <p className="text-sm font-medium" role="status" data-testid="memory-off-note">
            {t("offNote")}
          </p>
        )}
      </div>

      <RememberBox projectId={projectId} onError={setError} />
      <MemoryError error={error} />

      <section className="flex flex-col gap-3" aria-labelledby="memory-list-title">
        <div className="flex items-center justify-between gap-3">
          <h2 id="memory-list-title" className="font-medium">
            {t("listTitle")}
          </h2>
          <Button variant="outline" size="sm" disabled={all.length === 0 || deleteAll.isPending} onClick={() => setConfirming(true)} data-testid="memory-delete-all">
            {t("deleteAll")}
          </Button>
        </div>
        {items.isPending && (
          <p className="text-sm text-muted-foreground" role="status">
            {t("loading")}
          </p>
        )}
        {items.isError && <QueryError error={items.error} />}
        {items.isSuccess && active.length === 0 && (
          <p className="text-sm text-muted-foreground" data-testid="memory-empty">
            {t("empty")}
          </p>
        )}
        <ul className="flex flex-col gap-2">
          {active.map((item) => (
            <MemoryRow key={item.id} projectId={projectId} item={item} onError={setError} />
          ))}
        </ul>
        {archived.length > 0 && (
          <details className="rounded-lg border p-3 text-sm" data-testid="memory-archived">
            <summary className="cursor-pointer font-medium">{t("archived", { count: archived.length })}</summary>
            <p className="mt-2 text-muted-foreground">{t("archivedHint")}</p>
            <ul className="mt-2 flex flex-col gap-1 text-muted-foreground">
              {archived.map((item) => (
                <li key={item.id} data-testid="memory-archived-item">
                  {item.text}
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent data-testid="memory-delete-all-dialog">
          <AlertDialogTitle>{t("deleteAllTitle")}</AlertDialogTitle>
          <AlertDialogDescription>{t("deleteAllBody")}</AlertDialogDescription>
          <AlertDialogFooter>
            <Button variant="outline" onClick={() => setConfirming(false)} autoFocus data-testid="memory-delete-all-cancel">
              {t("cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setConfirming(false);
                run(deleteAll.mutateAsync());
              }}
              data-testid="memory-delete-all-confirm"
            >
              {t("deleteAllConfirm")}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function RememberBox({ projectId, onError }: { projectId: string; onError: (error: unknown) => void }) {
  const t = useTranslations("memory.page");
  const remember = useRemember(projectId);
  const [text, setText] = useState("");
  function save() {
    onError(null);
    remember.mutate(text.trim(), { onSuccess: () => setText(""), onError });
  }
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor="memory-remember">{t("rememberLabel")}</Label>
      <Textarea
        id="memory-remember"
        value={text}
        maxLength={TEXT_MAX}
        onChange={(e) => setText(e.target.value)}
        aria-describedby="memory-remember-hint"
        className="min-h-16"
        data-testid="memory-remember-input"
      />
      <p id="memory-remember-hint" className="text-sm text-muted-foreground">
        {t("rememberHint")}
      </p>
      <Button className="self-start" onClick={save} disabled={text.trim() === "" || remember.isPending} data-testid="memory-remember-save">
        {t("rememberSave")}
      </Button>
    </div>
  );
}

function MemoryRow({ projectId, item, onError }: { projectId: string; item: Memory; onError: (error: unknown) => void }) {
  const t = useTranslations("memory");
  const format = useFormatter();
  const update = useUpdateMemory(projectId);
  const remove = useDeleteMemory(projectId);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.text);
  const inputId = `memory-edit-${item.id}`;

  function save() {
    onError(null);
    update.mutate({ id: item.id, text: draft.trim() }, { onSuccess: () => setEditing(false), onError });
  }

  return (
    <li className="flex flex-col gap-2 rounded-lg border p-3" data-testid="memory-item" data-id={item.id}>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="secondary" data-testid="memory-item-kind">
          {t(`kinds.${item.kind}`)}
        </Badge>
        <span data-testid="memory-item-learned">{t("page.learned", { date: format.dateTime(new Date(item.created_at), { dateStyle: "medium" }) })}</span>
        <span data-testid="memory-item-uses">{t("page.uses", { count: item.use_count })}</span>
      </div>
      {editing ? (
        <div className="flex flex-col gap-2">
          <Label htmlFor={inputId} className="sr-only">
            {t("page.editLabel")}
          </Label>
          <Textarea id={inputId} value={draft} maxLength={TEXT_MAX} onChange={(e) => setDraft(e.target.value)} className="min-h-16" data-testid="memory-item-edit-input" />
          <div className="flex gap-2">
            <Button size="sm" onClick={save} disabled={draft.trim() === "" || update.isPending} data-testid="memory-item-edit-save">
              {t("page.editSave")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setDraft(item.text);
                setEditing(false);
              }}
            >
              {t("page.editCancel")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm whitespace-pre-wrap" data-testid="memory-item-text">
            {item.text}
          </p>
          <div className="flex shrink-0 gap-1">
            <Button variant="ghost" size="icon-sm" onClick={() => setEditing(true)} aria-label={t("page.edit")} data-testid="memory-item-edit">
              <PencilIcon aria-hidden />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              disabled={remove.isPending}
              onClick={() => {
                onError(null);
                remove.mutate(item.id, { onError });
              }}
              aria-label={t("page.delete")}
              data-testid="memory-item-delete"
            >
              <Trash2Icon aria-hidden />
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}
