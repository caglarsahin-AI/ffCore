# FFCore Console (frontend)

Next.js 15 App Router, shadcn/ui (`sidebar-07`, `dashboard-01` blocks), next-intl, next-themes.
This page covers packages 10a (console skeleton) and 10a-binding (connected to the 03a backend:
sign-in, projects, members, read-only provider and model lists).

## Screen map

| Path | Screen | Minimum role | Status |
|---|---|---|---|
| `/login` | Sign in (email, password) | none | `POST /auth/login`; wrong email or password: one message |
| `/projects` | Projects | admin | list; create (superadmin only, 03a) |
| `/projects/{id}/members` | Project members | admin | list; role, access, remove; add (superadmin: needs the user list) |
| `/providers` | Providers | superadmin | read-only list; forms in "10a-forms" |
| `/models` | Models of the selected project | admin | read-only list; forms in "10a-forms" |
| `/overview` and every other menu item | Later packages (10b-poc, 10c) | see role matrix | "not available yet" page |
| `/dev/theme` | Components in both themes side by side | none | done |

A path outside the user's role renders "You do not have access". This is a UI convenience;
the API enforces roles and read-only access with 403.

## Role matrix

Source of truth: `frontend/lib/navigation.ts` (one table drives the menu and the route guard).
Role order `user < analyst < developer < admin`; a role sees everything of the roles below it.
The menu uses the highest role from `GET /auth/me`. Tenant screens (Providers, Users, Audit) also
need a superadmin, because the backend serves them only to superadmins (03a `require_superadmin`).

| Group | Screen | analyst | developer | admin |
|---|---|---|---|---|
| Overview | Overview | ✓ | ✓ | ✓ |
| Build | Knowledge bases, Agents | ✓ | ✓ | ✓ |
| Build | Data sources, Tools, MCP servers | | ✓ | ✓ |
| Build | Models | | | ✓ |
| Build | Providers | | | superadmin |
| Operate | Runs, Approvals, Evaluations | ✓ | ✓ | ✓ |
| Operate | Guardrails, Channels | | ✓ | ✓ |
| Operate | Usage, System status | | | ✓ |
| Administration | Quotas | | ✓ | ✓ |
| Administration | Projects, API keys, Data retention, Settings | | | ✓ |
| Administration | Users, Audit | | | superadmin |

`user` (activated in 17) only gets `/chat` and My memory, so the console menu is empty for it.
"Usage" is admin-only here because brief 10 lists it under no smaller role; adjust in
`navigation.ts` if that changes.

**Access mode.** Role and access are per project (03a memberships). A screen uses the project in
its URL, otherwise the project chosen in the top bar; a superadmin is admin with its own access
mode everywhere. `read` users see the same screens and data. Every create, save, delete, publish,
approve or run control goes through `<WriteGate>`: in read mode it is disabled, explains why on
hover and to screen readers, and the top bar shows a "Read-only" badge. Theme, language and
sign-out stay available in read mode. The API is the real guard: a change that reaches it from a
read-only session returns 403 `read_only_access`, shown as "Read-only access".

## Language and theme

- English is the source locale (`messages/en.json`), Turkish the translation (`messages/tr.json`).
  Both files have the same keys (unit test). The choice is the `NEXT_LOCALE` cookie, set by the
  language switcher; there is no URL prefix.
- No hard-coded text in JSX (`react/jsx-no-literals`) and no hard-coded colours (ESLint rule in
  `eslint.config.mjs`): only token classes from `styles/tokens.css`.
- Palette "Kurumsal Mavi": navy `#1E3A5F` primary, blue `#2563EB` ring/secondary, `#EEF2F7`
  background; 8 chart colours per theme. Contrast is checked with axe (WCAG 2 AA) in both themes.
- Theme switcher: system / light / dark, stored in `localStorage`, applied before first paint.

## Backend connection

- **Same origin (C6).** The browser calls `/api/v1/...` on the console origin; `next.config.ts`
  rewrites it to `FFCORE_BACKEND_URL`. The variable is required (build and start fail without it)
  and is fixed at build time; compose passes `http://backend:8000` to the frontend build and
  runtime. The session cookie (`ffcore_session`, HttpOnly, SameSite=Strict, Secure) stays
  first-party; the console origin must be listed in the backend's `CONSOLE_ORIGINS`.
- **Session boundary.** `lib/session.ts` reads `GET /auth/me` on the server with the browser's
  cookie: 401 → sign-in; any other failure → "Backend unavailable" (never shown as a sign-in
  page); a user without memberships → "No project yet".
- **Project selection** is the `ffcore_project` cookie, chosen in the top bar. Nothing is selected
  automatically; project screens without a selection say "Select a project".
- **Contract.** `frontend/mocks/openapi-03a.yaml` is a byte copy of `backend/openapi/03a.yaml`;
  `lib/api/schema.d.ts` is generated from it. `npm run gen:api` refreshes both, `npm run
  check:api` fails on drift. No API type is written by hand.
- **Errors.** Every 4xx carries `{error: {message, type, code}}`. `lib/api/errors.ts` maps codes
  to messages (`read_only_access`, `insufficient_role`, `cross_origin_forbidden`,
  `obo_project_scope`, ...); an unknown code shows the generic message with the code and backend
  text under "Details". Queries do not retry silently.

## Commands

Node runs only in containers (`docs/gelistirme-ortami.md`).

| Task | Command (from `frontend/`) |
|---|---|
| Lint | `docker compose run --rm frontend npm run lint` |
| Types | `docker compose run --rm frontend npm run typecheck` |
| Unit tests (Vitest) | `docker compose run --rm frontend npm test` |
| API contract up to date | `docker compose run --rm frontend npm run check:api` (needs `../backend`) |

### Acceptance tests (Playwright, real backend)

From the repository root, on a throwaway stack (`-p 10ab`; use any project name):

```bash
docker compose -p 10ab --env-file .env.test up -d --wait backend
printf 'dummy-not-secret-e2e-pw' | docker compose -p 10ab --env-file .env.test run --rm -T backend python -m ffcore.cli create-superadmin --email e2e-admin@example.org --full-name "E2E Admin" --password-stdin
docker compose -p 10ab --env-file .env.test --profile e2e run --rm e2e
docker compose -p 10ab --env-file .env.test down -v
```

The superadmin is created once per stack; `tests/e2e/global-setup.ts` creates the other accounts
and projects through the API with a fresh suffix per run. The `e2e` service builds and serves the
console on `localhost:3000` (the origin in `.env.test` `CONSOLE_ORIGINS`) and drives Chromium.
CI runs the same three commands. Playwright image: `mcr.microsoft.com/playwright:v1.64.1-noble`
(`sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`), matching
`@playwright/test` 1.64.1, pinned in `deploy/docker-compose.yml`. Screenshots are written to
`docs/images/10a-<screen>-<theme>.png`.

## Screenshots

| Screen | Light | Dark |
|---|---|---|
| Sign in | ![](images/10a-login-light.png) | ![](images/10a-login-dark.png) |
| Projects | ![](images/10a-projects-light.png) | ![](images/10a-projects-dark.png) |
| Members | ![](images/10a-members-light.png) | ![](images/10a-members-dark.png) |
| Providers | ![](images/10a-providers-light.png) | ![](images/10a-providers-dark.png) |
| Models | ![](images/10a-models-light.png) | ![](images/10a-models-dark.png) |
| Not available yet | ![](images/10a-coming-soon-light.png) | ![](images/10a-coming-soon-dark.png) |
| Theme preview | ![](images/10a-theme-preview-light.png) | ![](images/10a-theme-preview-dark.png) |
