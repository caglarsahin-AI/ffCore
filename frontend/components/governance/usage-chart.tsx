"use client";

import { useTranslations } from "next-intl";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { ChartConfig } from "@/components/ui/chart";
import type { UsageGroup } from "@/lib/usage";

// Daily tokens of a project (input and output stacked), from the usage rows grouped by day. Colors
// are theme tokens (--chart-1/2), readable in both themes.
export function UsageChart({ days }: { days: UsageGroup[] }) {
  const t = useTranslations("Usage");
  const config = {
    input_tokens: { label: t("inputTokens"), color: "var(--chart-1)" },
    output_tokens: { label: t("outputTokens"), color: "var(--chart-2)" },
  } satisfies ChartConfig;
  if (days.length === 0) return <p className="text-sm text-muted-foreground">{t("noUsage")}</p>;
  return (
    <ChartContainer config={config} className="aspect-auto h-64 w-full" role="img" aria-label={t("chartLabel")}>
      <BarChart data={days} margin={{ left: 8, right: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="key" tickLine={false} axisLine={false} tickMargin={8} minTickGap={24} />
        <YAxis tickLine={false} axisLine={false} width={56} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Bar dataKey="input_tokens" stackId="tokens" fill="var(--color-input_tokens)" />
        <Bar dataKey="output_tokens" stackId="tokens" fill="var(--color-output_tokens)" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ChartContainer>
  );
}
