# FFCore

Kurumsal yapay zekâ platformu: model dışındaki her şey (kapı, bilgi tabanı, araçlar, agent'lar, koruma, izleme)
kurum içinde. Plan `PLAN.md`, kurallar `CLAUDE.md` ve `handbook/`, geliştirme ortamı
`docs/gelistirme-ortami.md`.

| Dizin | İçerik |
|---|---|
| `backend/` | FastAPI uygulaması ve LangGraph runtime |
| `frontend/` | Next.js yönetim önyüzü (Türkçe) |
| `services/` | MCP servisleri (`mcp-sql`, `mcp-search`) |
| `deploy/` | Compose, LiteLLM, Ollama, Langfuse yapılandırması |
| `data/` | Sentetik örnek veri (`data/samples/`) |
| `docs/` | Kurulum ve kullanım belgeleri |
