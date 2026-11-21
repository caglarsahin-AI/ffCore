"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { FieldShell } from "@/components/form-parts";
import { useAccess } from "@/components/session-provider";
import { useReportError } from "@/components/use-report-error";
import { WriteGate } from "@/components/write-gate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useUpdateAgent } from "@/lib/api/agents-queries";
import type { Agent } from "@/lib/api/agents-queries";
import { accentTones, isAccent } from "@/lib/portal-accent";
import type { Theme } from "@/lib/portal-accent";

const EXAMPLES = 3;

// The agent's chat portal settings (11-2, K-11-0005 S2): agent level, not versioned, so this tab
// sits outside the wizard's version fieldset and saves on its own with PATCH (analyst + edit; a
// published agent's are edited here too). Read access sees the values with the controls disabled.
// The preview shows the light and dark tones the chat derives from the accent (S3).
export function PortalTab({ projectId, agent }: { projectId: string; agent: Agent }) {
  const t = useTranslations("Agents.wizard.portal");
  const { canWrite } = useAccess(projectId);
  const report = useReportError();
  const update = useUpdateAgent(projectId, agent.id);
  const stored = agent.portal_config;
  const [welcome, setWelcome] = useState(stored?.welcome ?? "");
  const [examples, setExamples] = useState<string[]>(Array.from({ length: EXAMPLES }, (_, i) => stored?.examples?.[i] ?? ""));
  const [accent, setAccent] = useState(stored?.accent ?? "");
  const [saved, setSaved] = useState(false);
  const accentOk = accent === "" || isAccent(accent);

  function save() {
    const portal_config = {
      welcome: welcome.trim() || null,
      examples: examples.map((e) => e.trim()).filter(Boolean),
      accent: accent || null,
    };
    setSaved(false);
    update.mutate({ portal_config }, { onSuccess: () => setSaved(true), onError: report });
  }

  return (
    <div className="flex flex-col gap-4" data-testid="portal-tab">
      <div className="flex flex-col gap-1">
        <h2 className="font-medium">{t("title")}</h2>
        <p className="text-sm text-muted-foreground">{t("intro")}</p>
      </div>
      <FieldShell id="portal-welcome" label={t("welcome")} hint={t("welcomeHint")}>
        {(a11y) => (
          <Textarea {...a11y} value={welcome} onChange={(e) => setWelcome(e.target.value)} maxLength={500} disabled={!canWrite} className="min-h-20" data-testid="portal-welcome" />
        )}
      </FieldShell>
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">{t("examplesHint")}</p>
        {examples.map((value, i) => (
          <FieldShell key={i} id={`portal-example-${i + 1}`} label={t("example", { n: i + 1 })}>
            {(a11y) => (
              <Input
                {...a11y}
                value={value}
                maxLength={200}
                disabled={!canWrite}
                onChange={(e) => setExamples((current) => current.map((v, j) => (j === i ? e.target.value : v)))}
                data-testid={`portal-example-${i + 1}`}
              />
            )}
          </FieldShell>
        ))}
      </div>
      <FieldShell id="portal-accent" label={t("accent")} hint={t("accentHint")}>
        {(a11y) => (
          <Input
            {...a11y}
            aria-invalid={!accentOk}
            aria-describedby={[a11y["aria-describedby"], accentOk ? null : "portal-accent-error"].filter(Boolean).join(" ") || undefined}
            value={accent}
            onChange={(e) => setAccent(e.target.value.trim())}
            placeholder={t("accentPlaceholder")}
            disabled={!canWrite}
            className="max-w-40 font-mono"
            data-testid="portal-accent"
          />
        )}
      </FieldShell>
      {!accentOk && (
        <p id="portal-accent-error" className="text-sm text-destructive" data-testid="portal-accent-error">
          {t("accentInvalid")}
        </p>
      )}
      <Preview accent={accentOk && accent ? accent : null} />
      <div className="flex items-center gap-3">
        <WriteGate projectId={projectId}>
          <Button onClick={save} disabled={!accentOk || update.isPending} data-testid="portal-save">
            {t("save")}
          </Button>
        </WriteGate>
        {saved && (
          <span className="text-sm text-muted-foreground" role="status" data-testid="portal-saved">
            {t("saved")}
          </span>
        )}
      </div>
    </div>
  );
}

// Both themes side by side, each in its own theme scope (`.light` / `.dark`), with the tone the
// chat will use; it says when the tone is not exactly the picked colour.
function Preview({ accent }: { accent: string | null }) {
  const t = useTranslations("Agents.wizard.portal");
  const tones = accent ? accentTones(accent) : null;
  const adjusted = tones !== null && (tones.light.adjusted || tones.dark.adjusted);
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-medium">{t("preview")}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        {(["light", "dark"] as Theme[]).map((theme) => (
          <div key={theme} className={`${theme} flex flex-col gap-2 rounded-lg border bg-background p-3 text-foreground`} data-testid={`portal-preview-${theme}`}>
            <span className="text-xs text-muted-foreground">{t(theme === "light" ? "previewLight" : "previewDark")}</span>
            <div className="flex justify-end">
              <span
                className={`rounded-2xl px-4 py-2 text-sm ${tones ? "" : "bg-primary text-primary-foreground"}`}
                style={tones ? { background: tones[theme].background, color: tones[theme].foreground } : undefined}
              >
                {t("previewQuestion")}
              </span>
            </div>
          </div>
        ))}
      </div>
      {adjusted && (
        <p className="text-xs text-muted-foreground" data-testid="portal-adjusted">
          {t("adjusted")}
        </p>
      )}
    </div>
  );
}
