# Kararlar Defteri

Brief'lerde yazmayan ama planı şekillendiren kararlar. Koordinatör oturumu bu dosyayı PLAN.md ile birlikte okur. Yeni karar alındığında buraya tarihle eklenir; brief değiştirilecekse brief de güncellenir. Her karar üç durumdan birindedir (FELSEFE DOC-16): **çözüldü** (gerekçeli, aşağıdaki bölümler), **reddedildi** ("Reddedilenler"), **bilinçli ertelendi** (yön ve kısıt sabit, "Ertelenenler ve açık konular"). Tersine dönen karar silinmez, "tersine karar" diye işaretlenir. Agent bir konuyu kendi başına "çözüldü" yapamaz.

## Ürün ve pazar

- **Ürün varsayılanı `llmaas`** (26 Ekim 2026): model sağlayıcıdan, veri ve orta katman kurumda. Türkiye Hastanesi pilotu da bu profilde. `airgap` ikincil profil, tam desteklenir; geliştirme sunucusu (internetsiz, Qwen 3.5 35B Ollama CPU) airgap testleri için kullanılır.
- Cognipeer'e alternatif, açık kaynak parçalar üstünde kendi ürünümüz; 8 çekirdek özellik + kullanıcı hafızası + kanallar + veri kaynakları. Cognipeer'in 31 servisinin geri kalanı (GPU fleet, voice, sandbox, red team, crawler, web search) kapsam dışı.
- Lisans tamamen bizim; Cognipeer fork edilmedi (AGPL ve Next.js bağımlılığı). Ürün kodu müşteri deposunda yaşamaz (karar 1).
- **Ürün adı FFCore** (27 Ekim 2026): modüller Gateway, Trace, Knowledge, Tools, Agents, Guard, Eval, Console, Channels, Platform (PLAN.md 1b). ffcore.com dolu; alan adı adayları ffcore.com.tr, ffcore.ai/io, en son ffcoretr.com; marka araması (Türk Patent, EUIPO) yapılacak.
- Ürün FF ailesinin (FFEngine, FFGov) parçası, sahibi biziz. PayCore bir müşteridir; PayCore LLM projesi yalnızca ölçüm ve ders kaynağı olarak referans alınır, ürün adı ve alan adı PayCore'a bağlanmaz.

## PayCore entegrasyonu (27 Ekim 2026; inceleme v9/v10, yedi kullanıcı kararı)

- **Canlı test yeri PayCore LLM** (`C:\ai_paycore\paycoreLLM`, internetsiz sunucu, Qwen CPU, Qdrant). PoC profili `airgap`; ürün varsayılanı `llmaas` değişmez (TH ikinci kurulum). **Tersine karar:** önceki "airgap sertifikasyonunu ertele" önerisi geçersiz.
- **Karar 1, depo:** FFCore ayrı depoda; paycoreLLM tüketici (path bağımlılığı / wheel + imaj). PayCore'a özgü `jira/`, `prsim/`, `router/` uzantı olarak kalır (CONTRACTS C14). "Monorepo, bu klasör" kararı FFCore deposu için geçerliliğini korur; çalışma ve test yeri paycoreLLM'dir.
- **Karar 2, anayasa:** paycoreLLM kökünde FFCore CLAUDE.md; PayCore'un sıkı kuralları aynen; "dal açılmaz, doğrudan master" kuralı FFCore branch + PR akışıyla değişti (tersine karar, PayCore 02_agentic §5).
- **Karar 3, W17 kilidi:** 00i (Faz 1 açıkları) MERGED olduktan sonra yalnızca sentetik sunum DB'si için açılır; PayCore'un "Faz 1 bitmeden Faz 2 kodu yok" kuralı koşullu tersine döndü (26 Ekim kararı).
- **Karar 4, S1 seti:** iç dokümantasyon sorusu, müşteri verisi değil (`.gitignore` notu, 2 Ekim); FFCore deposuna kopyalanmaz; PoC kalite kabulü bu settir (≥ %80).
- **Karar 5, PRSIM:** kişi adı/e-posta içeriyorsa ingest'e guard eklenir; 08 devreye girene kadar **ertelendi**, koşullu.
- **Karar 6:** 4B router modeli PoC'de kapalı; PayCore profilleri FFCore agent'larına eşlenir (`definition.knowledge[].filter`, C8 additive).
- **Karar 7:** PoC chat'i Open WebUI; 11 PoC sonrası.
- **Bellek:** sunucu belleği artırılır; buna rağmen modeller yalnızca API sürecinde, bütçe tablosu ölçülür (00i).
- **Yığın kararları (PayCore seed'i):** Qdrant + bge-m3 sparse birincil (pgvector ürün varsayılanı kalır); **embedding süreç içi `FlagEmbedding` dense+sparse, C10 tersine** (Ollama sparse üretmez, U14 doğrulanacak); DuckDB belge deposu PoC'de `KnowledgeStore` bağdaştırıcısıyla sarılır, Postgres göçü 04b (`DEBT-1`); LiteLLM ve arq + Redis eklenir, PayCore Jira kuyruğu arq'a taşınır; Langfuse v3 (v2'de gönderilmiş iz yok); PaddleOCR; güven formülü seed'de `max` (PayCore ölçümü) ama rozet yine kapalı; PoC'de iki agent (`always` doküman asistanı, tek çağrılı onaylı SQL), `mode: tool` GPU/llmaas'ta ölçülür (PayCore CPU ölçümü: 165-320 sn/soru).
- **Reddedilen (v10):** FFCore'u PoC'den çıkarıp yalnızca PayCore Faz 1'i bitirmek (başka soruya cevap); tek kök paycoreLLM (sahiplik ve TH taşınabilirliği); Postgres kuyruğunu korumak (Redis zaten gerekli); LiteLLM'i çıkarmak (iki çağrı yolu oluşur).

