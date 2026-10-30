// Fails when the frontend contract copy or the generated types drift from the backend contract.
//   npm run check:api   (CI and before every PR; `npm run gen:api` fixes both)
// 03a keeps its copy in mocks/ (10a); 04a, 05a and 06a types come straight from the backend spec
// (K-10bp-0002: one source, no copy to drift).
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const SPECS = [
  { backend: "../backend/openapi/03a.yaml", copy: "mocks/openapi-03a.yaml", types: "lib/api/schema.d.ts" },
  { backend: "../backend/openapi/04a.yaml", copy: null, types: "lib/api/schema-04a.d.ts" },
  { backend: "../backend/openapi/05a.yaml", copy: null, types: "lib/api/schema-05a.d.ts" },
  { backend: "../backend/openapi/06a.yaml", copy: null, types: "lib/api/schema-06a.d.ts" },
];

const problems = [];
const dir = mkdtempSync(join(tmpdir(), "ffcore-api-"));
for (const [index, spec] of SPECS.entries()) {
  if (spec.copy && !readFileSync(spec.backend).equals(readFileSync(spec.copy))) {
    problems.push(`${spec.copy} differs from ${spec.backend}`);
  }
  const source = spec.copy ?? spec.backend;
  const fresh = join(dir, `schema-${index}.d.ts`);
  execFileSync("npx", ["openapi-typescript", source, "-o", fresh], { stdio: "ignore" });
  let current;
  try {
    current = readFileSync(spec.types);
  } catch {
    problems.push(`${spec.types} is missing`);
    continue;
  }
  if (!readFileSync(fresh).equals(current)) {
    problems.push(`${spec.types} is not the output of openapi-typescript for ${source}`);
  }
}
if (problems.length) {
  console.error(`API contract drift:\n- ${problems.join("\n- ")}\nRun: npm run gen:api`);
  process.exit(1);
}
console.log("API contract copies and generated types are current.");
