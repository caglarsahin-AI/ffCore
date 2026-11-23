# Data sources (FFCore Knowledge, package 16)

A data source feeds one knowledge base from a live system on a schedule, instead of manual
uploads: what is added or changed at the source is indexed, what is really deleted there leaves
the index, and the source's permissions are carried to the documents. 16-1 ships the core and
the **network folder** source, 16-2 **Confluence** and **Jira** (Server/Data Center and Cloud);
SharePoint/OneDrive and the console screen follow in 16-3. The word "connector" is not used
(TERMINOLOGY): a source is a *data source*, its code a *driver*.

| Source | Profiles | Package |
|---|---|---|
| Network folder (SMB/NFS mount) | llmaas, airgap | 16-1 |
| Confluence, Jira Server/Data Center | llmaas, airgap (internal host) | 16-2 |
| Atlassian Cloud, SharePoint Online | llmaas only (internet; refused with `OFFLINE=true`) | 16-2, 16-3 |

## How a sync runs: three layers

Every run is one row in `sync_runs` and one layer. A source has at most one active (queued or
running) run; a second request is `409 sync_running`.

- **raw** (sync worker, queue `sync`): the only layer that talks to the source. It takes the
  source's own item count before and after listing, stores each item's bytes as given
  (`raw/<project>/<kb>/<kind>/<space>/<item>/payload.<ext>`), decides attachments from the
  listing before downloading anything (Kapı 0, below) and maps permissions. An item whose bytes
  did not change is `unchanged`. A **full** run then applies the safe delete rule; a **delta**
  run never deletes on a source without deletion records (network folder, Confluence, Jira).
  Changed items are handed to silver automatically.
- **silver** (ingest worker): the driver renders the stored payload into the converter's input
  (no network) and the knowledge-base pipeline converts, gates, chunks and embeds it
  (docs/bilgi-tabani.md). Delta: only the items silver has not seen in their current version.
  Full: every item again from raw (after a converter or gate change).
- **gold** (ingest worker): rechunk and re-embed the source's documents from silver (after a
  chunking change); chunks whose text did not change keep their vector (`reused`).

Neither silver nor gold sends a request to the source. The raw layer's cursor (`source_sync_state`)
moves to the run's start time only when the listing finished and no item failed, so the next
delta looks at a failed item again.

```bash
make sync PROJECT=<project key> SOURCE=<source key> LAYER=raw MODE=full
make sync PROJECT=<project key> SOURCE=<source key> LAYER=gold MODE=full
```

`make sync` queues the run like the screen's "Sync now" and prints its id. A queued run can be
cancelled; a running raw run stops between two items (no deletion, no cursor move).

## Schedule

A source syncs on one of four fixed choices (no cron strings): `manual`, `hourly` (minute),
`daily` (`HH:MM`), `weekly` (weekday 0 = Monday, `HH:MM`). Times are **UTC**. The default for a
new source is `daily` at `02:00` UTC (out of office hours; ingest slows chat on CPU). A scheduled
run is a raw **delta**, except when the source's last completed full run is
`FULL_SYNC_EVERY_DAYS` old (default 7; `0` = never): then that scheduled run is a **full** run
under the safe delete rule. A full run is what sees deletions without tombstones and permissions
narrowed at the source, so they reach the index within a week without anyone starting one;
otherwise a full run is started by a person. A source
that has never synced is not started by the schedule: run the first full sync yourself, before
users rely on the knowledge base. The sync worker checks schedules once a minute; a slot missed
while it was down runs once. A run left `running` longer than the job limit (13 hours) is failed
`run_abandoned` so the source can sync again.

## Safe delete (full runs)

A full run deletes the items the source no longer lists only when **all** of these hold:

1. the listing finished without an error (`listing_failed` otherwise);
2. the source's count before and after the listing are known, equal, and equal to the items
   seen (`count_mismatch` otherwise; this is never forced: a listing cut in the middle must not
   look like a mass deletion);
3. the share to delete, over what the source holds now, is not above the limit
   (`PRUNE_MAX_RATIO`, default 0.2; a source can set its own). Above it the run is
   `prune_refused`: nothing is deleted, the run row and the log say so, and a `prune_refused`
   alert fires **when the project has an alert rule for it** (03c: alerts are rule driven; create
   one with `POST /api/v1/projects/{id}/alert-rules {"kind": "prune_refused", "channel": "ui"}`
   or e-mail/webhook). A project admin can repeat the full run with `force_prune` (audited) when
   the disappearance is real.

