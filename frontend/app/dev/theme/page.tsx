import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const CHART_TOKENS = [
  "bg-chart-1",
  "bg-chart-2",
  "bg-chart-3",
  "bg-chart-4",
  "bg-chart-5",
  "bg-chart-6",
  "bg-chart-7",
  "bg-chart-8",
] as const;

function Gallery() {
  const t = useTranslations("DevTheme");
  return (
    <div className="flex flex-col gap-4 bg-background p-4 text-foreground">
      <Card>
        <CardHeader>
          <CardTitle>{t("sampleCard")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <p className="text-muted-foreground">{t("sampleText")}</p>
          <div className="flex flex-wrap gap-2">
            <Button>{t("primary")}</Button>
            <Button variant="secondary">{t("secondary")}</Button>
            <Button variant="outline">{t("outline")}</Button>
            <Button variant="destructive">{t("destructive")}</Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge>{t("primary")}</Badge>
            <Badge variant="outline" className="text-success">
              {t("success")}
            </Badge>
            <Badge variant="outline" className="text-warning">
              {t("warning")}
            </Badge>
          </div>
          <Input placeholder={t("inputPlaceholder")} aria-label={t("inputPlaceholder")} />
          <div className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">{t("chart")}</span>
            <div className="flex gap-1">
              {CHART_TOKENS.map((token) => (
                <span key={token} className={`h-6 flex-1 rounded ${token}`} />
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// brief 10: every component in both themes side by side. The .dark wrapper scopes the dark
// token values to its subtree, so the page shows both regardless of the selected theme.
export default function ThemePreviewPage() {
  const t = useTranslations("DevTheme");
  return (
    <main className="flex min-h-screen flex-col gap-4 bg-background p-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("title")}</h1>
        <p className="text-muted-foreground">{t("description")}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <section className="light rounded-xl border bg-background text-foreground" aria-label={t("light")}>
          <h2 className="px-4 pt-4 font-medium">{t("light")}</h2>
          <Gallery />
        </section>
        <section className="dark rounded-xl border bg-background text-foreground" aria-label={t("dark")}>
          <h2 className="px-4 pt-4 font-medium">{t("dark")}</h2>
          <Gallery />
        </section>
      </div>
    </main>
  );
}
