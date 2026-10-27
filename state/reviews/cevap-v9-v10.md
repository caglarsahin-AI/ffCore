# İnceleme v9 ve v10 cevabı (27 Ekim 2026) — PayCore LLM entegrasyonu

Kullanıcı kararı: FFCore'un canlı test ve ilk kullanım yeri PayCore LLM (`C:\ai_paycore\paycoreLLM`). Yedi karar kullanıcıdan alındı, bellek artırımı onaylandı. Uygulama PLAN.md 2.4 (bölüm 2d), `plan/00i-paycore-entegrasyon.md`, KARARLAR "PayCore entegrasyonu", CONTRACTS C5/C14, SECURITY, brief'ler ve state dosyalarında.

## Genel değerlendirme

- **v9** doğru soruya cevap veriyor ("FFCore PayCore'da nasıl canlı olur"): iskeleti alındı (00i karar paketi, çalışan ingest/RAG'in sarılması, Qdrant + sparse, bellek, Faz kilidi, kimlik). Dört öneride v9'dan ayrıldık (aşağıda).
- **v10** başka bir soruya cevap veriyor ("PayCore Faz 1 nasıl biter"): FFCore'u PoC'den çıkarma önerisi **reddedildi**; ama üç güvenlik bulgusu (B3 kimliksiz API, B4 fail-open secret ve portlar, P4 eşzamanlılık donması) ve "Faz 1 açıkları önce" sırası **00i olarak PoC'nin başına alındı**.

## Kullanıcı kararları

| No | Karar | Nerede |
|---|---|---|
| 1 | FFCore ayrı depoda, paycoreLLM tüketici; `jira/`, `prsim/`, `router/` uzantı; tek yön bağımlılık | PLAN 2d.1, 00i A, CONTRACTS C14, KARARLAR |
| 2 | paycoreLLM kökünde FFCore CLAUDE.md; PayCore sıkı kuralları aynen; "dal açılmaz" kuralı PR akışıyla değişti | PLAN 2d.2, 00i A, KARARLAR tersine karar |
| 3 | W17 kilidi 00i MERGED sonrası, yalnızca sentetik DB için | PLAN 2d.3, 00i A, 05 teknik not |
| 4 | S1 seti iç dokümantasyon sorusu; PoC kalite kabulü | PLAN 2d.6, 13b, SECURITY okuma kuralı |
| 5 | PRSIM kişi verisi guard'ı 08 tam ile; ertelendi | PLAN 2d.7, BLOCKERS 14, 08 tam kapsamı |
| 6 | 4B router PoC'de kapalı; profiller = filtreli agent | PLAN 2d.4, 00i A, 06 `knowledge[].filter` |
| 7 | PoC chat'i Open WebUI; 11 PoC sonrası | PLAN 7/8, 11 başlık, WORK_QUEUE |
| + | Bellek artırımı; Langfuse v3 kalır (v2'de veri yok) | 00i A, KARARLAR, 02 |

## v9 maddeleri

| v9 | Karar | Uygulama |
|---|---|---|
| P1 iki anayasa | kabul | 00i A: FFCore CLAUDE.md geçerli, PayCore sıkı kuralları aynen, dört gevşetme KARARLAR'da tersine karar |
| P2 yerleşim | kısmen | Tek kök paycoreLLM değil: FFCore ayrı depo + path bağımlılığı (karar 1); FFCore örnek verisi `data/`'ya girmez; touch-zone 00i için paycoreLLM |
| P3 bileşen tablosu | kabul (bir fark) | Qdrant + sparse birincil (PayCore seed'i), embedding süreç içi (C10 tersine), DuckDB sarılır (DEBT-10), arq + Redis, LiteLLM eklenir, PaddleOCR, `max` seed'de, LangGraph. **Fark:** Langfuse v2 değil **v3** (bellek artırıldı, v2'de gönderilmiş iz yok) |
| P4 bellek | kabul | 00i bellek tablosu; modeller yalnızca API süreci; router kapalı; Open WebUI kalır; NER PoC'de yok; artırım onaylandı |
| B1, B2, B6 | zaten uygulanmıştı (cevap-v4-v6) | B6 daha da daraltıldı: 08-lite |
| B4 S1 kabulü | kabul | 13b kalite kabulü S1; akış kabulü sentetik KB + SQL; 09:87 ifadesi karar 4 ile düzeltildi |
| P5 doğrulama ortamı | kabul | 00i teknik not: sunucuya ajan bağlanmaz, "VERIFIED (ölçüm bekliyor)" istisnası; Jenkins `make lint test test-int` PoC sonrası |
| P6 CPU'da araçlı agent | kabul | PLAN 2d.5, 06: iki agent; `mode: tool` GPU/llmaas'ta ölçülür |
| P7 profiller = agent | kabul | 06 `knowledge[].filter.scope` additive (C8 M3'ten önce) |
| P8 kimlik bilgileri ve okuma yasağı | kabul | SECURITY dosya düzeyinde; `.env.test`; `experts/*.yaml` okunabilir |
| P9 donma düzeltmesi | kabul | 00i D (ilk görünür fayda) |
| M1, M2, M3, M8, M11, M12, M13, M15, M20, M21, M22 | zaten uygulanmış (cevap-v4-v6) | M22 güncellendi: PoC'de yalnızca `cpu`; M15: mevcut korpus "proje üyelerine açık", Confluence/Jira izinleri 16'da |
| M10 (v5'in tersi) | kabul | Embedding süreç içi dense+sparse; 01'den `embed-default` çıktı |
| N48, N49, N50, N51 | kabul | `source_sync_state`; taban migration 00i; `bronze` CLI uzantıda, API `raw`; sürüm eşlemesi 00i docs |
| §7.1 depo sahipliği çelişkisi | kabul | Karar 1 ile çözüldü; KARARLAR:11 korunuyor |
| §7 Qdrant/pgvector | kısmen | Ürün varsayılanı pgvector kalır; PayCore seed'i Qdrant. İki sürücü 04a'da |
| §7 LiteLLM env var | zaten tersine dönmüştü | — |
| U14, U16 | DRIFT 11, 13 | İşçi doğrular |
| U18 PRSIM kişi verisi | karar 5 | ertelendi, BLOCKERS 14 |

## v10 maddeleri

| v10 | Karar | Gerekçe / uygulama |
|---|---|---|
| B1 ikinci yığın | kısmen | FFCore servisleri `compose.ffcore.yml` override'ı olarak eklenir, PayCore compose korunur (00i); ama servisler eklenir, çünkü FFCore bunlarsız ürün değil |
| B2 Faz 2 yasağı | kısmen | Sıra ile çözüldü: 00i önce, W17 sonra ve yalnızca sentetik DB (karar 3). "LangGraph + MCP + onay PoC'den çıksın" **reddedildi**: FFCore'un kanıtlanacak değeri bunlar |
| B3 kimliksiz API | kabul | 00i B |
| B4 fail-open secret/port | kabul | 00i C |
| M1 pgvector/arq gereksiz | reddedildi | Redis zaten SSE/PII/`LLM_SLOTS` için gerekli; pgvector PayCore'da kullanılmaz ama ürün sürücüsü olarak kalır; DuckDB sarılır (v9 ile aynı) |
| M2 LiteLLM gereksiz | reddedildi | İki çağrı yolu oluşur; TH zaten ister; maliyet 1 GB ve 2,5 gün |
| M3 Langfuse v2 kalsın | reddedildi | Bellek artırıldı, v2'de veri yok; v3 FFCore standardı |
| M4 Next.js yerine Open WebUI | kısmen | Chat için **kabul** (karar 7, 11 ertelendi); konsol (10a/10b) **kalır**: FFCore'un çekirdek değeri, PayCore'da yönetim ekranı yok |
| M5 tam PII PoC'de değil | kabul | 08-lite |
| M6 Faz 1 eksikleri önce | kabul (FFCore'un önkoşulu olanlar) | 00i E; PRSIM TODO'ları PayCore uzantı kuyruğunda |
| N1 profil `airgap` | kabul | PLAN 2b/2d |
| N2 `/health` + `/readyz` | kabul | 00i: `/health` liveness kalır, `/readyz` 04a additive |
| F6 profil yükleme sessiz devam | not | PayCore uzantı kuyruğuna `FOLLOWUP-` (router kapalıyken etkisiz) |
| K1 `llmaas` varsayılanı | kabul (aynı şey) | Ürün varsayılanı kalır, PoC profili `airgap` |
| K2 pgvector | kabul (aynı şey) | PayCore seed'i Qdrant |
| K3 tek kök paycoreLLM | reddedildi | Karar 1 |
| U1-U6 | DRIFT 12 (U1), 00i S1 tabanı (U3), U4/U5 kullanıcı sunucuda doğrular |

## Süre

PoC ≈ 49 agent-günü (00 1,5; 00i 4; 01 2,5; 02 1; 03a 3; 03b 2; 04a 5,5; 05a 4; 06a 6,5; 07 1,5; 08-lite 3; 10a 3; 10b 6; 13a 1; 13b 2). Kritik yol 00 → 00i → 03a → 01 → 04a → 05a → 06a → 07 → 13b ≈ 31 iş günü; sunucuda kullanıcı eliyle yapılan ölçümler hariç. v9'un 50,5 ve v10'un 14-25 tahminiyle karşılaştırma: v10'un rakamı FFCore'u içermediği için karşılaştırılabilir değil.
