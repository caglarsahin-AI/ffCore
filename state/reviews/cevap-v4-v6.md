# İnceleme v4, v5, v6 cevabı (27 Ekim 2026)

Üç rapor tek listeye indirildi, her madde "kabul / kısmen / reddedildi" olarak sınandı ve kullanıcı listenin tamamını onayladı. Uygulama PLAN.md 2.3, brief'ler, KARARLAR.md, handbook/ ve state/ üzerinde yapıldı. Aşağıda madde numaraları bu cevabın (A-F) numaralarıdır; parantez içinde raporlardaki karşılıkları (v4 B/M/N/C, v5, v6) verilmiştir.

## A. Kapsam kararları (kullanıcı onayı)

| No | Karar | Nerede |
|---|---|---|
| A1 | PoC = M1-M3; 04b, 05b, 06b, 09, 12, 14-17 PoC sonrası (v5 kapsam, v6 tablo) | PLAN 7 "PoC" kolonu, dalgalar; WORK_QUEUE iki tablo |
| A2 | 03b daraltıldı (audit, OBO, `SERVICE_TOKEN`, `core/egress.py`); API key, kota, usage, retention, uyarılar, bildirim → 03c, 06b ile (v5 M20, v6 M2) | 03 brief başlık ve veri modeli; PLAN 6-7; KARARLAR |
| A3 | Giriş kalır, küçülür: admin + analyst; `read` modunun ekran tarafı 10c (kullanıcı: "kullanıcı girişi gibi") | 03a, 07 varsayılan rol, 13b demo kullanıcılar, KARARLAR |
| A4 | LiteLLM team/sanal anahtar/`end_user` bütçesi yok; tek iç anahtar + metadata (v4 B1/C8, v5 B1) | 01 §2, 03 (`litellm_team_id` kaldırıldı, 43-45, 88-90, 97), 06 facade, PLAN 5 R1.2, KARARLAR Reddedilenler |
| A5 | 09 Langfuse datasets/experiments üstünde; DECISION-4 kapandı (v4 İtiraz 4, C6) | 09 veri modeli, 02 kapsam dışı, BLOCKERS 4, KARARLAR |
| A6 | 10 → 10a / 10b-poc / 10c (v6 M4) | 10 başlık, PLAN 7, MULTI_AGENT touch-zone, BASLATMA dalga |
| A7 | 13 → 13a (dalga 1, sentetik) / 13b (M3 e2e, `make eval`); gerçek sözleşme ibaresi silindi (v4 B4/M18, v5 B4/M7, v6 M5) | 13 brief, 04/05/08/09/14 test seti kaynakları, PLAN 7-8 |
| A8 | `BACKGROUND_WINDOW` profil seed değeri; yalnızca airgap cpu dolu (v4 İtiraz 1, v5 §7) | 01 seed, 06 kuyruk, 09, 14, PLAN 5, KARARLAR tersine karar |
| A9 | 17 (LDAP) Slack/Teams'ten önce; widget ve Mattermost 15'te kalır (v4 İtiraz 3) | 15 başlık, PLAN 7-8 M7, WORK_QUEUE |

## B. BLOCKER'lar (hepsi kabul)

| No | Rapor | Uygulama |
|---|---|---|
| B1 | v4 B2, v5 B2 | 02 §7 06a'ya taşındı ("İz ve oturum alanları"); 02 = 1 gün, 06a = 7 gün |
| B2 | v4 B3, v5 B3, v6 B3/C1 | 01 `FallbackObserved` tipli sonuç + unit test; `run_events.fallback` 06a kriteri; 01 bağımlılığı 00, 03a (N9) |
| B3 | v4 B6/C4, v5 B6, v6 B2 | `litellm_hook.py` ve `guardrails:` kaydı silindi; 08 engine + `/internal/guardrails/evaluate`; 06a bağlar; 08 03a merge'ünden sonra başlar (dalga 2 kalır) |
| B4 | v4 B7/C3, v5 M8, v6 F3 | 04:35 yalnız `arq`, kuyruk `ingest` |
| B5 | v6 B1 | CONTRACTS C3 yalnız kök tablolar; istisna listesi (global, çocuk, append-only); PLAN 5; 03 `users`, `audit_events` işaretli |
| B6 | v6 B4, v4 N13 | 02 init `.env` yazmaz, anahtarı bir kez gösterir |
| B7 | v4 B5/C7 | 06b `user` yalnız `impersonate` ile; `api_keys.acl_role` (03c) |

## C. MAJOR'lar (hepsi kabul)