## Veri ve güvenlik

- Hasta verisi platformda yok; lakehouse'ta (CDC ile FFEngine besler) kalır. RAG yalnızca sözleşme, prosedür, kurumsal doküman.
- Text-to-SQL serbest SQL'dir, ama yalnızca ayrı ve salt-okunur "agent sunum DB'sine"; sqlglot doğrulaması, satır ve süre sınırı; kişi düzeyi veri yükleme anında maskelenmiş.
- Lakehouse üç katman (bronze/silver/gold) ve iki sunum DB'si (Superset, agent); bilgi tabanı da üç katman (raw/silver/gold).
- Dışa açılan tek adres backend facade; LiteLLM ve Langfuse iç ağda. `llmaas`'ta egress yalnızca izin listesi.
- Embedding her profilde yerel ve **süreç içi** (bge-m3 dense + sparse; C10 tersine döndü 27 Ekim); belge indekslenirken dışarı çıkmaz. Kurulum başına tek embedding modeli.
- Güven rozeti ve Türkçe düzeltme normalizer'ı varsayılan kapalı (PayCore ölçümleri); gerçek Türkçe NER modeli kullanılır.

## Kimlik ve roller

- **(A3, 27 Ekim) PoC'de giriş kalır ama küçülür:** e-posta+şifre, atanan roller yalnızca `admin` ve `analyst`; `developer` ve `user` enum'da rezerve; `access=read` kuralı backend'de var, ekran tarafı (düğme pasifleştirme, iki modda ekran görüntüsü) 10c'de PoC sonrası. Giriş tamamen çıkarılmadı: ACL, onay ve audit aktörü ona dayanır.
- **(A4, 27 Ekim) LiteLLM team/sanal anahtar/`end_user` bütçesi kullanılmaz:** backend LiteLLM'i tek iç anahtarla çağırır, proje/kullanıcı `metadata` ile gider, kota ve bütçe tek yerde backend'de (03c). `projects.litellm_team_id` kaldırıldı.
- **(A2) API anahtarları, kotalar, retention, uyarılar, bildirim ayarları 03c'dir (PoC sonrası, 06b ile):** PoC'de dış istemci yok; iç servisler `SERVICE_TOKEN` ile.
- Roller admin, developer, analyst, user (rezerve); her rol `edit` ya da `read` modunda; salt-okunur kullanıcı aynı ekranları görür, değiştiremez.
- Pilotta (M3-M5) son kullanıcı yok; sohbet analist ve bilgi işlemle test edilir. Son kullanıcı açılışı ve AD/LDAP paket 17, M6 sonrası.

## Mimari sabitler

