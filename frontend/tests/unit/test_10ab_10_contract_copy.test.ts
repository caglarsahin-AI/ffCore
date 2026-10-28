import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { ACCESS_MODES, ROLES } from "@/lib/access";

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url));
const BACKEND_CONTRACT = here("../../../backend/openapi/03a.yaml");
const FRONTEND_COPY = here("../../mocks/openapi-03a.yaml");

// Enum values of a top-level schema in the OpenAPI YAML (plain text; no YAML dependency).
function schemaEnum(yaml: string, name: string): string[] {
  const block = yaml.split(`\n    ${name}:\n`)[1]?.split(/\n    \S/)[0] ?? "";
  return [...block.matchAll(/^      - (\S+)$/gm)].map((match) => match[1]);
}

describe("test_10ab_10_contract_copy", () => {
  it("keeps the frontend copy byte-identical to the backend contract", () => {
    // The backend file exists in a full checkout; the copy must never drift from it.
    expect(existsSync(BACKEND_CONTRACT)).toBe(true);
    expect(readFileSync(FRONTEND_COPY)).toEqual(readFileSync(BACKEND_CONTRACT));
  });

  it("derives roles and access modes from the contract enums", () => {
    const yaml = readFileSync(FRONTEND_COPY, "utf8");
    expect([...ROLES]).toEqual(schemaEnum(yaml, "Role"));
    expect([...ACCESS_MODES]).toEqual(schemaEnum(yaml, "AccessMode"));
  });
});
