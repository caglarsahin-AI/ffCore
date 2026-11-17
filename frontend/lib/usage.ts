import type { UsageRow } from "@/lib/api/governance-queries";

// Usage screens (10c-2 D2). usage_daily rows are per day, model, key and user (03c); the screens
// show them by day and by model. Days are UTC calendar days, as the backend counts them.

const DAY_MS = 86_400_000;
const isoDay = (d: Date) => d.toISOString().slice(0, 10);

// The last `n` calendar days, today included: the default range, written on the screen.
export function lastDays(n: number, now: Date = new Date()): { from: string; to: string } {
  return { from: isoDay(new Date(now.getTime() - (n - 1) * DAY_MS)), to: isoDay(now) };
}

export type UsageGroup = { key: string; input_tokens: number; output_tokens: number; cost_usd: number; requests: number; unpriced_requests: number };

// Costs arrive as decimal strings; summed to 6 places (more than a cent's fraction is noise here).
const round = (v: number) => Math.round(v * 1e6) / 1e6;

function group(rows: UsageRow[], keyOf: (row: UsageRow) => string): UsageGroup[] {
  const out = new Map<string, UsageGroup>();
  for (const row of rows) {
    const key = keyOf(row);
    const g = out.get(key) ?? { key, input_tokens: 0, output_tokens: 0, cost_usd: 0, requests: 0, unpriced_requests: 0 };
    g.input_tokens += row.input_tokens;
    g.output_tokens += row.output_tokens;
    g.cost_usd = round(g.cost_usd + Number(row.cost_usd));
    g.requests += row.requests;
    g.unpriced_requests += row.unpriced_requests;
    out.set(key, g);
  }
  return [...out.values()].sort((a, b) => a.key.localeCompare(b.key));
}

export const byDay = (rows: UsageRow[]) => group(rows, (r) => r.date);
export const byModel = (rows: UsageRow[]) => group(rows, (r) => r.model);
