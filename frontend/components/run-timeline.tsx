"use client";

import { useFormatter, useTranslations } from "next-intl";

import { ListState } from "@/components/screen";
import { useRunEvents } from "@/lib/api/runs-queries";

// The run's stored events (06a run_events, C9: 18 types) in order. Payloads are shown as the
// backend stored them: tool arguments arrive already masked, nothing raw is fetched or rebuilt.
// A type this console does not know is shown with its raw name, never hidden.
export function RunTimeline({ projectId, runId, live }: { projectId: string; runId: string; live: boolean }) {
  const t = useTranslations("Runs");
  const format = useFormatter();
  const events = useRunEvents(projectId, runId, live);

  return (
    <ListState query={events} empty={{ title: t("noEventsTitle"), body: t("noEventsBody") }}>
      {(rows) => (
        <ol className="flex flex-col gap-2" data-testid="run-timeline">
          {rows.map((event) => {
            const key = `eventTypes.${event.type}`;
            const label = t.has(key as never) ? t(key as never) : event.type;
            return (
              <li key={event.seq} className="rounded-lg border p-3 text-sm" data-testid="run-event" data-type={event.type}>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-mono text-muted-foreground">{event.seq}</span>
                  <span className="font-medium">{label}</span>
                  <span className="text-muted-foreground">{format.dateTime(new Date(event.ts), { timeStyle: "medium" })}</span>
                  {event.iteration !== null && <span className="text-muted-foreground">{t("iteration", { n: event.iteration })}</span>}
                </div>
                {Object.keys(event.payload).length > 0 && (
                  <pre tabIndex={0} className="mt-2 max-h-64 overflow-auto rounded bg-muted p-2 text-xs" data-testid="run-event-payload">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </ListState>
  );
}
