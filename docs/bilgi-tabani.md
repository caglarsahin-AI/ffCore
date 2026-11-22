# Knowledge base (FFCore Knowledge, packages 04a and 04b)

Documents are uploaded, converted, checked by three quality gates, chunked, embedded in process
and searched with hybrid retrieval and a reranker. Documents never leave the installation:
conversion, embedding and reranking run locally. The defaults below are measured values (taken
over from the PayCore deployment); changing one is a decision, not a tuning knob.

## Three layers

| Layer | Where | Content | Rebuilt |
|---|---|---|---|
| raw | `KNOWLEDGE_STORAGE_DIR/raw/{project}/{kb}/{source}/{document}/original.<ext>` | the uploaded or fetched file, byte for byte; the stored name is ours, never the user's | only when the source changes |
| silver | `KNOWLEDGE_STORAGE_DIR/silver/{project}/{kb}/{source}/{document}.md` (+ `.raw.md`) | converted, cleaned Markdown with a frontmatter (breadcrumb, ACL, gate decisions, converter, `normalizer_config_id`); `.raw.md` is the converter output before cleanup | `make reindex LAYER=silver`, from raw |
| gold | Postgres `chunks` (+ the vector store) | chunks, vectors, BM25 tsvector | `make reindex LAYER=gold`, from silver |

`make reindex PROJECT=<key> KB=<key> LAYER=silver|gold [FULL=1]` (tools container) queues the
job; the worker log shows `reused=N embedded=M`.

Deleting a document (or its knowledge base) removes its silver file and `.raw.md` at once; raw
stays on disk (it is the only copy of what the source gave, D3) and is removed by the operator's
runbook (FOLLOWUP-133).

### Targeted reconversion (04b)

`make reconvert PROJECT=<key> KB=<key> PRESET=<preset>` (or `POST …/reindex` with
`{"layer": "silver", "preset": "<preset>"}`) reconverts from raw only the documents one problem
hit, whatever their status:

| Preset | Documents |
|---|---|
| `encoding` | failed with `encoding_undecodable` |
| `timeout` | status `timeout` |
| `mhtml` | converted as MHTML (`convert_engine` `mhtml…`, or sniffed `multipart/related`) |
| `engine:<name>` | `convert_engine` exactly `<name>` (e.g. `engine:docling`) |

Any other value is refused (`preset_unknown`); a preset with `layer: gold` is
`preset_requires_silver`. The response's `documents` is the number the preset selects. The
personnel-data rule of a silver reindex applies (`prsim_requires_ner`).

## Ingest from a raw-staging tree (`ingest-raw`, package 19)

