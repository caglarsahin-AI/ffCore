"use client";

import { InboxIcon } from "lucide-react";
import { useTranslations } from "next-intl";

import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/lib/api/client";
import { errorMessageKey } from "@/lib/api/errors";
import { isUnauthenticated } from "@/lib/login-redirect";

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

// A failed query, wherever its data would have been: mapped message, contract code and backend
// text under "Details". Never replaced by an empty list or an empty picker (ARCH-06).
export function QueryError({ error, compact = false }: { error: Error; compact?: boolean }) {
  const tState = useTranslations("State");
  const tErrors = useTranslations("Errors");
  const code = error instanceof ApiError ? error.code : "unexpected_response";
  return (
    <section
      className={compact ? "flex flex-col gap-1 text-sm" : "flex flex-col gap-2 rounded-xl border bg-card p-6"}
      role="alert"
      data-testid="query-error"
    >
      <p className="font-medium text-destructive">{tErrors(errorMessageKey(code))}</p>
      <details className="text-muted-foreground">
        <summary className="cursor-pointer">{tState("details")}</summary>
        <pre className="mt-2 whitespace-pre-wrap">{`${code}: ${error.message}`}</pre>
      </details>
    </section>
  );
}

// Loading, failed and empty states of a list query; the list itself only when there is data.
// A 401 is already on its way to sign-in (QueryProvider), so it keeps the loading text.
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
  if (query.isPending || (query.isError && isUnauthenticated(query.error))) {
    return <p className="text-muted-foreground">{tState("loading")}</p>;
  }
  if (query.isError) return <QueryError error={query.error} />;
  if (query.data.length === 0) return <EmptyState {...empty} />;
  return children(query.data);
}
