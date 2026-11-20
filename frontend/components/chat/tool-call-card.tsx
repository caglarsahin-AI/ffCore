"use client";

import { ChevronDownIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { toolActivity } from "@/lib/chat-view";
import type { ToolCard } from "@/lib/run-view";

// One tool call of a run, shared by the console test panel (10) and the end user chat (11).
// `panel`: the builder's view, arguments always shown (unchanged from 10b). `chat`: what the
// tool is doing in words ("Running SQL…"), its result summary, the arguments behind "Details".
export function ToolCallCard({ tool, variant }: { tool: ToolCard; variant: "panel" | "chat" }) {
  const t = useTranslations("RunCards");
  const [open, setOpen] = useState(false);
  const prefix = variant === "panel" ? "test" : "chat";
  const activity = toolActivity(tool.name);
  const status =
    tool.result === null ? (
      <Badge variant="outline">{t("toolPending")}</Badge>
    ) : (
      <Badge variant={tool.result.isError ? "destructive" : "secondary"}>
        {tool.result.isError ? t("toolError", { code: tool.result.errorCode ?? t("noCode") }) : t("toolDone")}
      </Badge>
    );
  const truncated = tool.result?.truncated && <span className="text-muted-foreground">{t("toolTruncated", { chars: tool.result.chars ?? 0 })}</span>;
  const args = (
    <pre tabIndex={0} className="overflow-auto rounded bg-muted p-2 text-xs" data-testid={`${prefix}-tool-arguments`}>
      {JSON.stringify(tool.arguments, null, 2)}
    </pre>
  );

  if (variant === "panel") {
    return (
      <div className="flex flex-col gap-1 rounded-lg border p-3 text-sm" data-testid="test-tool-card">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono">{tool.name}</span>
          {status}
          {truncated}
        </div>
        {args}
      </div>
    );
  }
  const running = tool.result === null;
  const label =
    activity.key === "tool" ? t(running ? "activity.tool" : "activityDone.tool", { name: activity.name }) : t(running ? `activity.${activity.key}` : `activityDone.${activity.key}`);
  return (
    <div className="flex flex-col gap-2 rounded-lg border bg-muted/40 p-3 text-sm" data-testid="chat-tool-card" data-state={running ? "running" : tool.result?.isError ? "error" : "done"}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{label}</span>
        {status}
        {truncated}
        <button
          type="button"
          className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-4 hover:underline"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
          data-testid="chat-tool-details"
        >
          {t("details")}
          <ChevronDownIcon className={`size-3 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
        </button>
      </div>
      {open && (
        <>
          <span className="font-mono text-xs text-muted-foreground">{tool.name}</span>
          {args}
        </>
      )}
    </div>
  );
}