A connector or a consumer that already has the content (PayCore's raw layer) writes a
**raw-staging tree**: each document is a file with `<file>.meta.json` beside it
(`source` as `<kind>:<space>`, `source_item_id`, optional `title`, `breadcrumb`, `source_url`,
`updated_at_source`, `attachments` as file names in the same directory). Other meta fields are
ignored. Then:

```
python -m ffcore.cli ingest-raw --project <p> --kb <kb> --raw-dir <tree, read-only>   --acl <role> --sources <kind:space> ... [--limit N] [--manifest-out <file>] [--text-filter pii_ner|pii_regex] [--accept-personnel-data]
```

- Every file goes through C6 `ingest_from_raw` with a named text filter, by default `pii_ner` (08 full
  1b): e-mail, phone, national id, IBAN, card (regex) and person names (the API's NER over
  `POST /api/v1/internal/guardrails/ner`), redacted to `[CODE]` before silver is written, so
  silver, `.raw.md` and gold are masked; raw stays byte for byte; the document records
  `metadata.text_filter = "pii_ner@<version>"`. A name never overrides a regex finding. Masking
  cannot be turned off: the only other choice is `--text-filter pii_regex` (below). The NER is checked before the first file:
  unreachable or not configured stops the run (`ner_unavailable`; with a PRSIM source
  `prsim_requires_ner`, before the database), a tree is never half name-masked.
- `pii_ner` is the default in every profile, airgap included: without the NER weights (or an
  API that answers NER) a default `ingest-raw` stops with `ner_unavailable` whatever the source.
  `GUARDRAIL_EGRESS_NER=false` (airgap) is about egress, not ingest.
- `--text-filter pii_regex` (FOLLOWUP-174) is for sources without person data (for example a
  product documentation space) on an installation without NER: identifiers are masked as above,
  person names are not looked for, no NER is called, and documents record `pii_regex@1`. A
  personnel-data source (PRSIM, by source or path) is still refused (`prsim_requires_ner`): it
  needs `pii_ner` or the M3 flag. Choosing the filter is the operator's statement that the
  sources carry no person data: no NER runs, so names in them stay as written. The regex
  identifiers (card, IBAN, national id, e-mail, phone) are still masked; the run does not stop
  on them (stopping on customer data is the personnel-data path's rule, below).
- `--accept-personnel-data` is the M3 measurement mode: it keeps `pii_regex` (identifiers only,
  person names not masked) so the measured manifest stays as it was, and is logged as such. With
  an explicit `--text-filter pii_ner` it is refused (`text_filter_conflict`, exit 2).
  Documents ingested before 08 full 1b keep `pii_regex@1`; a reindex applies the filter the
  document records. A run never processes a record written under another filter: the same
  bytes recorded as `pii_regex@1` in a `pii_ner` run (or the other way round) are refused as
  `text_filter_mismatch`, counted, and the record stays as it is (a PRSIM record from the M3
  mode is never retried with names unmasked).
- Reindex is inside the same boundary: `make reindex LAYER=silver` refuses with
  `prsim_requires_ner` (exit 2, nothing queued or touched) when a personnel-data record written
  with `pii_regex@1` (the M3 mode) is in its scope; `python -m ffcore.cli reindex ...
  --accept-personnel-data` runs it in the M3 mode, logged with the number of such records
  (`records=N`) and audited as `reindex_personnel_data_accepted` (system actor; layer, `full`
  and the count, never a file name or content). The flag concerns the silver reconversion only:
  with `--layer gold` it is refused (`flag_not_applicable`, exit 2). A reindex requested through
  the API with such a record in scope is refused at the endpoint with 409 `prsim_requires_ner`
  before anything is queued (the API has no M3 flag; the job checks again).
- Attachment file names are masked too: in a personnel-data source (PRSIM) the shown name
  (attachment record, silver heading, chunk breadcrumb) is `Ek <n>`; in other sources the name
  goes through the text filter with `_` and `-` read as spaces. The raw file keeps its name.
- The record key is the path inside the tree; an unchanged file (same sha256) is `unchanged`
  and not processed again. The breadcrumb from the meta file is used when given.
- Refused, counted, never silently skipped: `path_outside_base` (symlink, `..`, outside the
  tree), `too_large` (Kapı 0 limits), `meta_missing`, `meta_invalid`, `source_not_selected`,
  `prsim_requires_ner` (PRSIM while names cannot be masked). In a personnel-data source (PRSIM,
  with `pii_ner` or in the M3 mode) a card number, IBAN or national id stops the run
  (`customer_data_suspected`).
- The output is counts only. The manifest (`--manifest-out`, never under the tree) holds stage
  (`full` or `stage0-pipeline-evidence` with `--limit`), per-source documents and chunks, current
  statuses, `failed`/`timeout`, refusals, `text_filter` (the run's), `text_filters` (documents
  and chunks per filter the documents carry), `text_filter_mismatch` and `raw_manifest_sha256`.
- Deleting a document keeps raw and silver files (FOLLOWUP-133).

## Fed by a data source (package 16)

A knowledge base can also be fed by data sources (network folder; Confluence, Jira and SharePoint
follow): their items enter through the same pipeline (`ingest_from_raw`, C6), named
`<source key>/<item id>` and carrying `metadata.source`, `source_item_id` and `source_url`.
`make sync … LAYER=silver|gold` reprocesses one source's documents only; `make reindex` still
covers the whole knowledge base. Permissions, schedules and the safe delete rule:
docs/veri-kaynaklari.md.

## Conversion

The first bytes decide, the extension only breaks ties: an MHTML web archive saved as `.doc` is
read as HTML. Text is decoded strictly (UTF-8, then cp1254 line by line); a file that is neither
fails with `encoding_undecodable` instead of entering the index with broken letters.

| Format | Tool |
|---|---|
| PDF with a text layer | Docling, then pymupdf4llm, then the PyMuPDF text layer (never OCR); over 150 pages Docling is skipped |
| scanned PDF (text layer under 120 characters) | PaddleOCR `tr`, at most `OCR_PDF_MAX_PAGES` (200) pages, truncation stated |
| DOCX, PPTX, HTML | Docling |
| Markdown (`.md`, `.markdown`) | as written (decoded, not fenced), engine `markdown`; no Docling and no weights (04b-2, FOLLOWUP-87) |
| e-mail `.eml` / `.msg` | stdlib / extract-msg, HTML bodies as visible text |
| draw.io, `.vsdx` | stdlib XML |
| txt, log, json, xml, yaml | as text, fenced |
| old Office (`.ppt`, `.vsd`, binary `.doc`), video | skipped with `libreoffice_unavailable` / `video_disabled` (see "Video") |
| archives, spreadsheets, csv, sql, images, binaries | skipped with `out_of_scope` / `binary` |

Every file converts in a worker process with `CONVERT_TIMEOUT_SECONDS` (600); past it the process
is killed, the document is `timeout` and the next file goes on. A `timeout` is not retried by a
plain reindex. The file's time starts when its worker reports ready: a fresh worker's spawn and
imports are bounded separately by `CONVERT_WORKER_START_TIMEOUT_SECONDS` (60); past it the worker
is killed and the document fails with `convert_worker_start_timeout`. Docling and PaddleOCR load
on the first file that needs them, so that load still counts against the file's timeout
(about 66 s measured in a fresh process, well inside 600).

Limits, each a recorded refusal with a code (the file's content is never in the message):

| Limit | Default | Code |
|---|---|---|
| One upload request, checked before the body is parsed | `UPLOAD_MAX_REQUEST_BYTES` (516 MiB) | HTTP 413 `request_too_large` |
| One file (Kapı 0; streamed to disk, nothing stored past it) | 5 MB plain text, 500 MB others | `too_large` |
| ZIP containers (docx, pptx, vsdx): members, expanded bytes, per-member ratio | 10 000, 512 MiB, 100x | `archive_too_many_members`, `archive_too_large`, `archive_ratio` |
| draw.io diagram payload inflated | 64 MiB | `diagram_too_large` |
| PDF pages, page size rendered at 150 dpi | 5 000, 40 M pixels | `pdf_too_many_pages`, `pdf_page_too_large` |
| Converter process address space | `CONVERT_MEMORY_LIMIT_MB` (10240) | `convert_memory_limit` |
| Converter CPU per file | `CONVERT_CPU_LIMIT_SECONDS` (3600) | `convert_cpu_limit` |
| Worker container memory | `WORKER_MEM_LIMIT` (6g) | `worker_died` |

## Quality gates

Each gate keeps its own status (`ok`, `flagged`, `skipped`) and reason; nothing is deleted, and
the `ingest_gate_stats` view counts source × gate × reason (per gate the totals equal the
documents).

- Kapı 0 (scope, before conversion): binaries, out-of-scope formats, size (plain text 5 MB,
  others 500 MB).
- Kapı 1 (document): empty, too short (30 tokens; a short body passes when its attachments have
  text), template, duplicate of another document's text (`duplicate_of:<id>`; the first owner
  keeps it), language not in `ALLOWED_LANGUAGES` (`tr,en`; a text with neither Turkish nor
  English function words is left to Kapı 2).
- Kapı 2 (text quality, document and chunk): empty, title only, too short (20 tokens),
  `boilerplate` (over 60 % link lines), `code_heavy` (over 50 % code lines; outside a
  ```` ``` ```` or `~~~` fence a Markdown heading line, `#` to `######` followed by a space and
  text, is not a code line, so an unfenced `# text` shell comment is not one either, while
  `#include`, `#!/bin/sh` and a bare `#` are; inside a fence `# text` is a code line; the fence
  lines themselves are not, since plain text arrives wrapped in one fence; after a fence that
  never closes the in-fence rule applies), `no_prose`
  (function-word ratio under 0.05, the higher of the Turkish and the English one since
  04b-2 FOLLOWUP-145: flagged from 2000 characters, skipped below).
- Data dumps (attachments): `data_dump:encoded|log|stack_trace|structured|tabular`; the owning
  document is still indexed, the attachment is not.

## Chunking

Heading-aware, greedy packing from `chunk_size` (400 tokens) up to 1.5 × that (600), no
overlap, counted with the embedding model's own tokenizer (`FAKE_EMBED=1` uses the estimate
max(words × 1.6, characters / 6)). The 600 covers the whole embedded text: the breadcrumb
(`Knowledge base › file › section`; attachments get `Ek: <file>`) plus the body. The section
part is structure only (FOLLOWUP-108): a Markdown heading of at most 60 characters, an article as
`Madde N - Title` up to the first colon (plain text writes `Madde 2 - Süre: <clause>`); a longer
heading keeps only its number (`Madde 5`, `3.2`) and one without a number stays out of the
breadcrumb, still in the body. Over-long text
is split by paragraph, sentence and word, and a word longer than the limit by the tokenizer
itself; nothing is cut. A breadcrumb taking more than half of the limit fails the document with
`chunk_breadcrumb_too_long`. On reindex a chunk
whose text and embedding model are unchanged takes its vector over; a new embedding model
re-embeds everything.

## Embedding and search

- Embedding: `EMBED_MODEL` (`BAAI/bge-m3`, dense 1024 + sparse) in the API process only, one
  call at a time, never on the event loop. The ingest worker calls `POST /internal/embed`.
  Changing the model means a migration for `EMBED_DIM` and `make reindex LAYER=gold FULL=1`.
- Vector store: `VECTOR_BACKEND=pgvector` (default, `chunks.embedding` + HNSW) or `qdrant`
  (dense + sparse; compose profile `qdrant`, `QDRANT_URL`, and `qdrant` in
  `ALLOWED_INTERNAL_HOSTS`). No automatic choice and no fallback between them.
- Postgres keeps both halves of every embedding whatever the driver: the dense vector in
  `chunks.embedding` and the bge-m3 sparse weights in `chunks.sparse` (04b). A chunk whose text
  and model did not change takes both over at a gold reindex, so Qdrant reuses vectors too.
- Search: the query passes the same normalizer as silver (format cleanup, and the Turkish
  layer when `TEXT_NORMALIZE_TR` is on); a vector leg and a lexical leg
  (Postgres BM25 for pgvector, bge-m3 sparse inside Qdrant) are fused by RRF (k = 60) into 30
  candidates; the reranker (`BAAI/bge-reranker-v2-m3`) scores them and only those at or above
  `RERANK_MIN_SCORE` (0.1) are returned. With the reranker on, the embedding score never
  pre-filters (single threshold rule); with it off, only `default_min_score` applies.
- Every search writes one `kb_queries` row: the 30 candidates with both scores, what each
  threshold removed, latency and `run_id`.
- Newest first (`by_recency`) orders by the document's source date, `updated_at_source`: an
  upload form field, `PATCH …/documents/{id}`, or a connector's metadata (`ingest_from_raw`).
  Without it the date is unknown (`null`), listed after dated sources and shown as "unknown
  date" to the model; the upload time is never used in its place (FOLLOWUP-101).
- Model weights live in the `model_cache` volume, never in the image. Keep it when closing a
  stack (`docker compose down`, not `down -v`).

## Video (04b-2)

`VIDEO_TRANSCRIPT_ENABLED` is `false` (default) and a video (`mp4 m4a mov mkv avi wav mp3`) is
recorded at Kapı 0 as `video_disabled`, counted in the ingest report, never dropped silently.
This build has no transcriber (faster-whisper is a separate change, with its own approval), so
setting it to `true` stops start-up with `video_transcriber_unavailable`. Once a transcriber is
part of the build, `make reconvert PRESET=video` (or the `video` preset of `POST …/reindex`)
converts exactly the documents that were `video_disabled`.

## Turkish normalizer layer (`TEXT_NORMALIZE_TR`, 04b-2)

Off by default. On, silver and every query get PayCore's deterministic layer A on top of format
cleanup: circumflexes are folded (`kâr` → `kar`, `hâlâ` → `hala`, `Â` → `A`, `Î` → `İ`), in
prose only; fenced and inline code and URLs keep their exact form. The known cost is that
`kâr`/`kar` become one word. PayCore's lexicon layers (B-D) are not part of it.

The form is recorded as `normalizer_config_id`: `format-v1`, or `format-v1+tr-a1` with the layer,
on the knowledge base, every document, the silver frontmatter and every `kb_queries` row. A
search while an indexed document is in another form answers 409 `normalizer_config_mismatch`
(no mixed-form results): after changing the setting, run `make reindex PROJECT=… KB=…
LAYER=silver FULL=1`, which rebuilds silver from raw under the new setting; the 409 message
names the same command. Without `FULL=1` the documents whose raw did not change are not rebuilt
and the 409 stays.

## Thresholds per embedding model (04b-2)

Only measured values; "not measured" stays empty, never a guessed number.

| Embedding model | Reranker | Rerank floor (`RERANK_MIN_SCORE`) | Embedding `min_score` |
|---|---|---|---|
| `BAAI/bge-m3` | `BAAI/bge-reranker-v2-m3` | 0.1 (PayCore's measurement) | not measured; with the reranker on it does not filter (single threshold rule) |
| `intfloat/multilingual-e5-large` | none | not measured | not measured (the Turkish embedding comparison runs on the target machine) |

`GET …/knowledge-bases/{kb_id}/query-stats?days=30` (readers, 1-365 days) gives what a screen
needs to say "X % of queries are below the threshold": number of queries, zero-result count and
ratio, per score kind (rerank, embedding) how many queries had one, how many are below the
threshold in force (`RERANK_MIN_SCORE`; the knowledge base's `default_min_score`, `null` when it
has none) and the 10/50/90th percentiles of the best score per query, plus the table row of the
knowledge base's embedding model. It only informs; no threshold is changed by it.

## Who changes a document's ACL (04b)

Only a project admin changes a document's ACL. There are two ways, and both pass the same role
check: `PATCH …/documents/{id}` with `acl_roles`, `acl_users` or `acl_open`, and an upload under
the name of an existing document.

- An upload under an existing name that sends an ACL different from the document's is 403
  `insufficient_role` for anyone but an admin; nothing is written. An upload without ACL fields
  keeps the document's ACL (the `analyst` default is for new documents only).
- An upload under the name of a document the caller cannot read is 409 `document_name_taken`;
  the document's content, version and ACL stay. The answer shows that the name exists, nothing
  more. A project admin is exempt, so a document readable by named users only (which hides it
  from the admin too) can still be replaced.
- The same exemption holds for one document: a project admin (a superadmin's grant counts as
  admin) gets, changes and deletes a document readable by named users only through
  `GET`, `PATCH` and `DELETE …/documents/{id}`. Everyone else gets 404 `document_not_found`, as
  for a missing document. The document list, search and the ingest report keep the read filter
  for the admin too: the admin knows the document's id from the upload answer.
- `ingest-raw` (CLI, the operator) is not an API caller and is not affected.

## Moving vectors between drivers (`migrate-vectors`, 04b)

```bash
docker compose run --rm tools make migrate-vectors PROJECT=<key> FROM=pgvector TO=qdrant [KB=<key>] [DRY_RUN=1] [DROP_TARGET=1]
```

- Embeddings are not recomputed. pgvector → Qdrant upserts the stored dense vector, the sparse
  weights and the document ACL as it is now; Qdrant → pgvector fills `chunks.embedding` of the
  rows that lack it from the Qdrant points.
- A chunk written before 04b has no sparse weights: the migration computes those only (through
  the API's `/internal/embed`, so the backend must be up) and prints `sparse_computed=N`. A dry
  run writes nothing and prints `sparse_missing=N`.
- Per knowledge base the line shows `source`, `target`, `written`; the run exits 1 when the
  target does not hold the source's vectors, and the line says what to do for that target. A
  Qdrant collection with points of its own (an earlier run, another installation) is never
  cleaned silently: run again with `DROP_TARGET=1` (Qdrant only; the pgvector column is the
  source of truth and is never dropped). Towards pgvector a mismatch means Qdrant holds points
  of chunks that are not searchable in Postgres (document deleted or not indexed) or misses
  some: reindex those documents (`LAYER=gold`) or rebuild the Qdrant side with
  `FROM=pgvector TO=qdrant DROP_TARGET=1`.
- Run it while no ingest is running: a document being re-embedded is not searchable and is not
  counted on the pgvector side.
- The switch is `VECTOR_BACKEND` in `.env` (the operator's); going back is setting it back.
  Dense vectors, chunk text and documents on the source side never change. The one write there
  is additive: pgvector → Qdrant stores the sparse weights a pre-04b chunk lacked in
  `chunks.sparse`, and they stay even when the run ends in a mismatch (derived data, what a gold
  reindex would write). Search ACL is applied in the query on both sides.

## Ingest report (04b)

`GET …/knowledge-bases/{kb_id}/ingest-report?limit=100` counts documents by source × gate ×
status × reason (per gate the counts add up to `documents`, the shape of the `ingest_gate_stats`
view) and lists the rejected documents (the first gate that skipped them, with its reason) and
the skipped chunks (`chunk_reason`), each list up to `limit` rows with its total. Only documents
the caller may read are counted and listed.

## Model weights (offline)

Both profiles run offline: images and Compose set `HF_HUB_OFFLINE=1` and
`TRANSFORMERS_OFFLINE=1`, every loader reads a local path from the cache, and PaddleOCR gets
explicit directories under `/models/paddleocr`. Nothing downloads at run time; a missing weight
is `model_missing` with the model name and the path it was looked for in (in `/readyz`, in the
worker log at start, on the file that needed it). The tokenizer is required for every document,
so the worker does not start without it.

Weights come from one separate step, run once per installation by an operator. It connects out
(airgap: set `HF_ENDPOINT` to the internal mirror):

```bash
docker compose run --rm tools make models
```

`make models-check` lists every weight and where it is, offline; exit 1 when one is missing.

## Readiness

`GET /readyz` is 503 `warming` until both models are loaded (`model_missing` when a weight is
not in the cache), then checks the `chunks.embedding`
size against `EMBED_DIM`, the vector store, and (with `INFERENCE_BACKEND=ollama`) that
`OLLAMA_CONTEXT_LENGTH` is set and not below the largest needed context
(`context_configuration_invalid`): every active Ollama model's `limits.context_window` (the
console and seed field; checked without any agent, FOLLOWUP-219) and every published agent's
`limits.context_tokens` on an Ollama model. `ollama_runtime_context` (04b-2, FOLLOWUP-31) then
asks Ollama's `/api/ps` what each loaded model really runs with (`context_length`): below the
same largest needed context is `context_configuration_invalid`, a missing field
`ollama_ps_unexpected`, no answer `ollama_unreachable`; while no model is loaded the check
is skipped and names them. **Not yet verified against the pinned ollama 0.12.6 image**
(ENV-204): written to Ollama's API documentation and tested with a stand-in answer.
`ingest_queue` reports the jobs waiting in the ingest queue (information only).

## Measured

The PR description of package 04a lists the numbers measured with the real models: indexing
time of the 10-page sample contract, the rank of "fesih bildirim süresi", and `/healthz` latency
under 10 concurrent searches. Thresholds per embedding model: "Thresholds per embedding
model" above; the Turkish embedding comparison is a measurement on the target machine
(not a package deliverable).
