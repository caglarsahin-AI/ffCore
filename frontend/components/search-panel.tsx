"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { CheckField, TextField } from "@/components/form-parts";
import { EmptyState, QueryError } from "@/components/screen";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useTestQuery } from "@/lib/api/knowledge-queries";
import type { KnowledgeBase } from "@/lib/api/knowledge-queries";
import { isUnauthenticated } from "@/lib/login-redirect";

// "Try search": the playground endpoint (same search, the caller's ACL, logged as playground).
// Shows both scores per chunk, the threshold that applied and how many chunks it left out. Reading,
// so it is not behind WriteGate.
export function SearchPanel({ projectId, knowledgeBase }: { projectId: string; knowledgeBase: KnowledgeBase }) {
  const t = useTranslations("Search");
  const search = useTestQuery(projectId, knowledgeBase.id);
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(String(knowledgeBase.default_top_k));
  const [hybrid, setHybrid] = useState(knowledgeBase.hybrid);
  const [errors, setErrors] = useState<{ query?: string; topK?: string }>({});

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const k = Number(topK);
    const next = {
      query: query.trim().length === 0 || query.length > 2000 ? t("queryRequired") : undefined,
      topK: /^\d+$/.test(topK.trim()) && k >= 1 && k <= 50 ? undefined : t("topKInvalid"),
    };
    setErrors(next);
    if (next.query || next.topK) return;
    search.mutate({ query: query.trim(), top_k: k, hybrid });
  }

  const result = search.data;
  return (
    <section className="flex flex-col gap-4" data-testid="search-panel">
      <form className="flex flex-col gap-4 rounded-xl border bg-card p-6" onSubmit={onSubmit} noValidate>
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-medium">{t("title")}</h2>
          <p className="text-sm text-muted-foreground">{t("description")}</p>
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="search-query">{t("query")}</Label>
          <Textarea
            id="search-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-invalid={Boolean(errors.query)}
            aria-describedby={errors.query ? "search-query-error" : undefined}
          />
          {errors.query && (
            <p id="search-query-error" className="text-sm text-destructive">
              {errors.query}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <div className="w-32">
            <TextField id="search-top-k" type="number" label={t("topK")} error={errors.topK} value={topK} onChange={setTopK} />
          </div>
          <CheckField id="search-hybrid" label={t("hybrid")} checked={hybrid} onChange={setHybrid} />
          <Button type="submit" disabled={search.isPending} data-testid="search-button">
            {search.isPending ? t("running") : t("run")}
          </Button>
        </div>
      </form>
      {search.isError && !isUnauthenticated(search.error) && <QueryError error={search.error} />}
      {result && (
        <div className="flex flex-col gap-3" data-testid="search-result">
          <div className="flex flex-col gap-1 text-sm">
            <p data-testid="search-summary">{t("summary", { count: result.hits.length, ms: result.latency_ms })}</p>
            <p className="text-muted-foreground" data-testid="search-threshold" data-threshold-mode={result.threshold_mode}>
              {result.threshold_mode === "rerank_floor"
                ? t("thresholdRerank", { count: result.filtered_by_rerank_floor })
                : t("thresholdMinScore", { count: result.filtered_by_min_score })}
            </p>
          </div>
          {result.hits.length === 0 ? (
            <EmptyState title={t("noHitsTitle")} body={t("noHitsBody")} />
          ) : (
            <ol className="flex flex-col gap-3">
              {result.hits.map((hit) => (
                <li key={hit.chunk_id} className="flex flex-col gap-2 rounded-xl border bg-card p-4" data-testid="search-hit">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-medium">{hit.document_name}</span>
                    {hit.page != null && <span className="text-muted-foreground">{t("page", { page: hit.page })}</span>}
                    {hit.chunk_status === "flagged" && <Badge variant="outline">{t("flagged")}</Badge>}
                  </div>
                  <p className="text-sm text-muted-foreground">{hit.breadcrumb}</p>
                  <p className="text-sm whitespace-pre-wrap">{hit.text}</p>
                  <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                    <Score label={t("embedScore")} value={hit.embed_score} empty={t("noScore")} testId="embed-score" />
                    <Score label={t("rerankScore")} value={hit.rerank_score} empty={t("noScore")} testId="rerank-score" />
                  </dl>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  );
}

function Score({ label, value, empty, testId }: { label: string; value: number | null; empty: string; testId: string }) {
  return (
    <div className="flex gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-mono" data-testid={testId}>
        {value == null ? empty : value.toFixed(3)}
      </dd>
    </div>
  );
}
