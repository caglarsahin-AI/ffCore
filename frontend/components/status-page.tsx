import { CircleSlashIcon, ConstructionIcon, PlugZapIcon } from "lucide-react";
import { useTranslations } from "next-intl";

type Props =
  | { kind: "forbidden" }
  | { kind: "sessionUnavailable" }
  | { kind: "comingSoon"; screen: string };

// Full-page explanations: no access, screen not built yet, no session.
export function StatusPage(props: Props) {
  const tForbidden = useTranslations("Forbidden");
  const tSoon = useTranslations("ComingSoon");
  const tSession = useTranslations("Session");

  const [Icon, title, body] =
    props.kind === "forbidden"
      ? [CircleSlashIcon, tForbidden("title"), tForbidden("body")]
      : props.kind === "comingSoon"
        ? [ConstructionIcon, tSoon("title", { screen: props.screen }), tSoon("body")]
        : [PlugZapIcon, tSession("unavailableTitle"), tSession("unavailableBody")];

  return (
    <section
      className="mx-auto flex max-w-lg flex-col items-center gap-3 py-16 text-center"
      data-testid={`status-${props.kind}`}
    >
      <Icon className="size-10 text-muted-foreground" aria-hidden />
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="text-muted-foreground">{body}</p>
    </section>
  );
}
