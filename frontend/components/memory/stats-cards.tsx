"use client";

import { useFormatter, useTranslations } from "next-intl";

import { QueryError } from "@/components/screen";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { MEMORY_KINDS, useMemoryStats } from "@/lib/api/memories-queries";
import { useMembers } from "@/lib/api/queries";

// The administrator's view of memory (14-2 D6; brief 14): counts per member and kind, use and
// delete numbers, never a text (the API's statistics carry none; S4). The principle is said on the
// screen: administrators cannot see what is remembered.
export function MemoryStats({ projectId }: { projectId: string }) {
  const t = useTranslations("memory");
  const format = useFormatter();
  const stats = useMemoryStats(projectId);
  const members = useMembers(projectId);
  const name = (userId: string) => {
    const member = (members.data ?? []).find((m) => m.user_id === userId);
    return member ? member.full_name || member.email : userId;
  };
  const kindsOf = (byKind: Record<string, number>) =>
    MEMORY_KINDS.filter((k) => byKind[k])
      .map((k) => `${t(`kinds.${k}`)} ${format.number(byKind[k])}`)
      .join(", ");

  return (
    <section className="flex flex-col gap-4" aria-labelledby="memory-stats-title">
      <h2 id="memory-stats-title" className="font-medium">
        {t("stats.title")}
      </h2>
      <p className="rounded-lg border border-dashed p-3 text-sm" data-testid="memory-principle">
        {t("stats.principle")}
      </p>
      {stats.isError && <QueryError error={stats.error} />}
      {stats.isSuccess && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Stat id="memory-stat-active" label={t("stats.active")} value={format.number(stats.data.active)} />
            <Stat id="memory-stat-archived" label={t("stats.archived")} value={format.number(stats.data.archived)} />
            <Stat
              id="memory-stat-use-rate"
              label={t("stats.useRate")}
              value={stats.data.use_rate === null || stats.data.use_rate === undefined ? t("stats.unreadable") : format.number(stats.data.use_rate, { style: "percent" })}
            />
            <Stat id="memory-stat-deletes" label={t("stats.deletes")} value={format.number(stats.data.delete_events)} />
            <Stat id="memory-stat-opted-out" label={t("stats.optedOut")} value={format.number(stats.data.opted_out_users)} />
          </div>
          {stats.data.users.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("stats.none")}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("stats.member")}</TableHead>
                  <TableHead>{t("stats.active")}</TableHead>
                  <TableHead>{t("stats.byKind")}</TableHead>
                  <TableHead>{t("stats.used")}</TableHead>
                  <TableHead>{t("stats.archived")}</TableHead>
                  <TableHead>{t("stats.deletes")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stats.data.users.map((u) => (
                  <TableRow key={u.user_id} data-testid="memory-stats-user">
                    <TableCell>{name(u.user_id)}</TableCell>
                    <TableCell>{format.number(u.active)}</TableCell>
                    <TableCell>{kindsOf(u.by_kind)}</TableCell>
                    <TableCell>{format.number(u.used)}</TableCell>
                    <TableCell>{format.number(u.archived)}</TableCell>
                    <TableCell>{format.number(u.delete_events)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
    </section>
  );
}

function Stat({ id, label, value }: { id: string; label: string; value: string }) {
  return (
    <Card data-testid={id}>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl">{value}</CardTitle>
      </CardHeader>
    </Card>
  );
}
