"use client";

import { InboxIcon, PlusIcon } from "lucide-react";

import { notConnected } from "@/components/not-connected";
import { Button } from "@/components/ui/button";
import { WriteGate } from "@/components/write-gate";

type ScreenProps = {
  title: string;
  description: string;
  action: string;
  emptyTitle: string;
  emptyBody: string;
  notConnectedMessage: string;
};

// Screen shell for 10a: title, short explanation for the analyst, the create action behind
// <WriteGate>, and the empty state that tells what to do first (brief 10 "Ortak").
// Lists arrive with the 03a contract; until then every screen is in its empty state.
export function Screen({ title, description, action, emptyTitle, emptyBody, notConnectedMessage }: ScreenProps) {
  const create = (
    <WriteGate>
      <Button onClick={() => notConnected(notConnectedMessage)} data-testid="primary-action">
        <PlusIcon />
        {action}
      </Button>
    </WriteGate>
  );
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex max-w-2xl flex-col gap-1">
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="text-muted-foreground">{description}</p>
        </div>
        {create}
      </div>
      <section
        className="flex flex-col items-center gap-3 rounded-xl border border-dashed bg-card px-6 py-12 text-center"
        data-testid="empty-state"
      >
        <InboxIcon className="size-8 text-muted-foreground" aria-hidden />
        <h2 className="text-lg font-medium">{emptyTitle}</h2>
        <p className="max-w-md text-muted-foreground">{emptyBody}</p>
      </section>
    </div>
  );
}
