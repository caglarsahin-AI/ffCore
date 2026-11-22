# Data sources (FFCore Knowledge, package 16)

A data source feeds one knowledge base from a live system on a schedule, instead of manual
uploads: what is added or changed at the source is indexed, what is really deleted there leaves
the index, and the source's permissions are carried to the documents. 16-1 ships the core and
the **network folder** source; Confluence and Jira (Server/Data Center and Cloud) follow in
16-2, SharePoint/OneDrive and the console screen in 16-3. The word "connector" is not used
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
run is a raw **delta**; a full run (and so a deletion) is always started by a person. A source
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

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `FS_SOURCES_HOST_DIR` | `./data/sources` | host directory mounted read-only at `/data/sources` |
| `FS_SOURCES_BASE` | `/data/sources` | the only directory network-folder sources read |
| `PRUNE_MAX_RATIO` | `0.2` | largest share one full run may delete without `force_prune` |
| `ATTACHMENT_MIN_DATE` | empty | Kapı 0 date rule for attachments (`YYYY-MM-DD`) |
| `ARQ_QUEUE_SYNC` | `sync` | the sync worker's queue (test runs use another) |
| `SYNC_WORKER_MEM_LIMIT` | `2g` | sync-worker container memory (a file is read whole, up to 500 MB) |

## Services

`sync-worker` (`arq ffcore.sources.worker.SyncWorkerSettings`, backend image) runs raw runs and
the minute tick; it loads no model and converts nothing. Silver and gold run on the ingest
`worker` (`source_layer_job`). Neither publishes a port.
