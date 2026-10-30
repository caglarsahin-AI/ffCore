# FFCore Console (frontend)

Next.js 15 App Router, shadcn/ui (`sidebar-07`, `dashboard-01` blocks), next-intl, next-themes.
This page covers packages 10a (console skeleton), 10a-binding (connected to the 03a backend:
sign-in, projects, members), 10a-forms (provider and model forms) and 10b-poc-1 (knowledge bases
and system status).

## Screen map

| Path | Screen | Minimum role | Status |
|---|---|---|---|
| `/login` | Sign in (email, password) | none | `POST /auth/login`; wrong email or password: one message |
| `/projects` | Projects | admin | list; create (superadmin only, 03a) |
| `/projects/{id}/members` | Project members | admin | list; role, access, remove; add (superadmin: needs the user list) |
| `/providers` | Providers | superadmin | list; add, edit, connection test, projects, deactivate / activate |
| `/models` | Models of the selected project | admin | list; edit, delete; add (superadmin: needs the provider list) |
| `/knowledge-bases` | Knowledge bases of the selected project | analyst | list; create (admin) |
| `/knowledge-bases/{id}` | One knowledge base: settings, documents, try search | analyst | edit, delete (admin); upload, delete document, rebuild a layer (analyst+edit); search (read too) |
| `/system-status` | Readiness of the installation (`/readyz`) | admin | read only |
| `/tools` | Tools (MCP and OpenAPI servers) of the selected project | developer | list; register (admin) |
| `/tools/{id}` | One tool: settings, discovered actions, try an action | developer | edit, delete, discover, action switches, try (admin + edit) |
| `/agents` | Agents of the selected project | analyst | list; create (analyst + edit) |
| `/agents/{id}` | Agent wizard and test panel | analyst | edit the draft, publish, new draft, roll back, test run (analyst + edit) |
| `/runs` | Runs of the selected project | analyst | list with filters |
| `/runs/{id}` | One run: summary, answer, events, expert feedback | analyst | cancel (the run's user or an admin), feedback (edit) |
| `/approvals` | Approval queue | analyst | list, pending by default |
| `/approvals/{id}` | One approval | analyst | approve, reject (when `can_decide`) |
| `/overview` and every other menu item | Later packages (10c and others) | see role matrix | "not available yet" page |
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

## Brand

The FFCore mark comes from `assets/icons/` (source PNG renders, no vector source for the product
icon). The console copies are generated by one command, never edited by hand, and a second run
writes the same bytes:

```bash
py -3.12 assets/icons/scripts/make_web_brand.py          # write
py -3.12 assets/icons/scripts/make_web_brand.py --check  # exit 1 if a console copy drifted
```

| File | Used for |
|---|---|
| `app/favicon.ico` (16-64 px) | browser tab; linked by the Next.js file convention |
| `app/icon.png` (48 px, narrow FF) | browser tab, PNG |
| `app/apple-icon.png` (180 px) | iOS home screen |
| `app/manifest.ts` → `/manifest.webmanifest` | name `Home.title`, description `Home.subtitle` (from `messages/en.json`), `theme_color` `#0A192F`, 192 and 512 icons (`public/brand/ffcore-icon-*.png`) |
| `public/brand/ffcore-icon-128.png` | sidebar header, shown at 32 px (narrow FF: the full badge is unreadable that small) |
| `public/brand/ffcore-badge-256.png` | sign-in page, shown at 96 px with the product name and subtitle |
| `public/brand/ffcore-brand-variant-b-512.png` | marketing only; not shown in the console |

Rules: no image with baked-in text on screen. The product name and subtitle are `Home.title` and
`Home.subtitle` ("Enterprise AI Agent Platform" / "Kurumsal Yapay Zekâ Platformu"), and the alt
text is `Brand.logoAlt`, all in `messages/{en,tr}.json`; the page title, the meta description and
the manifest read the same keys. The variant B render has an old English slogan baked in, so it is
not used in the console. The badges have transparent corners and their own dark disc, so light and
dark themes show the same mark. Images go through `next/image`, which is optimised by `sharp` in the
image. The manifest's colour is a literal value because a manifest cannot read CSS variables; the
no-hard-coded-colour rule covers components only.

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
  check:api` fails on drift. No API type is written by hand. 04a, 05a and 06a types
  (`lib/api/schema-{04a,05a,06a}.d.ts`) are generated straight from `backend/openapi/*.yaml`.
  07 approval types (`lib/api/schema-07.d.ts`) likewise.
- **Errors.** Every 4xx carries `{error: {message, type, code}}`. `lib/api/errors.ts` maps codes
  to messages (`read_only_access`, `insufficient_role`, `cross_origin_forbidden`,
  `obo_project_scope`, ...); an unknown code shows the generic message with the code and backend
  text under "Details". Queries do not retry silently.

## Knowledge bases (04a)

- **Contract.** Types come straight from `backend/openapi/04a.yaml` (`lib/api/schema-04a.d.ts`;
  no frontend copy). `npm run gen:api` and `npm run check:api` cover both specs.
- **Roles.** Reading is analyst; creating, changing and deleting a knowledge base is admin (the
  button stays visible, disabled with the reason, for other roles); uploading, deleting a document
  and rebuilding a layer are analyst with edit access. Read mode disables all of them through
  `<WriteGate>`; "Try search" is reading and stays available.
- **Settings.** Defaults are the measured ones (chunk size 400, overlap 0, 5 results). One
  threshold: with the reranker on only the rerank floor applies, so the minimum score field is
  disabled (and not sent, a stored value stays); the knowledge base page names the rule in force.
- **Upload.** Drag and drop or choose files; one request with a progress bar (XHR upload progress,
  same origin and error contract as the other calls). Who may read is an explicit choice: roles
  (analyst pre-selected, the backend default) or every project member (`acl_open`); neither is
  refused in the form. The result lists each file as new, new version or unchanged (identity is
  the file name, the content its sha256).
- **Documents.** Each row shows the status, the layer reached (raw, silver, gold), every gate's
  decision with its reason (a known reason gets a sentence, an unknown one shows its code), a link
  to the original for `duplicate_of`, converter and time, chunks, version and read access. A
  failed document shows its coded explanation and the backend text under "Details". While a
  document is in flight the list refreshes every 2 s and says so; it stops when all are final.
- **Rebuild a layer.** Silver (text and gates) or gold (chunks and vectors), changed documents or
  all; the backend answers how many documents it took.
- **Try search** runs the playground endpoint (logged as `source=playground`) with the caller's
  access: both scores per chunk, the threshold mode and how many chunks it left out, the latency.
- **Not in this package** (no 04a endpoint yet, FOLLOWUP-86): editing a document's access after
  upload, the ingest report, the list of chunks below the rerank floor, re-convert with a preset,
  loaded models, memory and queue figures on the system status page, choosing users for access.

## System status

The page is rendered on the server behind the console sign-in and reads `/readyz` from the
backend's internal address (`FFCORE_BACKEND_URL`); the browser has no route to `/readyz`, because
its detail names model paths (K-10bp-0002). The role is checked on the server before the backend
is read. It shows the overall state and every check with its code explained and the backend
detail as it is. While the models warm up the page refreshes every 5 s. A response outside the
contract is shown as an error, never as "ready". Without model weights the page says
`model_missing` and that weights come only from `make models`, which the operator runs. With
`FAKE_EMBED=1` (tests only) the models check says so.

## Tools, agents, runs and approvals (05a, 06a, 07)

- **Tools.** Developers and above read tools; registering, editing, deleting, discovering, the
  action switches and "Try" are admin + edit (05a). Five identity types (none, bearer, custom
  header, basic, forward the user). Stored secrets come back as `***` and are kept unless the
  identity is changed. Field errors from the backend land on their field: `tool_key_taken`
  (key), `endpoint_url_not_allowed` and the egress codes (address), `header_name_not_allowed`
  (identity). Discovered actions arrive switched off and needing approval; nothing is switched on
  for the user. "Try" takes the arguments as JSON and shows the tool's answer with `truncated`,
  `is_error` and the latency.
- **Agents.** The wizard edits the latest draft's definition (C8) in place and saves it with one
  `PUT`; a published latest version is read-only until "New draft" is used, because 06a never
  edits a published version. Tabs: Identity (name and description are saved at once; the model
  is part of the draft), Instructions (inline text or a Langfuse prompt, exactly one; variables;
  placeholders without a variable are listed while typing, and the backend's
  `variable_undefined` is the final word), Knowledge (`always` or `as a tool`; empty passages and
  minimum score mean the knowledge base default; the minimum score is off where the reranker is
  on), Tools (actions switched on for the tool; the approval list; the approver role, never
  `user`), Safety and limits, Output (free text or a JSON schema) and Publish (versions, publish,
  new draft, roll back to a version published before). Read access disables every field. Agent
  templates (13a) are not offered in the wizard; 13b seeds them (D2).
- **Analysts and tools.** 05a lists tools to developers only, so an analyst sees the actions
  already chosen, read-only, with the reason (FOLLOWUP-100 opens tool reads to analysts).
- **Test panel.** Starts a `channel=test` run of the saved version and follows its stream with
  `fetch` (not `EventSource`: the start is a POST): tokens, tool cards with the masked arguments as
  sent, source cards, fallback and progress notes. An event name the console does not know is
  ignored (C9). A dropped stream reconnects with `Last-Event-ID` (`GET /runs/{id}/stream`) and
  says "reconnecting"; one that cannot be resumed is reported as lost, because the run may still
  be going. An approval is decided on the 07 endpoint (`/approvals/{id}/approve|reject`, D1) and
  the stream continues from `stream_after`; an `ask_user` question is answered with `/resume`.
- **Runs.** Explicit filters (agent, status, channel, feedback pending/given), nothing
  preselected. The detail shows timings, the answer, and the stored events (18 C9 types; an
  unknown type keeps its raw name) with their payloads as stored: tool arguments are already
  masked by the guardrail, the console never fetches raw values. The Langfuse trace id is shown
  as text: the console has no Langfuse address to link to. Expert feedback (F9): a vote and a
  note on a completed run, with edit access.
- **Approvals.** The queue opens on pending approvals; the sidebar badge counts them for the
  selected project. The detail shows the masked arguments, the model's reason and a link to the
  run; the buttons follow `can_decide` (signed-in user, edit access, role at least the assigned
  one) and the backend's 403/409 codes become messages.

## Provider and model forms

- **Driver fields.** The provider form asks `GET /provider-drivers` which uses and configuration
  fields a driver has. Labels and hints come from `messages/*.json` (`ProviderFields.<field>`);
  the backend's own English descriptions are not shown. A field without a message shows its raw
  name, and the acceptance test `test_10af_1` fails until it gets one.
- **Secrets.** Secret fields are password inputs. The API returns them as `***` and the form never
  prefills them: on edit an empty secret field keeps the stored value (the form sends `***`, which
  the backend keeps). The form always sends the whole configuration, because an update replaces
  it. A stored secret cannot be removed from the console yet (FOLLOWUP-80).
- **Connection test.** On add, "Test connection" tests the unsaved values
  (`POST /providers/test`); on edit, "Test saved configuration" tests the stored ones
  (`POST /providers/{id}/test`). A failed test never blocks saving. Drivers without a test say so.
- **Projects.** A provider is always assigned to at least one project; the form refuses an empty
  choice before sending. Deactivating a provider a model still uses is refused
  (`provider_in_use`).
- **Models.** The category comes first and decides which providers are offered (active, assigned
  to the project, serving models or embeddings). "Fill from catalog" looks the model up in
  `GET /model-catalog` for the provider's driver and fills capabilities, input types, context
  window, max output and prices, with the catalog's source and date; a model not in the catalog
  is reported, nothing is guessed. The embedding dimension is measured by the backend; until a
  driver has a probe, an embedding model is refused with `embedding_probe_unavailable`.
- **Upstream API** is chosen explicitly, `chat` by default. `responses` is shown but cannot be
  chosen for a new model: the gateway refuses it (`upstream_api_unsupported`, docs/gateway.md).
  An existing `responses` model stays editable and the list marks it "Not in the gateway".
  `forward_unknown_params` is always sent as `false` (LiteLLM has no per-model switch).
- **Who adds models.** Adding needs the provider list, which only superadmins can read, so a
  project admin sees the add button disabled with that reason and can edit and delete models
  (FOLLOWUP-79: a per-project provider list lifts this).
- A model saved in the console reaches LiteLLM through the 01 reconciler within seconds
  (`<project_key>.<model_key>` in `/model/info`).

## Commands

Node runs only in containers (`docs/gelistirme-ortami.md`).

| Task | Command (from `frontend/`) |
|---|---|
| Lint | `docker compose run --rm frontend npm run lint` |
| Types | `docker compose run --rm frontend npm run typecheck` |
| Unit tests (Vitest) | `docker compose run --rm frontend npm test` |
| API contract up to date | `docker compose run --rm frontend npm run check:api` (needs `../backend`) |

### Acceptance tests (Playwright, real backend)

From the repository root, on a throwaway stack (`-p 10bp1`; use any project name). The provider
tests point at `http://fake-llm:11434`, so the stack allows that host on the command line (the
shell value wins over `.env.test`; no file changes). The list must keep `langfuse-web` from
`.env.test`: since 02 the backend refuses to start when `LANGFUSE_HOST` is not an allowed host. `fake-llm` itself is not started: LiteLLM
does not call a provider when a model is registered, and the connection test reports the failure. If
another stack already uses host port 8000, add `BACKEND_PORT=<free port>` to the `export` line; the
tests reach the backend inside the compose network.

The knowledge base tests run in two stages on the same stack. Stage 1 has no model weights and
`FAKE_EMBED` off, so `/readyz` reports `model_missing`; only the test tagged `@model-missing` runs.
Stage 2 restarts the backend and the ingest worker with `FAKE_EMBED=1` (deterministic stand-in
embedding and reranker, no weights) and runs everything else. Export it rather than prefixing one
command: the `e2e` service depends on the backend, so `run` recreates the backend from the shell's
values, and a prefix-only `FAKE_EMBED=1` is back to 0 by the time the tests start. Weightless formats (measured): PDFs
with a text layer are indexed; DOCX and Markdown need Docling weights and fail with
`model_missing`, which the tests use as the failed-document case. `--workers=1` keeps the waits
stable on a shared machine.

```bash
export ALLOWED_INTERNAL_HOSTS=litellm,langfuse-web,fake-llm FFCORE_VERSION=0.0.0-10bp1
docker compose -p 10bp1 --env-file .env.test up -d --wait --build backend
printf 'dummy-not-secret-e2e-pw' | docker compose -p 10bp1 --env-file .env.test run --rm -T backend python -m ffcore.cli create-superadmin --email e2e-admin@example.org --full-name "E2E Admin" --password-stdin
docker compose -p 10bp1 --env-file .env.test --profile e2e run --rm e2e sh -c "npm ci --no-audit --no-fund && npx playwright test --grep @model-missing --workers=1"
export FAKE_EMBED=1   # keep it set: `run e2e` recreates the backend from the shell's values
docker compose -p 10bp1 --env-file .env.test up -d --wait backend worker
docker compose -p 10bp1 --env-file .env.test --profile e2e run --rm e2e sh -c "npm ci --no-audit --no-fund && npx playwright test --grep-invert @model-missing --workers=1"
docker compose -p 10bp1 --env-file .env.test --profile e2e down -v
```

The superadmin is created once per stack; `tests/e2e/global-setup.ts` creates the other accounts
and projects through the API with a fresh suffix per run. The `e2e` service builds and serves the
console on `localhost:3000` (the origin in `.env.test` `CONSOLE_ORIGINS`) and drives Chromium.
It also gets `LITELLM_URL` and `LITELLM_MASTER_KEY` (the `.env.test` test value) to read
LiteLLM's `/model/info`; the key goes only in a header. CI runs the same commands. Playwright image: `mcr.microsoft.com/playwright:v1.64.1-noble`
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
| Provider form | ![](images/10a-provider-form-light.png) | ![](images/10a-provider-form-dark.png) |
| Model form | ![](images/10a-model-form-light.png) | ![](images/10a-model-form-dark.png) |
| Not available yet | ![](images/10a-coming-soon-light.png) | ![](images/10a-coming-soon-dark.png) |
| Theme preview | ![](images/10a-theme-preview-light.png) | ![](images/10a-theme-preview-dark.png) |
| Knowledge bases | ![](images/10bp1-knowledge-bases-light.png) | ![](images/10bp1-knowledge-bases-dark.png) |
| Knowledge base: documents | ![](images/10bp1-kb-documents-light.png) | ![](images/10bp1-kb-documents-dark.png) |
| Knowledge base: try search | ![](images/10bp1-kb-search-light.png) | ![](images/10bp1-kb-search-dark.png) |
| System status | ![](images/10bp1-system-status-light.png) | ![](images/10bp1-system-status-dark.png) |
| Knowledge base, edit and read mode | ![](images/10bp1-kb-detail-edit.png) | ![](images/10bp1-kb-detail-read.png) |
| Brand: sign in | ![](images/10mrk-login-light.png) | ![](images/10mrk-login-dark.png) |
| Brand: sidebar | ![](images/10mrk-projects-light.png) | ![](images/10mrk-projects-dark.png) |
| Tools | ![](images/10bp2-tools-light.png) | ![](images/10bp2-tools-dark.png) |
| Tool: actions | ![](images/10bp2-tool-detail-light.png) | ![](images/10bp2-tool-detail-dark.png) |
| Agents | ![](images/10bp2-agents-light.png) | ![](images/10bp2-agents-dark.png) |
| Agent wizard: tools, test panel | ![](images/10bp2-agent-wizard-tools-light.png) | ![](images/10bp2-agent-wizard-tools-dark.png) |
| Runs | ![](images/10bp2-runs-light.png) | ![](images/10bp2-runs-dark.png) |
| Run detail | ![](images/10bp2-run-detail-light.png) | ![](images/10bp2-run-detail-dark.png) |
| Approvals | ![](images/10bp2-approvals-light.png) | ![](images/10bp2-approvals-dark.png) |
| Approval detail | ![](images/10bp2-approval-detail-light.png) | ![](images/10bp2-approval-detail-dark.png) |
