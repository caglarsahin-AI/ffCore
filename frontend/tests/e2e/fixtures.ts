// Test accounts for the e2e stack (docker compose -p 10ab --env-file .env.test). Not secrets:
// dummy values in the same style as .env.test, valid only on a throwaway local stack.
export const PASSWORD = "dummy-not-secret-e2e-pw";

// Created once per stack with the CLI (docs/onyuz.md "Acceptance tests"); everything else is made
// through the API by global-setup.ts with a fresh suffix per run, so runs never collide.
export const SUPERADMIN = { email: "e2e-admin@example.org", fullName: "E2E Admin" };

export type Account = { email: string; id: string };
export type Fixture = {
  run: string;
  superadmin: Account;
  reader: Account; // superadmin with access "read"
  projectAdmin: Account; // admin+edit on alpha, admin+read on beta, not a superadmin
  analyst: Account; // analyst+edit on alpha
  stale: Account; // admin+edit on alpha; set to read during a test (kabul 5)
  lonely: Account; // no membership
  memberCandidate: Account; // not a member anywhere, added in the members test
  expiring: Account; // admin+edit on alpha; its session is revoked during a test (401 path)
  alpha: { id: string; key: string };
  beta: { id: string; key: string };
};

export function fixture(): Fixture {
  const raw = process.env.E2E_FIXTURE;
  if (!raw) throw new Error("E2E_FIXTURE is not set: global-setup.ts did not run");
  return JSON.parse(raw) as Fixture;
}