Deletion order: the vector store first (if it fails nothing else is touched, `prune_failed`),
then the document rows, the runs that showed them (`source_deleted`) and their retained text,
then silver and raw files. An attachment file another item borrows (`shared_from`) moves to that
item instead of being removed.

Why: when the service account loses a permission or the mount drops, a naive full scan would
count the whole knowledge base as "deleted at the source" (PayCore measurement, D4).

## Kapı 0 for attachments (before download)

Decided from the listing (name, size, date, type), recorded per attachment in
`source_attachments`, never silently dropped:

| Reason | When |
|---|---|
| `binary`, `out_of_scope` | executables; archives, spreadsheets, csv/tsv, sql, images, wsdl |
| `too_large` | over 500 MB (5 MB for plain text/log/json/xml/yaml); also checked while streaming |
| `stale` | older than `ATTACHMENT_MIN_DATE` (unset = no date rule) |
| `shared_from` | the same name and size was already downloaded for another item of the source |
| `gone` | the source answered 404 for the file |

A downloaded attachment is converted with its page and joins the page's text under
`Ek: <file name>`; a data dump (log, stack trace, JSON) is recorded `data_dump:<kind>` and not
indexed, while the page still is.

## Permissions (ACL)

The source reports groups for each item; `acl_mappings` maps a group to one platform role or one
project member. The platform has no groups: they are expanded at sync time into
`documents.acl_roles` / `acl_users`, and every raw run maps the stored groups again (a mapping
change reaches all documents at the next run, without asking the source).

- A group without a mapping gives **admin only**; an item none of whose groups is mapped is
  readable by admins only. Open a source on purpose with a `*` row (every item).
- Confluence and Jira groups are a **union** (each group the source lists may read the
  item), so a restriction is reported **instead of** the broad group, never beside it: see
  the Confluence and Jira sections.
- Network folders report their folder chain (`folder:/`, `folder:/a`, `folder:/a/b`); the
  **deepest mapped folder wins**, so `folder:/contracts/board` → `admin` closes that subtree even
  when `folder:/` → `analyst`.
- Source members are matched to platform users by e-mail; an address without a user gives no
  access and is counted (`acl_user_unmatched`).

Mappings are changed by project admins (`PUT …/data-sources/{id}/acl-mappings`).

## Network folder

**Who registers it.** One share (`FS_SOURCES_BASE`) serves the whole installation, so a network-
folder source is registered, and its root or filters changed, **only by a superadmin**
(`403 fs_source_superadmin_only` for project roles). The superadmin knows the share and decides
which folder each project may index; otherwise any project's developer or admin could register
`.` and index every department's files. Project roles then sync it, map its permissions, watch
its runs and read it. Confluence, Jira and SharePoint sources bring the project's own service
account and are registered by the project admin (16-2, 16-3).

**Writing to the share decides content.** Whoever may write into the mounted share decides what
gets indexed: a symlink out of the base is refused, but a hard link to a file elsewhere on the
same file system cannot be told apart from a regular file. Mount only shares whose writers you
would let choose indexed content, and keep the base on its own file system.

Mount the share on the host and point `FS_SOURCES_HOST_DIR` at it; it is mounted read-only at
`/data/sources` (`FS_SOURCES_BASE`) in the backend and the sync worker. A source's `root` is a
path **relative** to that directory; an absolute path, `..` or a symlink out is refused at
registration (`400 path_outside_base`) and again for every file at sync time (the file is
skipped and listed with `path_outside_base`; a symlink inside the base is `symlink_refused`).
So `.env`, the application and the storage tree cannot be indexed. `include_globs` /
`exclude_globs` select files by their relative path (shell patterns, `*` crosses `/`).

A delta lists files whose modification time is newer than the cursor and compares their bytes.
A file that keeps an old modification time (moved, renamed, copied with its original date, e.g.
`cp -p`, `robocopy /COPY:DAT`) is not seen by a delta; scheduled runs are deltas, so run a
**full** sync after such a change (it also finds deleted files). A folder named like a personnel-data source
(`prsim…`) is refused (`prsim_requires_ner`) until names are masked (08).

## Confluence

Set up with three things (K-16-0003): the address, a service account credential and an
optional scope.

| Field | Server/Data Center (`deployment: server`) | Cloud (`deployment: cloud`) |
|---|---|---|
| `config.base_url` | `https://wiki.example.org[/context]` | `https://<site>.atlassian.net` |
| `secret` | `{"token": "<personal access token>"}` | `{"email": "...", "api_token": "..."}` |
| `config.space_keys` | empty = every space the account sees | same |
| `config.attachments_enabled` | `true` | same |

