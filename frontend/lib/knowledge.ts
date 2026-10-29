import type { components } from "@/lib/api/schema-04a";

// Knowledge base UI state derived from the 04a contract. Pure functions; the runtime lists below
// must match the contract enums (test_10bp1_14_knowledge_status).
type S = components["schemas"];
export type DocumentStatus = S["DocumentStatus"];
export type GateStatus = S["GateStatus"];
export type ReadinessState = S["ReadyzOut"]["status"];
export type Layer = "raw" | "silver" | "gold";

export const DOCUMENT_STATUSES = [
  "pending",
  "converting",
  "gated",
  "chunking",
  "embedding",
  "indexed",
  "skipped",
  "failed",
  "timeout",
] as const satisfies readonly DocumentStatus[];
export const GATE_STATUSES = ["ok", "flagged", "skipped"] as const satisfies readonly GateStatus[];
export const READINESS_STATES = ["ready", "warming", "not_ready"] as const satisfies readonly ReadinessState[];

const ACTIVE: ReadonlySet<DocumentStatus> = new Set(["pending", "converting", "gated", "chunking", "embedding"]);

export function isActiveDocument(status: DocumentStatus): boolean {
  return ACTIVE.has(status);
}

type Gate = { status: GateStatus | null; reason: string | null };
type LayeredDocument = { status: DocumentStatus; gate1: Gate; gate2: Gate };

// raw → silver (converted text passed Kapı 1) → gold (chunks and vectors). The highest layer the
// document reached; a skipped or failed document stays on the layer where it stopped.
export function documentLayer(document: LayeredDocument): Layer {
  if (document.status === "indexed") return "gold";
  if (document.gate1.status !== null) return "silver";
  return "raw";
}

// Gate reason codes from backend knowledge/scope.py (Kapı 0) and knowledge/gates.py (Kapı 1-2).
// Two carry an argument after a colon. Unknown codes are shown as they are (key null).
const GATE_REASONS = {
  binary: "binary",
  out_of_scope: "outOfScope",
  video_disabled: "videoDisabled",
  libreoffice_unavailable: "libreofficeUnavailable",
  too_large: "tooLarge",
  empty: "empty",
  too_short: "tooShort",
  template: "template",
  language_not_allowed: "languageNotAllowed",
  title_only: "titleOnly",
  boilerplate: "boilerplate",
  code_heavy: "codeHeavy",
  no_prose: "noProse",
  embedding_truncated: "embeddingTruncated",
  duplicate_of: "duplicateOf",
  data_dump: "dataDump",
} as const;
export type GateReasonKey = (typeof GATE_REASONS)[keyof typeof GATE_REASONS];
export const GATE_REASON_KEYS = Object.values(GATE_REASONS);

export function gateReason(reason: string): { key: GateReasonKey | null; code: string; arg?: string } {
  const colon = reason.indexOf(":");
  const code = colon < 0 ? reason : reason.slice(0, colon);
  const key = code in GATE_REASONS ? GATE_REASONS[code as keyof typeof GATE_REASONS] : null;
  if (!key) return { key: null, code: reason };
  return colon < 0 ? { key, code } : { key, code, arg: reason.slice(colon + 1) };
}

// Readiness and document error codes with a dedicated explanation (04a core/readiness.py,
// knowledge/ingest.py). Others show the code and the backend detail.
const READINESS_CODES = {
  warming: "warming",
  warmup_failed: "warmupFailed",
  model_missing: "modelMissing",
  context_configuration_invalid: "contextConfigurationInvalid",
  embed_dim_mismatch: "embedDimMismatch",
  vector_store_unavailable: "vectorStoreUnavailable",
} as const;
export type ReadinessCodeKey = (typeof READINESS_CODES)[keyof typeof READINESS_CODES];
export const READINESS_CODE_KEYS = Object.values(READINESS_CODES);

export function readinessCodeKey(code: string): ReadinessCodeKey | null {
  return code in READINESS_CODES ? READINESS_CODES[code as keyof typeof READINESS_CODES] : null;
}

// Document.error is "<code>: <message>" (knowledge/ingest.py).
export function documentError(error: string): { code: string | null; key: ReadinessCodeKey | null; text: string } {
  const match = /^([a-z][a-z0-9_]*): ([\s\S]*)$/.exec(error);
  if (!match) return { code: null, key: null, text: error };
  return { code: match[1], key: readinessCodeKey(match[1]), text: match[2] };
}

// Explicit refresh: the document list polls only while a document is in flight; the readiness
// page refreshes only while the models warm up.
export const DOCUMENTS_POLL_MS = 2000;
export const READINESS_REFRESH_MS = 5000;

export function documentsRefetchInterval(documents: { status: DocumentStatus }[] | undefined): number | false {
  return documents?.some((document) => isActiveDocument(document.status)) ? DOCUMENTS_POLL_MS : false;
}

// A document reached a final status since the last poll (or arrived final): the knowledge base
// counts changed, so its summary and list are refreshed (review r1 MINOR-1). The first load is not
// a change.
export function documentsFinished(
  previous: { id: string; status: DocumentStatus }[] | undefined,
  current: { id: string; status: DocumentStatus }[],
): boolean {
  if (!previous) return false;
  const before = new Map(previous.map((document) => [document.id, document.status]));
  return current.some((document) => {
    if (isActiveDocument(document.status)) return false;
    const was = before.get(document.id);
    return was === undefined || isActiveDocument(was);
  });
}

export function readinessNeedsRefresh(status: ReadinessState): boolean {
  return status === "warming";
}
