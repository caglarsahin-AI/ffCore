// Fails when the frontend contract copy or the generated types drift from the backend contract.
//   npm run check:api   (CI and before every PR; `npm run gen:api` fixes both)
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BACKEND = "../backend/openapi/03a.yaml";
const COPY = "mocks/openapi-03a.yaml";
const TYPES = "lib/api/schema.d.ts";

const problems = [];
if (!readFileSync(BACKEND).equals(readFileSync(COPY))) {
  problems.push(`${COPY} differs from ${BACKEND}`);
}
const fresh = join(mkdtempSync(join(tmpdir(), "ffcore-api-")), "schema.d.ts");
execFileSync("npx", ["openapi-typescript", COPY, "-o", fresh], { stdio: "ignore" });
if (!readFileSync(fresh).equals(readFileSync(TYPES))) {
  problems.push(`${TYPES} is not the output of openapi-typescript for ${COPY}`);
}
if (problems.length) {
  console.error(`API contract drift:\n- ${problems.join("\n- ")}\nRun: npm run gen:api`);
  process.exit(1);
}
console.log("API contract copy and generated types are current.");
