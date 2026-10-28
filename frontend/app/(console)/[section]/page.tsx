import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { StatusPage } from "@/components/status-page";
import { itemForPath } from "@/lib/navigation";

// Menu screens owned by later packages (10b-poc, 10c): an explicit "not available yet" page,
// never an empty list that looks real. Unknown paths are 404.
export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  const item = itemForPath(`/${section}`);
  if (!item || item.ready) notFound();
  const t = await getTranslations("Nav");
  return <StatusPage kind="comingSoon" screen={t(`items.${item.key}` as "items.projects")} />;
}