| No | Rapor | Uygulama |
|---|---|---|
| C1 | v4 M1/C2, v5 M1, İtiraz 2 | 01 uzlaştırıcı; `config.yaml`'da `model_list` yok; anahtar API gövdesiyle, U2 doğrulaması ilk iş; 03:23 ve 10:25 "uzlaştırıcı"; 00:37 şablon |
| C2 | v4 M2/C17, v5 M2 | `run_timeout_s` seed'de 120/900/300; 06:36 `null`; 06:84, 06:135; PLAN 2b aynen |
| C3 | v4 M3, v5 M3 | JWT her çağrıda, `aud=<tool_key>`, havuz yok; yalnız iç servisler; 03:37, 05:19/24/71 kriter |
| C4 | v4 M4/C13 | Onay yalnız oturum açmış kullanıcı; facade istemcisi bekler; 06:73, 07:22 |
| C5 | v4 M5, v6 M2 | 03b `core/egress.py` SafeOutboundClient + kabul testleri; 05, 07, 12, 15, 16 bunu kullanır; 16 `FS_SOURCES_BASE` |
| C6 | v4 M6 | Next.js rewrite tek origin, `SameSite=Strict`, CSRF token yok (ARCH-07); 03:41 |
| C7 | v4 M7/C1, v6 M1 | `embed_dim` 400 her yerde; 04:16, 04:105 |
| C8 | v4 M8, v5 M8 | 06 kuyruk iki katman: run = arq işi, `LLM_SLOTS` yuvası; etkileşimli-düşük `llm-background`'da penceresiz; CONTRACTS C10 |
| C9 | v4 M9 | APScheduler kaldırıldı: 03:35/50, 07:20, 16:23 `arq cron` |
| C10 | v4 M10/N4, v5 M10 | Embedding her profilde Ollama → LiteLLM; 01:14, 04:44/122, PLAN 2b |
| C11 | v4 M11/C11, v5 M11 | 06:110 tek araç `search_documents` |
| C12 | v4 M12, v5 M12 | `kb_queries.run_id` + `candidates`; `X-Run-Id`; 04:87, 05:53, 06, 09:21 |
| C13 | v4 M13/C19, v5 M13, v6 M3/F1/F2 | 06:54 400/503; `dropped_by_budget`; 05:19 `[kırpıldı]` + `truncated`; 02:15 seed + önbellek + `prompt_cache_stale`; limit aşımı `failed/limit_reached` |
| C14 | v4 M14/C18 | PLAN 5 R1.2 iki yüzey; 05:33 `tools_invoke` zorunlu; CONTRACTS C11 |
| C15 | v4 M15, v5 M15 | Boş ACL = proje üyeleri; elle yüklemede ACL zorunlu; 16 grup genişletme; 04:73 ve kriterler |
| C16 | v4 M16 | 12 forward proxy (`EGRESS_ALLOWLIST`), Teams yalnız `/channels/teams/messages`; 15:37 |
| C17 | v4 M17 | 08 akış tamponlayıcı + chunk bölme kriteri |
| C18 | v4 M18 | PII ve hafıza test setleri 13a'da; 08:70, 14:56 |
| C19 | v4 M19 | 14:27 "bunu hatırla" PII filtresi, 400 `memory_pii_blocked` |
| C20 | v4 M20, v5 M20 | `scope_type` project/api_key/user; bütçe Redis sayaçla anlık; `usage_daily` raporlama |
| C21 | v4 M21, v5 M21 | `chunk_strategy=heading`; 04:85 alanlar çıktı; 06:107 `webhook_url/budget_usd/raw_output_tools` çıktı |
| C22 | v4 M22, v5 M22 | GPU sütunu `NOT_RUN (PENDING_ENV)`; 12:46, 13 tablo; M5 cpu+llmaas |
| C23 | v4 M23, M24 | 08 tablo kolonları birleşti; `documents.gate0_*`; `messages.feedback` |
| C24 | v4 C9, v5 N47 | `runs.outcome_label` (3) ve `eval_scores.outcome` (8) ayrı terimler; 06:18, 09:17 |

## D. MINOR'lar

Kabul edilip uygulananlar: v4 N1 (03:90), N2 (00:37), N3 (06:95), N4 (01:14), N5 (06:125), N6 (09:88), N7 (05:38), N8 (PLAN 6), N9 (01:3), N10 (00:13), N11 (00:40 → 04a), N12 (00:15), N13 (= B6), N14 (03:3), N15 (= B5 ile çözüldü: `chunks`/`few_shots` istisna), N16 (05:6), N17 (05:48), N18 (06:83), N19 (07:23), N20 (08:82), N21 (08:65), N22 (09:50), N23 (10:41-42, MULTI_AGENT), N24 (12:7), N25 (12:11), N27 (15:7), N28 (16:13); v5 N4, N11, N16, N23, N47; v4 C5 (07:40), C10 (13:48), C12 (14:69), C14 (07:22, 15:19), C15 (PLAN 6), C16 (16:13), C20 (16:23).

**Reddedilen:** v4 N26 (`memories.scope` şimdiden) — ARCH-07, additive sonra.

## E. Takvim

PLAN 7: toplam ≈101 agent-günü, PoC ≈51, kritik yol ≈31 iş günü (eski "~20 gün" düzeltildi). Kapı kuralı dalga değil doğrudan bağımlılık (EXECUTION_HANDBOOK 1-2, WORK_QUEUE, BASLATMA 3). Süre tahminleri paket başlıklarına işlendi (v4 §6, v5 §6, v6 S1 ortalamaları).

## F. Reddedilen reviewer önerileri

- 08'i dalga 3'e taşımak (v6 B2 önerisi): 03a merge'ünden sonra başlaması yeter; dalga 2'de kalır.
- "Ölçüm sonra" tarzı ertelemelerle alan bırakmak (`chunk_strategy`): tek değer sabitlendi.
- Doğrulanmamış iddiaları brief'e olgu gibi yazmak: U listeleri `state/BLOCKERS.md` DRIFT-5..9 olarak işçi planlarına "doğrula" maddesi oldu.

## Reviewer'ların kendi "doğrulanmadı" listesi

v4 §8 (1-8), v5 §8 (U1-U5, U12), v6 §8 (U1-U4): ilgili brief'lerde "doğrulanır" ifadesiyle işçiye bırakıldı; BLOCKERS 5-9.
