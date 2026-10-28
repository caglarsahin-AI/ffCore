# FFCore Console (frontend)

Next.js 15 App Router, shadcn/ui (`sidebar-07`, `dashboard-01` blocks), next-intl, next-themes.
This page covers package 10a: the console skeleton in the **fake API stage**. Data screens show
their empty state; the real backend is connected in 10a-binding, after 03a is merged.

## Screen map

| Path | Screen | Minimum role | Status (10a) |
|---|---|---|---|
| `/login` | Sign in (email, password) | none | form shell; submitting reports "not connected" |
| `/projects` | Projects | admin | shell + empty state |
| `/projects/{id}/members` | Project members | admin | shell + empty state |
| `/providers` | Providers | admin | shell + empty state |
| `/models` | Models | admin | shell + empty state |
| `/overview` and every other menu item | Later packages (10b-poc, 10c) | see role matrix | "not available yet" page |
| `/dev/theme` | Components in both themes side by side | none | done |

A path outside the user's role renders "You do not have access". This is a UI convenience;
the API enforces roles and read-only access with 403.

## Role matrix

Source of truth: `frontend/lib/navigation.ts` (one table drives the menu and the route guard).
Role order `user < analyst < developer < admin`; a role sees everything of the roles below it.

| Group | Screen | analyst | developer | admin |
|---|---|---|---|---|
| Overview | Overview | ✓ | ✓ | ✓ |
| Build | Knowledge bases, Agents | ✓ | ✓ | ✓ |
| Build | Data sources, Tools, MCP servers | | ✓ | ✓ |
| Build | Providers, Models | | | ✓ |
| Operate | Runs, Approvals, Evaluations | ✓ | ✓ | ✓ |
| Operate | Guardrails, Channels | | ✓ | ✓ |
| Operate | Usage, System status | | | ✓ |
| Administration | Quotas | | ✓ | ✓ |
| Administration | Projects, Users, API keys, Audit, Data retention, Settings | | | ✓ |

`user` (activated in 17) only gets `/chat` and My memory, so the console menu is empty for it.
"Usage" is admin-only here because brief 10 lists it under no smaller role; adjust in
`navigation.ts` if that changes.

**Access mode.** `read` users see the same screens as their role. Every create, save, delete,
publish, approve or run control goes through `<WriteGate>`: in read mode it is disabled, explains
why on hover and to screen readers, and the top bar shows a "Read-only" badge. Theme and language
stay changeable in read mode.

## Language and theme

- English is the source locale (`messages/en.json`), Turkish the translation (`messages/tr.json`).
  Both files have the same keys (unit test). The choice is the `NEXT_LOCALE` cookie, set by the
  language switcher; there is no URL prefix.
- No hard-coded text in JSX (`react/jsx-no-literals`) and no hard-coded colours (ESLint rule in
  `eslint.config.mjs`): only token classes from `styles/tokens.css`.
- Palette "Kurumsal Mavi": navy `#1E3A5F` primary, blue `#2563EB` ring/secondary, `#EEF2F7`
  background; 8 chart colours per theme. Contrast is checked with axe (WCAG 2 AA) in both themes.
- Theme switcher: system / light / dark, stored in `localStorage`, applied before first paint.

## Fake API stage

`FAKE_API=1` (development and Playwright only) reads the signed-in role and access mode from the
`ffcore_fake_session` cookie (`<role>:<access>`, default `admin:edit`); a malformed value shows
"Session unavailable" instead of guessing. Without `FAKE_API` the console shows "Session
unavailable" because `GET /auth/me` is not connected yet.

No request or response body is invented: lists, forms and generated API types arrive with the
03a OpenAPI contract (`openapi-typescript`, msw handlers from the same file).
**Tests in this stage do not prove backend integration.**

## Commands

Node runs only in containers (`docs/gelistirme-ortami.md`).

| Task | Command (from `frontend/`) |
|---|---|
| Lint | `docker compose run --rm frontend npm run lint` |
| Types | `docker compose run --rm frontend npm run typecheck` |
| Unit tests (Vitest) | `docker compose run --rm frontend npm test` |
| Acceptance (Playwright) | `docker run --rm --ipc=host -v "$PWD/..:/work" -w /work/frontend mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea sh -c "npm ci && npx playwright test"` |

Playwright image: `mcr.microsoft.com/playwright:v1.64.1-noble`
(`sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`), matching
`@playwright/test` 1.64.1. Screenshots are written to `docs/images/10a-<screen>-<theme>.png`.

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
