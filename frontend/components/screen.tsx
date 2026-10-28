"use client";

import { InboxIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";

type ScreenProps = { title: string; description: string; action?: React.ReactNode; children: React.ReactNode };

// Screen shell: title, short explanation for the analyst, the screen's main action (already
// behind <WriteGate> at the call site) and its content.
export function Screen({ title, description, action, children }: ScreenProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex max-w-2xl flex-col gap-1">
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="text-muted-foreground">{description}</p>
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

// Empty list: tells the analyst what to do first (brief 10 "Ortak").
export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <section
      className="flex flex-col items-center gap-3 rounded-xl border border-dashed bg-card px-6 py-12 text-center"
      data-testid="empty-state"
    >
      <InboxIcon className="size-8 text-muted-foreground" aria-hidden />
      <h2 className="text-lg font-medium">{title}</h2>
      <p className="max-w-md text-muted-foreground">{body}</p>
    </section>
  );
}

// Loading, failed and empty states of a list query; the list itself only when there is data.
// A failed load is shown with its error code, never as an empty list (ARCH-06).
export function ListState<T>({
  query,
  empty,
  children,
}: {
  query: UseQueryResult<T[]>;
  empty: { title: string; body: string };
  children: (rows: T[]) => React.ReactNode;
}) {
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  if (query.isPending) return <p className="text-muted-foreground">{tState("loading")}</p>;
  if (query.isError) {
    const code = query.error instanceof ApiError ? query.error.code : "unexpected_response";
    return (
      <section className="flex flex-col gap-2 rounded-xl border bg-card p-6" role="alert" data-testid="list-error">
        <p className="font-medium">{tErrors(errorMessageKey(code))}</p>
        <details className="text-sm text-muted-foreground">
          <summary className="cursor-pointer">{tState("details")}</summary>
          <pre className="mt-2 whitespace-pre-wrap">{`${code}: ${query.error.message}`}</pre>
        </details>
      </section>
    );
  }
  if (query.data.length === 0) return <EmptyState {...empty} />;
  return children(query.data);
}
