import type { ServerStatus } from "@/lib/api/mcp-servers-queries";

// Badge look of a server status: served (active) stands out, a draft is quiet, disabled is outlined.
export function statusVariant(status: ServerStatus): "default" | "secondary" | "outline" {
  return status === "active" ? "default" : status === "disabled" ? "outline" : "secondary";
}
