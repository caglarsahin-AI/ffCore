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
| `/tools` | Tools (MCP servers) of the selected project | developer | list; register (admin) |
| `/tools/{id}` | One tool: settings, discovered actions, try an action | developer | edit, delete, discover, action switches, try (admin + edit) |
| `/mcp-servers` | Published MCP servers of the selected project (05b) | developer | list; publish a server (admin + edit) |
| `/mcp-servers/{id}` | One server: settings, operations, monitoring | developer | edit, delete, replace the document, read again / discover, select and rename operations, publish / stop, connection test, add as a tool (admin + edit); monitoring (read too) |
| `/agents` | Agents of the selected project | analyst | list; create (analyst + edit) |
| `/agents/{id}` | Agent wizard and test panel | analyst | edit the draft, publish, new draft, roll back, test run (analyst + edit); publish past the exam gate (admin + edit) |
| `/runs` | Runs of the selected project | analyst | list with filters |
| `/runs/{id}` | One run: summary, answer, events, expert feedback, Add to exam | analyst | cancel (the run's user or an admin), feedback (edit), add to exam (completed run, analyst + edit) |
| `/approvals` | Approval queue | analyst | list, pending by default |
| `/approvals/{id}` | One approval | analyst | approve, reject (when `can_decide`) |
| `/evaluations` | Exam suites of the selected project | analyst | list; create (analyst + edit) |
| `/evaluations/{id}` | One suite: settings, exam start, its exams, compare pick | analyst | edit, delete, start an exam (analyst + edit); compare (read too) |
| `/evaluations/runs/{id}` | One exam: live progress, summary, every item (filter, pages) | analyst | cancel while it runs (analyst + edit) |
| `/evaluations/compare?a=&b=` | Two exams of one suite, item by item | analyst | read only |
| `/overview` | The project at a glance: 30-day usage, approvals waiting, open alerts, newest runs | analyst | read only; open alerts from developer |
| `/usage` | Tokens, cost and requests per day and per model, chosen range | admin | read only |
| `/api-keys` | API keys of the selected project | admin | list (all keys); create with explicit scopes, shown once; revoke (admin + edit) |
| `/quotas` | Quotas and limits, last quota warning per quota | developer | list; create, edit, delete (admin + edit) |
| `/alerts` | Open alerts, history, rules, notification settings | developer | acknowledge (developer + edit); rules and notification settings (admin + edit); installation alerts (superadmin) |
| `/retention` | Data retention of the installation | superadmin | policies, dry run, real run behind a confirmation, past passes (superadmin + edit) |
| every other menu item | Later packages (14, 15, 16 and others) | see role matrix | "not available yet" page |
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
| Operate | Alerts | | ✓ | ✓ |
| Operate | Guardrails, Channels | | ✓ | ✓ |
| Operate | Usage, System status | | | ✓ |
| Administration | Quotas | | ✓ | ✓ |
| Administration | Projects, API keys, Settings | | | ✓ |
| Administration | Users, Audit, Data retention | | | superadmin |

`user` (activated in 17) only gets `/chat` and My memory, so the console menu is empty for it.
"Usage" is admin-only here because brief 10 lists it under no smaller role; adjust in
`navigation.ts` if that changes.

10c-2 choices (KARARLAR "10c-2 plan kararları"): **Data retention** is superadmin-only because the
backend serves it, reads included, only to superadmins (S1). **API keys** stay admin-only (R10.5)
although the backend lets an analyst manage their own keys; a screen for that would be a separate
decision (S2). **Alerts** is a new Operate item: developers see and acknowledge, rules and
notification settings are an admin's (S3); a superadmin switches the screen to the installation's
own alerts (service down, disk and memory) and its SMTP settings (S4). Controls a role cannot use
stay visible and disabled with the reason, like read mode.

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

## MCP servers (05b)

The screen publishes an OpenAPI document or a remote MCP server as an MCP server of this
installation at `/mcp/<key>/` (docs/araclar.md "Publish an MCP server") and is the only way an
OpenAPI service becomes a tool: the tool form no longer offers an OpenAPI kind (05b S5).

- **Who.** The menu item is developer and up (R10.5). Every change is a project admin's, because
  the 05b API allows changes only to `admin` (KARARLAR "10c-3 plan kararları" S1): a developer
  sees the same pages with each change control disabled and the reason "Only a project admin can
  publish or change MCP servers"; read mode disables them through `<WriteGate>` as everywhere.
- **Publish.** Key (unique in the installation), name, source (OpenAPI document or remote MCP
  server), upstream address and identity (none, bearer, custom header, basic; secrets come back
  masked and are kept unless the identity is changed), who can call (platform agents only, or
  agents and API keys with `tools_invoke`), guardrail mode and policy key. An OpenAPI document is
  pasted or read from a local file (YAML or JSON). Fetching it from a URL is not offered: there
  is no backend endpoint for it, and the browser would make an outbound request outside the
  egress policy. Refusals land on their field (`mcp_server_key_taken`, `upstream_url_refused`,
  `egress_*`, `openapi_path_invalid` under the document, ...).
- **Operations.** Every operation of the document is listed with method and path. One that cannot
  be published keeps its row, has no selection and shows its reason (`openapi_path_invalid`,
  `operation_id_missing`, `ref_cycle`, ...; an unknown reason is shown as its code). Select the
  operations to serve and, optionally, the tool name and description the model sees (empty keeps
  the operation's own); "Save selection" sends the selection and only the changed names. A
  server starts as a draft: "Publish" serves it, "Stop serving" stops it. "Replace document"
  (`PUT /spec`) keeps selection and names by operation name; "Read the document again" (OpenAPI)
  or "Discover tools" (remote MCP) reads the catalog again.
- **Connection test** shows reachable or not, the upstream's HTTP status (for OpenAPI any HTTP
  answer counts as reachable), the tools a remote server lists, latency and the refusal code.
- **Add as a tool** creates the 05a tool at the server's own address with `forward_user` and links
  to it; discover its actions there (they start switched off and needing approval).
- **Monitoring** (tab, read too): the last 24 hours from `GET .../calls?hours=24` as the backend
  gives them (requests, not OK, blocked, p50 and p95 latency) and the last 50 calls with time,
  operation, status, code, latency and caller; a call of an agent run links to the run. Status:
  **OK** the upstream answered; **Error** the request was made but failed (`invalid_arguments`,
  `upstream_http_404`, ...); **Denied** refused before any request left (`openapi_path_invalid`,
  `upstream_origin_mismatch`, `egress_not_allowlisted`, ...); **Blocked** stopped by the
  guardrail. "Not OK" counts error, denied and blocked. Changes to the server are in the audit log
  (`create_mcp_server`, `update_mcp_server`, `update_mcp_server_spec`, `discover_mcp_server`,
  `test_mcp_server`, `add_mcp_server_tool`, `delete_mcp_server`); the audit list is the Audit
  screen's (later package).

## Governance (03c): overview, usage, API keys, quotas, alerts, retention

- **Overview.** Usage of the last 30 UTC days (requests, tokens, cost; requests without a price
  are counted apart), approvals waiting, open alerts (developer and up) and the 10 newest runs.
  No run total: there is no count endpoint and a number read from a capped list would be wrong (S5).
- **Usage.** `GET /usage` for the chosen range (default the last 30 days, shown), by day (chart
  and table) and by model. A range that ends before it starts is refused before it is sent.
- **API keys.** The form preselects no scope; `impersonate` needs allowed networks (CIDR), checked
  before sending as the backend does. The raw key is shown once with a copy button and is gone on
  "I have saved the key" or a reload. Revoke asks first. Keys are managed only from a console
  session (`requires_console_session`).
- **Quotas.** Windows, tokens and budgets; only filled limits are sent (empty = no limit), and a
  quota with no limit is refused. "block" refuses a call over the limit (429); "warn" lets it
  through and records a `quota_warn` alert, which is how an exceeded quota shows on the screen
  (the last warning per quota; a block leaves no record). The scope is fixed once created.
- **Alerts.** Open alerts (not acknowledged) and history, newest 500 (backend limit, said on the
  screen when reached). The header badge counts open alerts of the selected project for developer
  and up, every 30 s and after an acknowledgement. Rule kinds come from `/alert-kinds` (only kinds
  something emits); an e-mail rule needs recipients; `budget_threshold` takes thresholds in
  percent. Notification settings: SMTP (password masked, kept when left as is), sender, default
  webhook, and a test send that reports the delivery status.
- **Retention.** Policies per data class with per-project overrides, the scheduled mode
  (`RETENTION_DRY_RUN`) and audit deletion (`RETENTION_AUDIT_DROP_ENABLED`) as configured. "Dry
  run" shows the counts a pass would delete. "Delete now" is a real deletion that ignores
  `RETENTION_DRY_RUN` (FOLLOWUP-130): it starts only from a confirmation dialog that says so, with
  cancel as the default. Every pass is listed with its trigger and mode.

## Evaluations (09)

- **Suites.** Analysts and above read suites; creating, editing, deleting and starting an exam
  need edit access (09 `Editor = analyst, write`). The form sends only what is filled: a blank
  dataset name, pass threshold or scorer value leaves the backend's documented default
  (`<project_key>.<key>`, `EVAL_PASS_THRESHOLD`, judge 4, semantic 0.8). `approve_tools` is an
  explicit switch with its consequence written next to it; the exam never approves anything.
  Binding an agent makes the suite gate that agent's publish.
- **Items.** Exam questions live in the suite's Langfuse dataset (09 brief, ARCH-09). The console
  does not list or edit them (K-10C1-0002 S2); it adds one from a completed run with "Add to
  exam" on the run page. The backend masks the question and the expectation with the agent's
  egress policy first, and the console shows what it did (`masking`: `none`, `regex` with person
  names stored as written, or `regex+ner`; `masked_fields`). Refusals keep their code:
  `run_input_blocked`, `expected_would_be_masked`, `ner_unavailable`.
- **Exams.** "Start exam" takes the suite's gated agent (or one the user picks) and a version with
  a visible default: the draft when there is one, else the published version (S4). The exam page
  follows `GET /eval-runs/{id}/stream` with `fetch`: `progress` counts, then `done`; an unknown
  event name is logged and skipped. A silent stream counts as dropped: the backend sends
  `progress` every 2 s, so an attempt with nothing for 6 s (`STALL_MS`, `lib/eval-stream.ts`) is
  ended, which covers a half-open connection after a backend kill or an idle proxy drop. As soon
  as an attempt ends without `done` the page says "reconnecting" and reads the exam with `GET` at
  once and every few seconds while the stream is reopened; a stream that speaks again takes over,
  one that cannot be reopened is reported as lost and `GET` goes on. Status and counts come from
  whichever arrived last, stream or `GET`; a failed `GET` is shown above the exam and does not
  bring back an older status. Nothing is guessed about how it ended. Event streams are sent with
  `Cache-Control: no-cache, no-transform` so that the console's proxy does not gzip-buffer them
  (docs/degisiklikler.md). The summary is shown as written: pass rate against the threshold, scored / items,
  completeness (`complete=false` says the exam did not finish unattended), not-run reasons with
  their code (`approval_required`, `partial:<code>` for some repeats, an unknown code raw),
  errors (`judge_out_of_time`, `judge_failed:*`, `advance_failed:*`), outcome and style counts,
  warm-up apart from latency. Below it, every item of the exam from
  `GET /eval-runs/{id}/items` (10c-2, FOLLOWUP-185): failed, not run, passed, not yet scored, with
  each scorer's value, the outcome, the not-run code next to its meaning and links to the item's
  runs; a status filter and pages of 50 use the endpoint's own parameters. `EvalRunOut.summary` is
  the typed `EvalSummary` in the contract; the console still reads it with a narrow schema and
  shows "could not be read" with the failing field rather than an empty result.
- **Compare.** Two completed exams of one suite, picked on the suite page (read access too):
  summary differences, each exam's completeness, the configuration warning (`config_differs`),
  item changes (`fixed`, `regressed`, `same`, `not_comparable`, `only_a`, `only_b`) and the 10
  worst. Another pair shows `eval_runs_not_comparable` with its message.
- **Publish gate.** A publish the gate refuses (409 `eval_gate_failed`) lists each bound suite
  and its reason, read from the message (`<key>=<reason>`; FOLLOWUP-176); an unknown reason or
  another message shape is shown as written. "Publish past the gate" is for an admin with edit
  access and needs a reason; others see it disabled with why (backend 403
  `force_requires_admin`, 422 `force_reason_required`). The versions table links each version to
  the exam that opened its gate (`eval_run_id`); "—" when there is none (no bound suite, or a
  forced publish).

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

From the repository root, on a throwaway stack (`-p 10bp2`; use any project name). Each stack sets
its own host ports (`BACKEND_PORT`, `FRONTEND_PORT`; K-INIT-0020: the defaults 8000/3000 are not
used, so stacks never collide); the tests reach the backend inside the compose network. The
`test` profile starts the two fakes the agent tests need: `fake-llm` (chat on port 9999; model id
`tool-default` calls the first offered tool once) and `ticket-desk` (MCP server with
`send_reply`, which needs approval). `ALLOWED_INTERNAL_HOSTS` is the `.env.test` list plus
`fake-llm`: the provider connection tests make the backend call it directly (the agent runs reach
it through LiteLLM, which needs no entry). The shell value wins over `.env.test`; no file changes.
Runs need the `platform_rules` prompt in Langfuse, so `seed-prompts` runs once per stack.

The knowledge base tests run in two stages on the same stack. Stage 1 has no model weights and
`FAKE_EMBED` off, so `/readyz` reports `model_missing`; only the test tagged `@model-missing` runs.
Stage 2 restarts the backend and the ingest worker with `FAKE_EMBED=1` (deterministic stand-in
embedding and reranker, no weights) and runs everything else. Export it rather than prefixing one
command: the `e2e` service depends on the backend, so `run` recreates the backend from the shell's
values, and a prefix-only `FAKE_EMBED=1` is back to 0 by the time the tests start (FOLLOWUP-93).
Weightless formats (measured): PDFs with a text layer and (since 04b-2) Markdown are indexed;
DOCX needs Docling weights and fails with `model_missing`, which the tests use as the failed-document case. The
stand-in reranker scores the share of query words found in a passage, so questions about the
Turkish samples are asked in Turkish. `--workers=1` keeps the waits stable on a shared machine.

```bash
export ALLOWED_INTERNAL_HOSTS=litellm,langfuse-web,mcp-search,mcp-sql,ticket-desk,fake-llm FFCORE_VERSION=0.0.0-10bp2 BACKEND_PORT=18010 FRONTEND_PORT=13010
docker compose -p 10bp2 --env-file .env.test --profile test up -d --wait --build --pull never
docker compose -p 10bp2 --env-file .env.test --profile test --profile e2e up --build --pull never --no-start --no-deps e2e
docker compose -p 10bp2 --env-file .env.test --profile tools run --rm --no-deps tools make seed-prompts
printf 'dummy-not-secret-e2e-pw' | docker compose -p 10bp2 --env-file .env.test run --rm --no-deps -T backend python -m ffcore.cli create-superadmin --email e2e-admin@example.org --full-name "E2E Admin" --password-stdin
docker compose -p 10bp2 --env-file .env.test --profile test --profile e2e run --rm e2e npx playwright test --grep @model-missing --workers=1
export FAKE_EMBED=1   # keep it set: `run e2e` recreates the backend from the shell's values
docker compose -p 10bp2 --env-file .env.test --profile test up -d --wait backend worker
docker compose -p 10bp2 --env-file .env.test --profile test --profile e2e run --rm e2e npx playwright test --grep-invert @model-missing --workers=1
docker compose -p 10bp2 --env-file .env.test --profile test --profile e2e down -v
```

The superadmin is created once per stack; `tests/e2e/global-setup.ts` creates the other accounts
and projects through the API with a fresh suffix per run. The `e2e` service builds and serves the
console on `localhost:3000` (the origin in `.env.test` `CONSOLE_ORIGINS`) and drives Chromium.
It also gets `LITELLM_URL` and `LITELLM_MASTER_KEY` (the `.env.test` test value) to read
LiteLLM's `/model/info`; the key goes only in a header. CI runs the same commands. Playwright image: `mcr.microsoft.com/playwright:v1.64.1-noble`
(`sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`), matching
`@playwright/test` 1.64.1, pinned in `deploy/docker-compose.yml` (build argument
`PLAYWRIGHT_IMAGE` of the `e2e` service).

**Dependencies (FOLLOWUP-220).** The `e2e` service runs `ffcore/e2e:<FFCORE_VERSION>`, built from
`frontend/Dockerfile.e2e`: the pinned Playwright image plus `npm ci` of
`frontend/package-lock.json`. Build it once per stack and lock file with the second line of the
sequence (`up --build --pull never --no-start --no-deps e2e`; never `docker compose build`, which
reaches the registries for base image metadata). That build is the only step that downloads
packages; the runs do not. The stack's `e2e_node_modules` volume is filled from the image when it
is empty, also after `down -v`. When `package-lock.json` changes, the container stops with
`e2e_deps_stale` instead of installing anything: rebuild the image as above and `down -v` (or
remove the volume `<project>_e2e_node_modules`) so the volume is filled again.

**Screenshots (FOLLOWUP-221).** The screenshot tests write only when `E2E_SCREENSHOT_DIR` is set
(`frontend/tests/e2e/screenshots.ts`); empty, the default, writes nothing, so a run on the
repository checkout (the `e2e` service mounts it at `/work`) never rewrites `docs/images`. To
refresh the docs images on purpose: `export E2E_SCREENSHOT_DIR=../docs/images` before the
`run` (an existing directory inside the container, relative to `/work/frontend`; a missing one
fails the test). Prefer the relative value: Git Bash rewrites an absolute `/work/…` value into a
Windows path (`C:/Program Files/Git/work/…`) unless `MSYS_NO_PATHCONV=1` is set. The images
are `docs/images/<package>-<screen>-<theme>.png` (10a, 10bp1, 10mrk, 10bp2, 10c1, 10c2, 10c3,
11, 14). The main gate script needs no change: it does not set the variable, so the gate's e2e
stage leaves the checkout's `docs/images` as it is.

**Memory tests (14).** Memory can be turned on only with the installation's NER model, so the
`test_14_*` specs need `NER_MODEL`/`NER_REVISION` exported in the shell (the values of
`.env.example`; `run e2e` recreates the backend from them, `.env.test` stays as it is) and the
weights in the stack's own `model_cache` volume. Each stack has its own volume, so copy them
from the machine's filled cache instead of downloading (no network):
`docker compose -p <project> --env-file .env.test --profile tools run --rm --no-deps -T -v ffcore_model_cache:/src:ro tools sh -c 'mkdir -p /models/huggingface/hub && cp -a /src/huggingface/hub/models--akdeniz27--bert-base-turkish-cased-ner /models/huggingface/hub/'`.
Without them the specs are skipped with the reason `memory_requires_ner`, never passed.

The exam tests (10c-1) need nothing more than the agent tests: Langfuse and the background
worker's advancer are default services, fake-llm answers "hello", and each test adds its exam
items from a completed run (from-run), so no `seed-eval` is needed. Without network access the
runs need nothing: the packages are in the `e2e` image (only its build needs the registry).

### MCP servers (10c-3): the fake upstream

05b refuses every platform service as an upstream (`RESERVED_HOSTS`: litellm, ticket-desk, ...),
so the MCP tests serve a fake Superset from the e2e container itself (KARARLAR "10c-3 plan
kararları" S2). The container runs with a fixed name, the stack lists that name in
`ALLOWED_INTERNAL_HOSTS` for the run only, and `E2E_UPSTREAM_HOST` tells the tests the name;
servers that are never called use `http://superset.example.com/api`, allowed by
`EGRESS_ALLOWLIST` (creation checks the address, it does not resolve it). Nothing of this exists
in an installation, and no file changes. Without `E2E_UPSTREAM_HOST` the two specs that need the
fake (`test_10c3_1`, `test_10c3_3`) fail loudly.

```bash
export ALLOWED_INTERNAL_HOSTS=litellm,langfuse-web,mcp-search,mcp-sql,ticket-desk,fake-llm,ffcore-10c3-e2e-upstream EGRESS_ALLOWLIST=superset.example.com FAKE_EMBED=1
docker compose -p ffcore-10c3 --env-file .env.test --profile test up -d --wait --pull never
docker compose -p ffcore-10c3 --env-file .env.test --profile test --profile e2e up --build --pull never --no-start --no-deps e2e
docker compose -p ffcore-10c3 --env-file .env.test --profile test --profile e2e run --rm --name ffcore-10c3-e2e-upstream -e E2E_UPSTREAM_HOST=ffcore-10c3-e2e-upstream e2e npx playwright test --grep-invert @model-missing --workers=1
```

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
| Overview, edit mode | ![](images/10c2-overview-edit-light.png) | ![](images/10c2-overview-edit-dark.png) |
| Overview, read mode | ![](images/10c2-overview-read-light.png) | ![](images/10c2-overview-read-dark.png) |
| Usage, edit mode | ![](images/10c2-usage-edit-light.png) | ![](images/10c2-usage-edit-dark.png) |
| Usage, read mode | ![](images/10c2-usage-read-light.png) | ![](images/10c2-usage-read-dark.png) |
| API keys, edit mode | ![](images/10c2-api-keys-edit-light.png) | ![](images/10c2-api-keys-edit-dark.png) |
| API keys, read mode | ![](images/10c2-api-keys-read-light.png) | ![](images/10c2-api-keys-read-dark.png) |
| Quotas, edit mode | ![](images/10c2-quotas-edit-light.png) | ![](images/10c2-quotas-edit-dark.png) |
| Quotas, read mode | ![](images/10c2-quotas-read-light.png) | ![](images/10c2-quotas-read-dark.png) |
| Alerts, edit mode | ![](images/10c2-alerts-edit-light.png) | ![](images/10c2-alerts-edit-dark.png) |
| Alerts, read mode | ![](images/10c2-alerts-read-light.png) | ![](images/10c2-alerts-read-dark.png) |
| Data retention, edit mode | ![](images/10c2-retention-edit-light.png) | ![](images/10c2-retention-edit-dark.png) |
| Data retention, read mode | ![](images/10c2-retention-read-light.png) | ![](images/10c2-retention-read-dark.png) |
| MCP servers, publish form | ![](images/10c3-mcp-servers-light.png) | ![](images/10c3-mcp-servers-dark.png) |
| MCP server, edit mode | ![](images/10c3-mcp-server-edit-light.png) | ![](images/10c3-mcp-server-edit-dark.png) |
| MCP server, read mode | ![](images/10c3-mcp-server-read-light.png) | ![](images/10c3-mcp-server-read-dark.png) |
| MCP monitoring | ![](images/10c3-mcp-monitoring-light.png) | ![](images/10c3-mcp-monitoring-dark.png) |
| Exam suites | ![](images/10c1-suites-light.png) | ![](images/10c1-suites-dark.png) |
| New suite | ![](images/10c1-suite-new-light.png) | ![](images/10c1-suite-new-dark.png) |
| Suite: exam start, exams | ![](images/10c1-suite-light.png) | ![](images/10c1-suite-dark.png) |
| Exam result | ![](images/10c1-exam-light.png) | ![](images/10c1-exam-dark.png) |
| Compare exams | ![](images/10c1-compare-light.png) | ![](images/10c1-compare-dark.png) |
| Add to exam | ![](images/10c1-from-run-light.png) | ![](images/10c1-from-run-dark.png) |
| Publish gate refusal | ![](images/10c1-gate-light.png) | ![](images/10c1-gate-dark.png) |
| Suite, edit and read mode | ![](images/10c1-suite-edit.png) | ![](images/10c1-suite-read.png) |
