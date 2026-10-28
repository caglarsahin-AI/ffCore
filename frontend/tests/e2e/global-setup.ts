import { PASSWORD, SUPERADMIN } from "./fixtures";
import type { Account, Fixture } from "./fixtures";

// Builds the accounts and projects of one run through the real 03a API, called directly on the
// backend (server side, no browser Origin). Fails loudly with the next step if the stack is not ready.
export default async function globalSetup() {
  const base = process.env.FFCORE_BACKEND_URL;
  if (!base) throw new Error("FFCORE_BACKEND_URL is not set (compose e2e service sets it)");
  const run = Date.now().toString(36);

  const login = await fetch(`${base}/api/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: SUPERADMIN.email, password: PASSWORD }),
  });
  if (login.status !== 200) {
    throw new Error(
      `superadmin login returned ${login.status}. Create the e2e superadmin once per stack (docs/onyuz.md).`,
    );
  }
  const cookie = (login.headers.get("set-cookie") ?? "").split(";")[0];
  const me = (await login.json()) as { user: { id: string } };

  async function call<T>(method: string, path: string, body: unknown): Promise<T> {
    const response = await fetch(`${base}/api/v1${path}`, {
      method,
      headers: { "content-type": "application/json", cookie },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`${method} ${path} → ${response.status} ${await response.text()}`);
    return (await response.json()) as T;
  }

  async function user(name: string, superadminAccess?: "edit" | "read"): Promise<Account> {
    const email = `e2e-${name}-${run}@example.org`;
    const created = await call<{ id: string }>("POST", "/users", {
      email,
      full_name: `E2E ${name}`,
      password: PASSWORD,
      is_superadmin: Boolean(superadminAccess),
      superadmin_access: superadminAccess ?? null,
    });
    return { email, id: created.id };
  }

  async function project(name: string) {
    const key = `e2e-${name}-${run}`;
    const created = await call<{ id: string }>("POST", "/projects", { key, name: `E2E ${name}`, description: null });
    return { id: created.id, key };
  }

  const member = (projectId: string, userId: string, role: "admin" | "analyst", access: "edit" | "read") =>
    call("POST", `/projects/${projectId}/members`, { user_id: userId, role, access });

  const fixture: Fixture = {
    run,
    superadmin: { email: SUPERADMIN.email, id: me.user.id },
    reader: await user("reader", "read"),
    projectAdmin: await user("project-admin"),
    analyst: await user("analyst"),
    stale: await user("stale"),
    lonely: await user("lonely"),
    memberCandidate: await user("candidate"),
    expiring: await user("expiring"),
    alpha: await project("alpha"),
    beta: await project("beta"),
  };
  await member(fixture.alpha.id, fixture.projectAdmin.id, "admin", "edit");
  await member(fixture.beta.id, fixture.projectAdmin.id, "admin", "read");
  await member(fixture.alpha.id, fixture.analyst.id, "analyst", "edit");
  await member(fixture.alpha.id, fixture.stale.id, "admin", "edit");
  await member(fixture.alpha.id, fixture.expiring.id, "admin", "edit");
  process.env.E2E_FIXTURE = JSON.stringify(fixture);
}
