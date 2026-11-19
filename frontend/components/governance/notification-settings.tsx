"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { CheckField, FieldShell, SELECT, TextField } from "@/components/form-parts";
import { QueryError } from "@/components/screen";
import { Button } from "@/components/ui/button";
import { useReportError } from "@/components/use-report-error";
import { useNotificationSettings, useSaveNotificationSettings, useTestNotification } from "@/lib/api/governance-queries";
import type { AlertScope, NotificationSettings, NotificationTestResult } from "@/lib/api/governance-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

type Gate = (control: React.ReactElement<{ disabled?: boolean }>) => React.ReactNode;

// Where e-mail and webhook alerts go (03c): SMTP, sender, default webhook, and a test send. The
// SMTP password comes back masked ("***"); sending the mask keeps the stored one (backend).
export function NotificationSettingsPanel({ scope, gate }: { scope: AlertScope; gate: Gate }) {
  const tState = useTranslations("State");
  const settings = useNotificationSettings(scope);
  if (settings.isPending || (settings.isError && isUnauthenticated(settings.error))) return <p className="text-muted-foreground">{tState("loading")}</p>;
  if (settings.isError) return <QueryError error={settings.error} />;
  return (
    <div className="flex flex-col gap-6">
      <SettingsForm key={settings.data.updated_at ?? "new"} scope={scope} settings={settings.data} gate={gate} />
      <TestSend scope={scope} gate={gate} />
    </div>
  );
}

function SettingsForm({ scope, settings, gate }: { scope: AlertScope; settings: NotificationSettings; gate: Gate }) {
  const t = useTranslations("Alerts.notifications");
  const tState = useTranslations("State");
  const save = useSaveNotificationSettings(scope);
  const report = useReportError();
  const smtp = settings.smtp;
  const [host, setHost] = useState(smtp?.host ?? "");
  const [port, setPort] = useState(smtp ? String(smtp.port) : "587");
  const [username, setUsername] = useState(smtp?.username ?? "");
  const [password, setPassword] = useState(smtp?.password ?? "");
  const [starttls, setStarttls] = useState(smtp?.starttls ?? true);
  const [from, setFrom] = useState(settings.from_address ?? "");
  const [webhook, setWebhook] = useState(settings.default_webhook_url ?? "");
  const [portError, setPortError] = useState<string>();

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const portNumber = Number(port);
    if (host.trim() && !Number.isInteger(portNumber)) {
      setPortError(t("portInvalid"));
      return;
    }
    setPortError(undefined);
    try {
      await save.mutateAsync({
        smtp: host.trim() ? { host: host.trim(), port: portNumber, username: username.trim() || null, password: password || null, starttls } : null,
        from_address: from.trim() || null,
        default_webhook_url: webhook.trim() || null,
      });
      toast.success(tState("saved"));
    } catch (error) {
      report(error);
    }
  }

  return (
    <form className="flex flex-col gap-4 rounded-xl border bg-card p-6" onSubmit={onSubmit} noValidate data-testid="notification-form">
      <h2 className="text-lg font-medium">{t("title")}</h2>
      <p className="text-sm text-muted-foreground">{t("description")}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField id="notify-smtp-host" label={t("host")} hint={t("hostHint")} value={host} onChange={setHost} />
        <TextField id="notify-smtp-port" label={t("port")} hint={t("portHint")} type="number" value={port} onChange={setPort} error={portError} />
        <TextField id="notify-smtp-user" label={t("username")} value={username} onChange={setUsername} />
        <TextField id="notify-smtp-password" label={t("password")} hint={t("passwordHint")} type="password" value={password} onChange={setPassword} />
        <TextField id="notify-from" label={t("from")} value={from} onChange={setFrom} />
        <TextField id="notify-webhook" label={t("webhook")} hint={t("webhookHint")} value={webhook} onChange={setWebhook} />
      </div>
      <CheckField id="notify-starttls" label={t("starttls")} checked={starttls} onChange={setStarttls} />
      <div>
        {gate(
          <Button type="submit" disabled={save.isPending} data-testid="notification-save" data-write="">
            {t("save")}
          </Button>,
        )}
      </div>
    </form>
  );
}

function TestSend({ scope, gate }: { scope: AlertScope; gate: Gate }) {
  const t = useTranslations("Alerts.notifications");
  const send = useTestNotification(scope);
  const report = useReportError();
  const [channel, setChannel] = useState<"email" | "webhook">("email");
  const [recipient, setRecipient] = useState("");
  const [result, setResult] = useState<NotificationTestResult | null>(null);

  function onSend() {
    setResult(null);
    send.mutate({ channel, recipient: recipient.trim() || null }, { onSuccess: setResult, onError: report });
  }

  return (
    <section className="flex flex-col gap-4 rounded-xl border bg-card p-6" data-testid="notification-test">
      <h2 className="text-lg font-medium">{t("testTitle")}</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <FieldShell id="notify-test-channel" label={t("testChannel")}>
          {(a11y) => (
            <select {...a11y} className={SELECT} value={channel} onChange={(e) => setChannel(e.target.value as "email" | "webhook")}>
              <option value="email">{t("email")}</option>
              <option value="webhook">{t("webhookChannel")}</option>
            </select>
          )}
        </FieldShell>
        <TextField id="notify-test-recipient" label={t("testRecipient")} hint={t("testRecipientHint")} value={recipient} onChange={setRecipient} />
      </div>
      <div>
        {gate(
          <Button type="button" variant="outline" onClick={onSend} disabled={send.isPending} data-testid="notification-test-send" data-write="">
            {t("testSend")}
          </Button>,
        )}
      </div>
      {result && (
        <p className="text-sm" role="status" data-testid="notification-test-result">
          {t("testResult", { channel: result.channel, status: result.status })}
        </p>
      )}
    </section>
  );
}
