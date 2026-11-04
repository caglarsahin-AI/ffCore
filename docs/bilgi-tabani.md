# Knowledge base (FFCore Knowledge, package 04a)

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

## Ingest from a raw-staging tree (`ingest-raw`, package 19)

A connector or a consumer that already has the content (PayCore's raw layer) writes a
**raw-staging tree**: each document is a file with `<file>.meta.json` beside it
(`source` as `<kind>:<space>`, `source_item_id`, optional `title`, `breadcrumb`, `source_url`,
`updated_at_source`, `attachments` as file names in the same directory). Other meta fields are
ignored. Then:

```
python -m ffcore.cli ingest-raw --project <p> --kb <kb> --raw-dir <tree, read-only>   --acl <role> --sources <kind:space> ... [--limit N] [--manifest-out <file>] [--accept-personnel-data]
```

- Every file goes through C6 `ingest_from_raw` with the named text filter `pii_ner` (08 full
  1b): e-mail, phone, national id, IBAN, card (regex) and person names (the API's NER over
  `POST /api/v1/internal/guardrails/ner`), redacted to `[CODE]` before silver is written, so
  silver, `.raw.md` and gold are masked; raw stays byte for byte; the document records
  `metadata.text_filter = "pii_ner@<version>"`. A name never overrides a regex finding. There is
  no option to turn it off or to name another filter. The NER is checked before the first file:
  unreachable or not configured stops the run (`ner_unavailable`; with a PRSIM source
  `prsim_requires_ner`, before the database), a tree is never half name-masked.
- `--accept-personnel-data` is the M3 measurement mode: it keeps `pii_regex` (identifiers only,
  person names not masked) so the measured manifest stays as it was, and is logged as such.
  Documents ingested before 08 full 1b keep `pii_regex@1`; a reindex applies the filter the
  document records.
- The record key is the path inside the tree; an unchanged file (same sha256) is `unchanged`
  and not processed again. The breadcrumb from the meta file is used when given.
- Refused, counted, never silently skipped: `path_outside_base` (symlink, `..`, outside the
  tree), `too_large` (Kapı 0 limits), `meta_missing`, `meta_invalid`, `source_not_selected`,
  `prsim_requires_ner` (PRSIM while names cannot be masked). In a personnel-data source (PRSIM,
  with `pii_ner` or in the M3 mode) a card number, IBAN or national id stops the run
  (`customer_data_suspected`).
- The output is counts only. The manifest (`--manifest-out`, never under the tree) holds stage
  (`full` or `stage0-pipeline-evidence` with `--limit`), per-source documents and chunks, current
  statuses, `failed`/`timeout`, refusals and `raw_manifest_sha256`.
- Deleting a document keeps raw and silver files (FOLLOWUP-133).

## Conversion

The first bytes decide, the extension only breaks ties: an MHTML web archive saved as `.doc` is
read as HTML. Text is decoded strictly (UTF-8, then cp1254 line by line); a file that is neither
fails with `encoding_undecodable` instead of entering the index with broken letters.

| Format | Tool |
|---|---|
| PDF with a text layer | Docling, then pymupdf4llm, then the PyMuPDF text layer (never OCR); over 150 pages Docling is skipped |
| scanned PDF (text layer under 120 characters) | PaddleOCR `tr`, at most `OCR_PDF_MAX_PAGES` (200) pages, truncation stated |
| DOCX, PPTX, HTML, Markdown | Docling |
| e-mail `.eml` / `.msg` | stdlib / extract-msg, HTML bodies as visible text |
| draw.io, `.vsdx` | stdlib XML |
| txt, log, json, xml, yaml | as text, fenced |
| old Office (`.ppt`, `.vsd`, binary `.doc`), video | skipped with `libreoffice_unavailable` / `video_disabled` (package 04b) |
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
  (stopword ratio under 0.05: flagged from 2000 characters, skipped below).
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
- Search: the query passes the same format cleanup as silver; a vector leg and a lexical leg
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
`OLLAMA_CONTEXT_LENGTH` is set and not below any active Ollama model's `limits.context_tokens`
(`context_configuration_invalid`). The context Ollama actually applies at run time is not
verified here (FOLLOWUP-31).

## Measured

The PR description of package 04a lists the numbers measured with the real models: indexing
time of the 10-page sample contract, the rank of "fesih bildirim süresi", and `/healthz` latency
under 10 concurrent searches. Thresholds per embedding model and a Turkish embedding comparison
are package 04b.