A credential that does not fit the deployment is refused (`422 secret_invalid`); a base URL
that points at the platform itself is `400 endpoint_is_platform`. Cloud needs outbound HTTP:
refused with `OFFLINE=true` (`source_kind_unavailable`); with the egress overlay the sync
worker goes through the forward proxy (add the site to `EGRESS_ALLOWLIST`). A Server/Data
Center host inside the network goes into `ALLOWED_INTERNAL_HOSTS`.

**Cloud attachments.** Confluence Cloud answers an attachment download with a redirect to its
media host; add `api.media.atlassian.com` to `EGRESS_ALLOWLIST` in llmaas. Redirects are not
followed for any source (`max_redirects=0`), so without it each Confluence Cloud attachment
fails loudly with an `egress_*` code in the run (the page itself is indexed). Jira asks for
attachments with `redirect=false` and gets the bytes directly. Any other answer than a 2xx to a
download is `attachment_download_failed` (a 404 is `attachment_gone`), never a file.

- **What is read:** pages (`type=page`) with their storage-format body; Server/Data Center
  lists bodies with the listing (one request per 50 pages), Cloud lists with the v1 CQL search
  and reads each changed page's body from the v2 API. The count is the search's `totalSize`.
- **Delta:** only pages modified since the last run, `lastmodified >= now("-Nm")` with N =
  minutes since the cursor + 10 (no time zone in the query; the 10 minutes cover clock skew).
  A delta never deletes; a page deleted, archived or out of scope leaves in a **full** run under
  the safe delete rule. Adding a read restriction does not change the page's version, so a
  delta does not see it: **a narrowed permission reaches the index with a full run** (the
  weekly scheduled full, `FULL_SYNC_EVERY_DAYS`, or one you start). Space keys are quoted in
  the query (personal spaces `~user` work).
- **Document:** the body is turned into Markdown (headings, lists, tables, code blocks kept;
  `toc`, `children`, `pagetree`, attachment galleries removed; `include`d pages are not expanded
  because they are indexed themselves; an unknown macro keeps its rich body or is dropped and
  counted; `script`/`style` bodies are dropped). User mentions are dropped (the person's name
  is not indexed). The breadcrumb is `space › parent pages › page`; the search hit's
  `source_url` is the page in Confluence.
- **Attachments:** listing metadata first (newest version per title), Kapı 0 before any
  download; the same name and size on two pages is downloaded and indexed once.
- **Permissions:** a page with no read restriction (on itself or any parent page) reports
  `space:<KEY>`; map it to open the space. A restricted page reports only the restriction's
  `group:<name>` and `user:<name>`; restrictions on several levels report who is named on every
  level, and none in common means admins only.

## Jira

| Field | Value |
|---|---|
| `config.base_url`, `secret` | as Confluence |
| `config.jql` | empty = every issue the account sees; otherwise a filter such as `project = OPS`. Leave `ORDER BY` out (`422 config_invalid` `jql_order_by`): the sync orders by `updated` |
| `config.attachments_enabled` | `true` |

- **Document:** one per issue, `# KEY: summary`, a metadata block (project, type, status,
  priority, resolution, labels, created, updated), `## Description`, `## Resolution` and one
  `## Comment <n> (<date>)` per comment, so chunks break at comment boundaries. Jira wiki code
  blocks and headings become Markdown. **Person name fields and mentions are not indexed**
  (assignee, reporter, comment authors, `[~user]` mentions; in Confluence `ri:user` mentions):
  the issue's knowledge is the problem and its solution, not who said it. Names written as
  plain text in a description or comment are not recognised here; that is 08's name masking
  (NER), when the knowledge base uses it. `source_url` is `<base_url>/browse/<KEY>`.