- **(C1, 27 Ekim) LiteLLM tek kaynak:** modeller yalnızca LiteLLM DB'sinde, `config.yaml`'da `model_list` yok; `render-litellm` = uzlaştırıcı. **Tersine karar (P6'nın ikinci yarısı):** sağlayıcı anahtarı LiteLLM'e ortam değişkeniyle değil model API gövdesiyle gider (çalışan konteynere env verilemez); LiteLLM'in anahtarı şifreli sakladığı 01 işçisi tarafından doğrulanır (U2).
- **(B3) LiteLLM içinde guardrail kancası yok;** tek denetim noktası backend (06a graf, 06b facade). **(C5)** Tüm dış HTTP çağrıları `core/egress.py` SafeOutboundClient'tan. **(C6)** Önyüz backend'e Next.js rewrite ile aynı origin'den; CSRF token'ı yok. **(C9)** Zamanlı işler `arq cron`, APScheduler yok. **(C10, tersine 27 Ekim)** Embedding süreç içi `FlagEmbedding` dense + sparse (Ollama sparse üretmez); reranker da süreç içi; ikisini yalnızca API süreci yükler. **(C2)** İki zaman aşımı: LLM çağrısı (60/600/120 s) ve run (`run_timeout_s` 120/900/300 s).
- **(A5, 27 Ekim) 09 Langfuse datasets/experiments üstüne kurulur** (DECISION-4 kapandı, ARCH-09); yerelde yalnız `eval_suites`/`eval_runs` özet tabloları. Judge evaluator OSS'de değilse scorer bizde koşar, skor Langfuse'a yazılır.
- **(B5) C3 ortak kolonlar yalnızca proje sahipli kök tablolar için;** istisna listesi CONTRACTS C3.
- **(A9) Paket 17 (AD/LDAP) Slack ve Teams'ten önce;** widget ve Mattermost yerel kullanıcılarla 15'te.
- LiteLLM config'i yalnızca `providers`/`models` tablolarından; çalışırken DB model API'si; ad uzayı `<proje>.<model>` ve `agent:<proje>/<agent>`.
- pgvector varsayılan, Qdrant ikinci sürücü (04b). Tek kuyruk kütüphanesi `arq`; kuyruk sınıfları etkileşimli / etkileşimli-düşük / arka plan; run = arq işi, model çağrıları `LLM_SLOTS` yuvasından (C8). **Tersine karar (27 Ekim, A8):** `BACKGROUND_WINDOW` profil seed değeridir; yalnızca `airgap` cpu'da `19:00-07:00`, `llmaas` ve `gpu`'da boş (arka plan gün içinde etkileşimli işten sonra koşar). Eski karar "her profilde mesai dışı" idi; llmaas'ta hiçbir şey korumuyordu.
- Her değişiklik audit'e (03b); retention sınıfları ve uyarılar 03c'de tek liste (PoC sonrası).
- Açık ve koyu tema; arayüz Türkçe, kod İngilizce.

## Geliştirme düzeni

- **Felsefe** (27 Ekim 2026): `FELSEFE.md` (kullanıcının geliştirme felsefesi) ve `handbook/FELSEFE_UYGULAMA.md` her kuralın üstündedir; her PR planında üç felsefe sorusu (ARCH-07, ARCH-09, ARCH-10/06) zorunlu; koordinatör her soruyu önerili sorar (META-01).
- **META-01 tersine karar — yapılandırılmış sorular** (28 Ekim 2026): önceki “seçenek menüsü sunma” hükmü kaldırıldı. Kullanıcı kararı gereken her soru 2-3 birbirini dışlayan A/B/C seçeneğiyle sorulur; koordinatör önerdiği seçeneği önce “Önerilen” diye işaretler, gerekçesini ve her seçeneğin etkisini/bedelini yazar. İşçinin önerisi koordinatör değerlendirmesinde görünür kalır. Serbest metin yalnız seçeneklerin kararı dürüstçe ifade edemediği durumda kullanılır.
- **Handbook** (27 Ekim 2026): kalıcı kurallar `handbook/` (sözleşmeler, değişiklik kontrolü A-D, yürütme, çoklu agent, güvenlik, test, sürüm, terimler), canlı durum `state/` (WORK_QUEUE, HANDOFF, BLOCKERS), giriş `CLAUDE.md`. FFEngine handbook'undan uyarlandı. Kararlar: tek edition ve lisans yok (ileride `core/features.py` kapısı); kanıt PR açıklamasında, ayrı evidence dosyası yok; yalnızca Claude Code (Antigravity kuralları yok).
- Monorepo, bu klasör. Dalgalar PLAN.md 7. **PoC = M1-M3** (A1): 00, 01, 02, 03a, 03b, 04a, 05a, 06a, 07, 08, 10a, 10b-poc, 11, 13a, 13b ≈ 51 agent-günü; kritik yol 00 → 03a → 01 → 04a → 05a → 06a → 07/11 → 13b ≈ 31 gün (eski "~20 gün" yanlıştı; toplam ~101 agent-günü). Kapı dalga değil doğrudan bağımlılık bazlıdır (E). 03 a/b/c, 04-06 a/b, 10 a/b/c, 13 a/b bölünmüş.
- 1 koordinatör + 3 işçi (A kritik zincir, B yan paketler, C önyüz) + dalga 1'de 13a için test agent'ı; PoC sonrası 2 geçici işçi (14, 16). Koordinatör kod yazmaz.
- Her paket kendi PR'ı; aynı dalgada ayrı Alembic branch label'ı; dalga sonunda merge PR'ı; CI tek head bekler.
- M3 karar noktası: Qwen CPU'nun araçlı agent'ı taşıyıp taşımadığı ve model/donanım kararı burada verilir.
- PayCore LLM deposu `C:\ai_paycore\paycoreLLM`: canlı test yeri ve tüketici (PayCore entegrasyonu bölümü). Okuma yasağı dosya düzeyinde: `.env`, `data/**`, `eval/results/**`; `eval/scenario*/questions.jsonl` ve `experts/*.yaml` okunabilir, kopyalanmaz.

## Reddedilenler (gerekçeli, FELSEFE ARCH-14)

| Reddedilen | Neden | Tarih |
|---|---|---|
| Cognipeer'i fork etmek | AGPL lisansı ve Next.js kilidi; sahiplenilemez | 24 Ekim |
| Kubernetes | Tek Linux sunucu, tek müşteri tipi; Compose yeter, K8s kalıcı karmaşıklık (ARCH-07) | 24 Ekim |
| SQLite vektör deposu | Eşzamanlı yazma ve ACL filtresi zayıf; pgvector ek servis istemeden aynı işi görür | 25 Ekim |
| Elle yazılan statik LiteLLM config | İki kaynak (DB ve dosya) sapar; config tablolardan üretilir (P1) | 26 Ekim |
| Ayrı `tool_invocations` tablosu | `run_events` ve `mcp_server_calls` zaten taşıyor (ARCH-09, R4.2) | 26 Ekim |
| İkinci kuyruk kütüphanesi (`rq`) | Tek kütüphane `arq`; iki kuyruk sistemi tutarsızlık riski (R10.8) | 26 Ekim |
| Kurulum başına birden çok embedding modeli | Vektörler karışır, yeniden indeksleme matrisi büyür; tek model, değişimde `migrate-vectors` | 26 Ekim |
| Güven rozeti varsayılan açık, Türkçe normalizer zorunlu | PayCore ölçümü: 0,7 eşiği yanlış cevap yakalamadı, doğru cevaplara güvensizlik işareti koydu; normalizer TR katmanı ölçülmeden açılmaz (K1/K3) | 26 Ekim |
| "Yalnızca önceden tanımlı sorgular, serbest SQL yok" | Kullanıcı kararı: serbest text-to-SQL var, ama yalnızca ayrı salt-okunur sunum DB'sine ve sqlglot doğrulamasıyla | 25 Ekim |
| Örtük Ollama→Anthropic fallback (01) | Sessiz degrade ve veri sınırı ihlali (ARCH-06, ARCH-10); fallback yalnızca açık `chat-fallback` kaydıyla ve kayıtlı olayla | 27 Ekim |
| Postman koleksiyonu içe aktarma (05b) | %1 senaryo, Postman zaten OpenAPI dışa aktarır (ARCH-07, META-06) | 27 Ekim |
| Dış istemcilere LiteLLM sanal anahtarı vermek | Tek giriş kapısı facade'dır; kota, guardrail ve audit backend'de tek yerde (R1.2). LiteLLM team anahtarı yalnızca backend'de | 26 Ekim |
| Sağlayıcı anahtarlarını yalnızca `.env`'de tutmak (FFEngine'in "credential tutmama" ilkesi) | FFEngine'de kimlik bilgisi Airflow Connection'da yaşar; FFCore'da böyle bir dış kasa yok ve sağlayıcı ekranı ürün gereksinimi. Anahtar DB'de Fernet ile şifreli, API'de maskeli, LiteLLM'e model API gövdesiyle (P6; "ortam değişkeniyle" yarısı tersine döndü, C1). Dış kasa (Vault) istek gelirse additive sürücü | 27 Ekim |
| LiteLLM team / sanal anahtar / `end_user` bütçesi (proje başına) | Facade tek kapı; kota backend'de; team anahtarı saklama kolonu ve 03↔01 döngüsel bağımlılık yaratıyordu (A4, B1) | 27 Ekim |
| LiteLLM içinde `CustomGuardrail` kancası (`litellm_hook.py`) | Dış istemci LiteLLM'e ulaşmaz; çift HTTP döngüsü (ARCH-09, B3) | 27 Ekim |
| APScheduler | `arq cron_jobs` yeter; ikinci zamanlayıcı çoklu worker'da mükerrer koşar (ARCH-09, C9) | 27 Ekim |
| `mode: tool` için `knowledge_read_document*` araçları | C7 donmuş sözleşme yalnızca `search_documents`; tam belge okuma CPU bütçesini aşar (C11) | 27 Ekim |
| `chunk_strategy` 5 seçenek, `separators`, `parent_window`, `contextual_headers`, `oversample`, `response_detail`, `filterable_fields` | Ölçülmüş tek yol `heading`; kalıcı test ve yeniden indeksleme matrisi (ARCH-07, C21) | 27 Ekim |
| `definition.webhook_url`, `budget_usd`, `raw_output_tools[]` | Tanımsız gizli özetleme adımı varsayımı; istek gelirse additive (ARCH-07/10, C21) | 27 Ekim |
| Kota kapsamları `group`, `model`, `provider` | Uygulayıcısı yok; "ekranda var, çalışmıyor" (ARCH-13, C20) | 27 Ekim |
| Ayrı CSRF token'ı | Next.js rewrite ile tek origin + `SameSite=Strict` yeter (ARCH-07, C6) | 27 Ekim |
| `EVAL_RESET_MODEL` (sınav öncesi model sunucusu sıfırlama) | Backend'e Docker soketi vermek güvenlik riski; `warm_cache` işaretlenir (N22) | 27 Ekim |
| `memories.scope` kolonunu şimdiden eklemek | YAGNI; additive sonra (N26) | 27 Ekim |
| 13'e gerçek sözleşme koymak (maskeleyerek) | Veri sınırı D sınıfı; ad-soyad recall'u 0,85 olan maskeleme sınırı taşıyamaz (B4/M7) | 27 Ekim |
| Zorla `finalize` (limit aşımında kısmi cevabı başarı gibi döndürmek) | Fail-loud: `failed` + `limit_reached`, kısmi çıktı işaretli (v6 M3) | 27 Ekim |
| Örtük `.env` yazan init scripti (02) | Agent ve script `.env` yazmaz; anahtar bir kez gösterilir (B6) | 27 Ekim |
| Reviewer önerisi: 08'i dalga 3'e taşımak | 03a merge'ünden sonra başlaması yeter; dalga değişmez (F) | 27 Ekim |
| Pilotta Keycloak / LDAP | Pilotta son kullanıcı yok; yerel kullanıcı + rol yeter. LDAP paket 17 (bilinçli ertelendi) | 26 Ekim |
| Cognipeer'in GPU fleet, voice, sandbox, red team, crawler, web search servisleri | Dar ve derin (ARCH-12); 8 çekirdek + hafıza + kanal + kaynak | 24 Ekim |

## Ertelenenler ve açık konular (kullanıcı kararı bekliyor; `state/BLOCKERS.md` DECISION kayıtları)

- **Bilinçli ertelendi:** son kullanıcı açılışı ve AD/LDAP (paket 17, M6 sonrası; `user` rolü rezerve). Ekip hafızası, webhook tetikleyici, zamanlanmış görevler (istek gelirse yeni paket; veri modeli engellemez).
- **Açık:** GPU satın alma, `docs/donanim.md` örnek verir; karar müşterinin.
- **Açık:** M3'te `rewrite` (çok biçimli sorgu) ve judge modeli; M4'te ad-soyad NER eşiği.
- **Kapandı (DECISION-4, A5):** 09 Langfuse datasets/experiments üstünde; işçi yalnızca OSS'de judge evaluator olup olmadığını doğrular.
- **Açık:** ffcore alan adı ve marka araması (DECISION-1).
