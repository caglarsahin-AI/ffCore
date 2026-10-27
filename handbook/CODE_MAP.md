# Kod Haritası

Bu dosya 00 paketi merge edilince koordinatör tarafından doldurulur ve her dalga kapanışında güncellenir. Satır sayıları ve yollar ipucudur, otorite değildir; her plan gerçek depoda arama yapar.

## Ağaç (00 sonrası doldurulur)

```
backend/app/
  api/         (router'lar; paket başına dosya)
  core/        config.py, auth.py (resolve_actor), db.py, audit.py, tracing.py, features.py
  models/      SQLAlchemy; paket başına dosya, __init__ paylaşımlı
  services/    litellm_*, mcp_client.py
  runtime/     builder.py, nodes/, state.py
  guardrails/  engine.py, rules/, recognizers/ (LiteLLM kancası yok, B3)
  knowledge/   pipeline/, vectorstore/{base,pgvector,qdrant}.py, search.py
  evaluation/
  memory/      (14)
  channels/    (15)
  sources/     (16)
backend/alembic/versions/   paket branch label'ları
frontend/app/(console)/ (chat)/   messages/tr.json   styles/tokens.css
services/mcp-sql/   services/mcp-search/
deploy/   docker-compose.yml  litellm/  ollama/  offline/
```

## Agent keşif kuralı

Plan yazmadan önce en az şu aramalar gerçek depoda yapılır; bulunan gerçek yol ve sembol PR planına yazılır:

```text
rg -n "def resolve_actor|class Actor|require_role|access_mode" backend
rg -n "class VectorStore|PgVectorStore|QdrantStore|ingest_from_raw" backend
rg -n "class Decision|stage ==|input.pre|tool.post|egress" backend/app/guardrails
rg -n "definition|schema_version|build_graph|interrupt\(" backend/app/runtime
rg -n "run_events|RunEventType|RunStatus" backend/app
rg -n "render_litellm|/model/new|store_model_in_db" backend
rg -n "arq|WorkerSettings|queue_name" backend
rg -n "useTheme|tokens.css|tr.json" frontend
```

## Sapma listesi

Doküman ile kod arasında görülen sapmalar buraya eklenir (no, sapma, hangi paket düzeltir). İlk sapma ilgili modüle dokunan paketle kapatılır; kapsamı aşıyorsa `state/BLOCKERS.md` `DEBT-` kaydı.

| # | Sapma | Düzeltme |
|---|---|---|
| — | henüz yok | |