- **Restricted comments stay out:** a comment visible only to a role or a group
  (`visibility`) and a service desk internal note (`jsdPublic: false`) are not in the document
  (the issue's permission is wider than theirs); they stay in the raw layer as the API answered.
  Comment numbers count the comments in the document.
- **Count:** Server/Data Center asks the search for `total`; Jira Cloud has only an approximate
  count, so the driver counts by a key-only listing (two light scans per full run) to keep the
  safe delete rule exact.
- **Delta:** `updated >= "-Nm"` (as Confluence). Deleted issues leave in a full run; a
  security level added to an issue updates it, so the next delta carries the new permission.
- **Permissions:** `project:<KEY>`; an issue with a security level reports only
  `security:<KEY>/<level>` (map it to the role that may see that level; named per project
  because level names repeat across security schemes).

Requests are paced (0.5 s between reads, 0.1 s between downloads, two at a time per source);
`429` and `503` wait for `Retry-After` (at most 30 s) or back off exponentially, four tries,
then a coded error (`rate_limited`, `source_unavailable`); a `Retry-After` that is not a
finite number of seconds falls back to the exponential wait. A link the source returns that
points to another host is not followed (`foreign_url`); a next link or page token seen before
is `pagination_loop`. Wrong credentials are `source_auth_failed` on the connection test and in
the run.

The Jira sample `data/samples/openapi/jira.yaml` (search, get, create, comment) can be published
as agent tools through the OpenAPI → MCP road (05b); publish create and comment with approval.

## API

`/api/v1/projects/{project_id}/data-sources` (OpenAPI `backend/openapi/16.yaml`). Developers and
above list, test and sync; a network-folder source is registered (and its root/filters
changed) by a superadmin, the other kinds by the project admin; deleting a source, mapping
permissions and `force_prune` are the project admin's. A knowledge base fed by an active source
cannot be deleted (`409 knowledge_base_has_sources`: pause or delete the source first); a run
of a source whose knowledge base is gone fails `kb_deleted` and writes nothing.

| Method and path | Purpose |
|---|---|
| `GET`, `POST /data-sources` | list, register (`kind`, `config`, `secret`, `schedule`, `sync_mode`, `prune_max_ratio`) |
| `GET`, `PATCH`, `DELETE /data-sources/{id}` | read, change (kind, deployment and knowledge base are fixed), delete |
| `POST /{id}/test` | reach the source, return its item count or an error code |
| `POST /{id}/sync` | `{layer, mode, force_prune}` → 202 with the queued run |
| `GET /{id}/runs`, `GET /{id}/runs/{run_id}`, `POST …/cancel` | history, one run, cancel |
| `GET /{id}/items?state=&errors=&skipped=` | items, their document, Kapı 0 and last error |
| `GET`, `PUT /{id}/acl-mappings` | permission mappings (PUT replaces the list) |

Credentials are stored encrypted and returned as `***`; a field sent back as `***` keeps its
stored value; they never reach logs or audit rows. A source still feeding documents cannot be
deleted (`409 data_source_has_items`): remove its documents with a full run first (narrow the
filter or empty the folder), so the safe delete rule applies.

Error codes: `path_outside_base` (400), `fs_source_superadmin_only` (403),
`source_kind_unavailable`, `deployment_invalid`,
`config_invalid`, `secret_required`, `secret_unexpected`, `secret_invalid`, `schedule_invalid`,
`fs_root_missing`, `prsim_requires_ner`, `force_prune_requires_full`, `acl_mapping_target`,
`acl_mapping_duplicate`, `acl_mapping_user_not_member` (422), `data_source_key_taken`,
`data_source_paused`, `data_source_has_items`, `sync_running`, `sync_run_finished`,
`knowledge_base_has_sources` (409), `queue_unavailable` (503). Run errors (in the run row):
`kb_deleted`, `count_failed`, `listing_failed`, `prune_failed`, `raw_failed`, `run_abandoned`.
Confluence/Jira (16-2): `source_auth_failed`, `source_not_found`, `source_query_refused`,
`source_unavailable`, `source_bad_response`, `rate_limited`, `foreign_url`, `attachment_gone`,
`attachment_download_failed`, `pagination_loop`, `endpoint_is_platform` (400 at registration).

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `FS_SOURCES_HOST_DIR` | `./data/sources` | host directory mounted read-only at `/data/sources` |
| `FS_SOURCES_BASE` | `/data/sources` | the only directory network-folder sources read |
| `PRUNE_MAX_RATIO` | `0.2` | largest share one full run may delete without `force_prune` |
| `ATTACHMENT_MIN_DATE` | empty | Kapı 0 date rule for attachments (`YYYY-MM-DD`) |
| `FULL_SYNC_EVERY_DAYS` | `7` | a scheduled run is full when the last full is this old; `0` = never |
| `ARQ_QUEUE_SYNC` | `sync` | the sync worker's queue (test runs use another) |
| `SYNC_WORKER_MEM_LIMIT` | `2g` | sync-worker container memory (a file is read whole, up to 500 MB) |

## Services

`sync-worker` (`arq ffcore.sources.worker.SyncWorkerSettings`, backend image) runs raw runs and
the minute tick; it loads no model and converts nothing. With the egress overlay it gets
`EGRESS_PROXY_URL` like the other application services (Cloud sources). Silver and gold run on the ingest
`worker` (`source_layer_job`). Neither publishes a port.
