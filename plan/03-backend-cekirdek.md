# 03. Backend çekirdek: kimlik, proje, katalog, audit; (03c) API key, kota, retention, uyarılar [FFCore Gateway]

**Bağımlılık:** 00. **Süre:** 8,5 gün (03a 3 + 03b 2 + 03c 3,5). **Dalga:** 03a ve 03b dalga 2; 03c PoC sonrası (06b ile aynı dalga).

**(P1, A2) Üç alt paket, üç PR:**
- **03a, kimlik ve kaynak kataloğu (PoC):** `users, projects, project_members, providers, provider_projects, model_catalog, models` + auth API + proje API + sağlayıcı/model CRUD + `POST /providers/test` + readiness + `core/secrets.py`. M1 için gereken kısım; 01 buna bağlıdır. **(A3) PoC'de atanan roller yalnızca `admin` ve `analyst`;** enum dört rolü taşır (`developer`, `user` rezerve), `access` kolonu ve `write=True` kuralı backend'de vardır (ucuz), salt-okunur modun ekran tarafı (düğme pasifleştirme, iki modda ekran görüntüsü) PoC sonrası 10c'de.
- **03b, audit ve iç kimlik (PoC):** `audit_events` + `core/audit.py` decorator'ı + on-behalf-of JWT (`resolve_actor`) + iç servis hesabı (`SERVICE_TOKEN`) + `core/egress.py` SafeOutboundClient (C5). M2 için gereken kısım.
- **03c, yönetişim (PoC sonrası, 06b ile):** `api_keys, quotas, usage_daily, retention_policies, alert_rules, alerts, notification_settings` + API'leri + kota motoru + retention işi + uyarı değerlendirici. PoC'de dış istemci olmadığı için ertelendi (karar A2); brief'teki tanımlar bağlayıcı kalır.
03a bitince 01 ve 08 başlayabilir; 03b paralel sürer. Aynı `backend/app/models/` dizininde ayrı dosyalara yazarlar; Alembic branch label'ları `03a`, `03b`, `03c`.

## Amaç

Diğer tüm paketlerin dayandığı temel: kullanıcı ve rol, proje, sağlayıcı ve model kataloğu, API anahtarı, kota ve kullanım sayacı, değişmez audit kaydı, veri saklama politikası.

## Kapsam

### Veri modeli (Alembic migration)

**03a, sağlayıcı ve model kataloğu** (alan davranışları 01 Kapsam "Sağlayıcı ve model kaydı gereksinimleri" bölümünde):
- `providers(id, key, label, description, driver, domains[], config_encrypted, supports_test, is_active, created_by)`; tenant düzeyi. Sürücüler ilk sürümde: `ollama, vllm, anthropic, openai, azure_openai, bedrock, openai_compatible` (Model/Embedding), `pgvector, qdrant` (Vector), `local_fs` (File).
- `provider_projects(provider_id, project_id)`; boş bırakılamaz, oluşturma sonrası atama adımı.
- `model_catalog(id, driver, model_id, category, capabilities jsonb, input_types[], context_window, max_output, pricing jsonb, updated_at)`: "Fill from catalog" için statik katalog, repo'da YAML'dan yüklenir.
- `models(id, project_id, key, display_name, provider_id, category: llm|embedding|stt|tts|ocr|moderation, model_id, capabilities jsonb, input_types[], pricing jsonb, limits jsonb, reasoning_default, upstream_api: chat|responses, request_policy jsonb, embed_dim nullable, is_active)`; `key` LiteLLM sanal model adıdır (`chat-default`; `category=embedding` kayıtları süreç içi sürücüyle (`local_flagembedding`) çalışır ve LiteLLM'e yazılmaz, C10 tersine). Embedding modeli için `embed_dim` kayıt anında sağlayıcıya test çağrısıyla ölçülür ve P5 kuralıyla doğrulanır.
- API: sağlayıcı CRUD, `POST /providers/{id}/test`, model CRUD, `GET /projects/{id}/readiness`; her değişiklik 01'deki **uzlaştırıcıyı** (`litellm_reconcile`, LiteLLM DB model API'si; config dosyası yeniden üretilmez, C1) tetikler.

- `users(id, email, password_hash, full_name, is_active, is_superadmin, created_at, updated_at, deleted_at)`; **global tablo**, `project_id` taşımaz (CONTRACTS C3 istisna listesi, B5).
- (P4 kararı) Pilotta (M3-M5) son kullanıcı yoktur; sohbet analist ve bilgi işlem kullanıcılarıyla test edilir. Rol enum'una şimdiden `user` (son kullanıcı: yalnızca sohbet, kanallar ve kendi hafızası; yönetim ekranı yok) eklenir ama bu sürümde atanmaz; son kullanıcı açılışı ve AD/LDAP girişi M6 sonrası ayrı paket (17). Böylece sonradan migration ve yetki matrisi değişikliği gerekmez.
- Roller ve erişim modu: sabit dört rol `admin, developer, analyst, user` (`developer` ve `user` PoC'de atanmaz, rezerve; A3); her üyelik için `access: edit|read`. `project_members(project_id, user_id, role, access)`. Admin rolü proje üstü de olabilir (`users.is_superadmin`), onun da `read` modu vardır (denetçi, yönetici gözlemci). Rol "hangi ekranlar ve kaynaklar", erişim modu "değiştirebilir mi" sorusunu cevaplar; ikisi bağımsızdır. Eski "viewer" kavramı `analyst + read`'e karşılık gelir.
- `projects(id, key, name, description, created_by, created_at, updated_at, deleted_at)`; LiteLLM team eşlemesi **yoktur** (karar A4), `litellm_team_id` kolonu kaldırıldı.
**03b, audit ve iç kimlik (PoC):** `audit_events`, on-behalf-of, `SERVICE_TOKEN`, `core/egress.py` (aşağıda). **03c, yönetişim (PoC sonrası):**
- `api_keys(id, project_id, name, key_prefix, key_hash, scopes[] (chat_direct, agents, impersonate, kb_search, tools_invoke), acl_role: admin|developer|analyst (varsayılan `analyst`; anahtarın kendisi aktörken KB ACL bu role göre, B7), allowed_cidrs text[], expires_at, last_used_at, revoked_at, created_by)`; ham anahtar yalnızca oluşturma cevabında bir kez döner. LiteLLM anahtarı yoktur; dış istemci facade'a (06b) bu anahtarla gelir, facade LiteLLM'i tek iç anahtarla çağırır (01 A4).
- (R2.1, C20) `quotas(id, scope_type: project|api_key|user, scope_id, project_id, label, priority, windows jsonb {rpm, rph, rpd, rpm_month, concurrent}, tokens jsonb {tpm, tpd, tpm_month, max_input, max_output, max_total}, budget jsonb {daily_usd, monthly_usd}, action: block|warn, is_active, activate_at)`. `group`, `model`, `provider` kapsamları bu sürümde yok (uygulayıcısı yok, ARCH-13). (R2.3) **Uygulama yeri tek: backend** (Redis sayaçları; `concurrent` 06 scheduler ile ortak; LiteLLM team yok, A4). API anahtarı ve proje bütçesi Redis sayaçlarıyla **anlık** uygulanır; `usage_daily` yalnızca raporlama. "Proje limiti alt kapsamlar için tavandır."
- `usage_daily(project_id, date, model, api_key_id, user_id, input_tokens, output_tokens, cost_usd, requests)`; LiteLLM spend verisinden (metadata'daki `api_key_id`/`user` ile) saatlik senkron (arq cron); yalnızca raporlama ve uyarı eşikleri için, bütçe kararı Redis sayacından (C20).
- **(03b)** `audit_events(id, ts, actor_type: user|api_key|system, actor_id, project_id nullable, action, resource_type, resource_id, outcome, before jsonb, after jsonb, request_id, ip)`; yalnızca INSERT; Postgres rolü ile UPDATE/DELETE engellenir; aylık partition; append-only olduğu için C3 ortak kolonlarının istisnasıdır (B5).
- (R2.2) `retention_policies(data_class, keep_days, min_days, max_days, expiry_behavior: delete|clear_content)`; **tek sınıf listesi:** `content 30 (1-90, clear_content), telemetry 90 (30-400), traces 30 (7-180), jobs 90 (30-365), metrics 45 (7-180), alerts 180 (90-730), audit 365 (365-3650), usage 760 (400-1095), results 365 (90-3650), memory 365 (30-1095, kullanıcı silince anında)`. Diğer paketler bu listeye yalnızca referans verir.
- (R9.1) **Uyarılar:** `alert_rules(id, project_id nullable, kind: budget_threshold|service_down|ingest_error|sync_error|prune_refused|approval_pending_age|guardrail_block_rate|quota_warn|convert_timeout|disk_memory, params jsonb (eşik, pencere), channel: email|webhook|ui, recipients[], is_active)`, `alerts(id, rule_id, fired_at, payload jsonb, severity, acked_by, acked_at, resolved_at)`. Değerlendirme `arq` `cron_jobs` ile dakikalık, worker sürecinde tek örnek (APScheduler yok, C9; kural listesi her koşuda DB'den okunur, dinamik cron gerekmez); `service_down` `/readyz` 5 dk başarısızlıkta; `budget_threshold` %50/80/100; `quota_warn` `quotas.action=warn` aşımında. Readiness listesi "en az bir aktif alert kuralı" diye bunu sorar. Teslimat: tablolar, değerlendirici, e-posta ve webhook gönderici, API (kural CRUD, uyarı listesi, ack), 10'da "Uyarılar" ekranı. Diğer paketler yalnızca olay üretir (`alerts.emit(kind, payload)`), kanal seçmez.
- `notification_settings(project_id nullable, smtp jsonb (şifreli), default_webhook_url, from_address)`: 07'nin e-postası ve 15'in uyarıları buradan okur; tek SMTP ayarı. Webhook gönderimi `core/egress.py` üzerinden (C5).
- **(03b, R2.5, C3)** On-behalf-of: iç servisler ve facade, çağıran son kullanıcıyı `X-On-Behalf-Of` başlığıyla taşır: değer backend'in imzaladığı kısa ömürlü JWT (`sub=user_id, project_id, exp ≤ 5 dk, aud=<hedef servis ya da tool_key>`); **her araç/servis çağrısında yeniden imzalanır** (uzun CPU run'ında süresi dolmasın, C3), `forward_user` bağlantıları havuzlanmaz. Yalnızca `impersonate` kapsamlı API anahtarı (03c) ya da iç servis hesabı (`SERVICE_TOKEN`) ile kabul edilir; doğrulama `core/auth.py` `resolve_actor()` içinde tek yerde. 04 arama API'si, 05 mcp-search ve 06 facade bunu kullanır; ACL, hafıza ve audit aktörü bu kullanıcıdır.
- **(03b, C5) `core/egress.py` SafeOutboundClient:** tüm dış HTTP çağrıları (webhook, araç uç noktası, MCP upstream, kanal, kaynak) bu istemciden geçer: URL ayrıştırma, DNS çözümleme ve **her redirect'te** IP kontrolü (loopback, RFC1918, link-local engelli; `ALLOWED_INTERNAL_HOSTS` ile açılır), `llmaas` izin listesi (`EGRESS_ALLOWLIST`), `OFFLINE=true` iken dış adres reddi, connect/read/total timeout zorunlu, secret-free hata. Kabul testleri: loopback, RFC1918, link-local, DNS rebinding ve izin listesi dışı alan adı reddedilir.

### API (FastAPI, `/api/v1`)

- Auth: `POST /auth/login` (JWT, httpOnly cookie, `SameSite=Strict; Secure`), `POST /auth/logout`, `GET /auth/me`. Şifre: argon2. **(C6)** Önyüz backend'e Next.js rewrite ile aynı origin'den gider; CORS `allow_credentials` açılmaz, ayrı CSRF token'ı yoktur (ARCH-07); kabul testi: farklı origin'den gelen cookie'li mutasyon 403.
- Users (admin): CRUD, rol atama.
- Projects: CRUD (LiteLLM team açılmaz, A4).
- **(03c)** API keys: oluştur, listele, iptal et.
- **(03c)** Quotas: CRUD; tamamı backend'de uygulanır (R2.3, A4).
- **(03c)** Alerts: kural CRUD, uyarı listesi, `POST /alerts/{id}/ack`; `GET /alerts/count` (önyüz rozeti).
- **(03c)** Notification settings: görüntüle/düzenle (admin), `POST /notifications/test` (deneme e-postası/webhook).
- **(03c)** Usage: proje ve tarih aralığına göre özet.
- Audit: filtreli listeleme, CSV export (admin).
- **(03c)** Retention: politika görüntüle/düzenle, `dry-run` ve `run` (admin); zamanlı iş `arq` cron (C9), `RETENTION_DRY_RUN=true` varsayılan.
- Yetki: `require_role(project_id, min_role, write=False)` bağımlılığı; rol sırası `user < analyst < developer < admin` (R2.4; `user` rezerve, 17'de aktive edilir ve yalnızca `/chat`, kanallar, `/memories` endpoint'lerine erişir). Tüm mutasyon endpoint'leri (POST/PUT/PATCH/DELETE ve çalıştırma gibi yan etkili POST'lar) `write=True` ile işaretlenir; `access=read` olan kullanıcı bu endpoint'lerde rolü yeterli olsa bile 403 alır ve deneme audit'e `outcome=denied` yazılır. GET endpoint'leri rol yeterliyse iki modda da aynı veriyi döner. `GET /auth/me` cevabında `role` ve `access` birlikte döner; önyüz buna göre düğmeleri pasifleştirir, ama asıl koruma API'dedir.
- Salt-okunur modun istisnaları (kullanıcının kendi verisi): şifre değiştirme, tema ve dil tercihi, kendi hafızasını (14) silme ve kapatma, sohbet (11) yapma. Sohbet sırasında onay verme ve "sınava ekle" gibi platform mutasyonları yine `write` gerektirir.
- Test yardımcıları: her rol × erişim modu için fixture (`admin_edit, admin_read, developer_edit, developer_read, analyst_edit, analyst_read, user_edit, user_read`); yetki testleri bu matris üzerinde parametrik koşar. PoC'de koşan alt küme `admin_edit, admin_read, analyst_edit` (A3); kalanlar 10c ve 17 ile açılır.

### Altyapı

- `core/audit.py`: `@audited(action, resource_type, redact_fields=[...], audit_payload=True)` decorator'ı; before/after'ı otomatik alır, secret alanlarını (`password, key, token, secret`) ve `redact_fields` ile verilen alanları maskeler; `audit_payload=False` ile yalnızca olay yazılır, içerik yazılmaz (R10.1; 14 hafıza metni için bunu kullanır).
- (R2.6) Alembic: 03a ve 03b ayrı branch label'ları (`03a`, `03b`); dalga sonunda merge PR'ı.
- (R2.7) `models.embed_dim` ölçümü globalle (`EMBED_DIM`) uyuşmazsa model kaydı 400 döner (uyarı değil; P5 kuralı). 04 ile aynı cümle.
- `core/secrets.py`: Fernet ile şifreleme/çözme.
- `core/db.py`: async session, `project_id` zorunlu filtre yardımcıları.
- OpenAPI şeması Türkçe açıklamalı.

### Konsol incelemesinden türetilen gereksinimler (bağlayıcı)

- API anahtarı: `allowed_cidrs text[]` (boşsa her yerden); izin listesi dışından gelen istek OpenAI hata şemasıyla reddedilir: `{"error":{"message":"...","type":"permission_error","code":"ip_not_allowed"}}`. Tüm 4xx cevaplar bu şemaya (`error.type`, `error.code`) uyar.
- Anahtar görünürlüğü: herkes yalnızca kendi anahtarlarını görür (`api_keys.created_by`); `require_role(admin)` ile "tüm anahtarlar" listesi.
- **(03c)** Kota şeması (R2.1) tek formda kapsam, pencere, token, bütçe ve aktivasyon boyutlarını birleştirir; "proje limiti alt kapsamlar için tavandır"; tamamı backend'de (A4).
- `GET /projects/{id}/readiness`: model sağlayıcı atanmış mı, vektör sağlayıcı atanmış mı, proje yöneticisi var mı; (03c ile) en az bir limit var mı, en az bir aktif uyarı kuralı var mı; 10'da "Hazırlık: n/5" kartı. Proje sayfası sekmeleri: Genel, Üyeler, Sağlayıcılar, (03c) Anahtarlar, Limitler, Ayarlar.
- `provider_projects` boş bırakılamaz; sağlayıcı oluşturma sonrası UI atama adımına zorlar.
- Retention (R2.2) ekranı: sınıf başına süre, izin verilen aralık (`min_days/max_days` doğrulaması), kaynak (varsayılan/override), süre dolunca davranış (`expiry_behavior`: `content` sınıfında prompt/yanıt metni NULL'lanır, metrik kalır; diğerlerinde silinir), "dry run" varsayılan (`RETENTION_DRY_RUN=true`), "şimdi temizle" her zaman siler, proje bazlı istisna, imha kayıtları ayrı liste.
- İçerik saklama kuralı (02 ve 08 ile ortak): modele giden **maskelenmiş** metin `run_events.payload`'da saklanır; ham kullanıcı mesajı yalnızca `messages.content`'te kalır ve `content` retention sınıfına tabidir.


## Teslimatlar

- Migration'lar, modeller, router'lar, servisler.
- `tests/`: auth, rol kontrolü, API key hash doğrulama, audit kaydının mutasyonda otomatik düşmesi, retention dry-run sayımı.
- `docs/api.md`: endpoint özeti.

## Kabul kriterleri

- `analyst + edit` ile `POST /projects` 403 döner (rol yetersiz); `admin + read` ile `POST /projects` 403 döner (erişim modu yetersiz); her ikisi audit'e `outcome=denied` olarak yazılır.
- `admin + read` kullanıcı, `admin + edit`'in gördüğü tüm GET endpoint'lerinden aynı veriyi alır (parametrik test, endpoint listesi OpenAPI'den otomatik türetilir).
- Mutasyon endpoint'lerinden `write=True` işareti eksik olan varsa CI'da başarısız olur (OpenAPI üzerinde tarayan test: her POST/PUT/PATCH/DELETE'in `write` bağımlılığı olmalı; istisnalar açık listede).
- **(03c, R9.1)** Aylık bütçesi 100 USD olan projede harcama 80 USD'ye ulaşınca `budget_threshold` uyarısı e-posta ve UI'da görünür; `/readyz` 5 dk 503 dönünce `service_down` uyarısı düşer; `quotas.action=warn` aşımı uyarı üretir ve isteği engellemez.
- (R2.5) `impersonate` kapsamı olmayan anahtarla gönderilen `X-On-Behalf-Of` yok sayılır ve audit'e `impersonation_denied` yazılır; geçerli JWT ile gelen istekte ACL ve audit aktörü belirtilen kullanıcıdır.
- (C5) `core/egress.py` loopback, RFC1918, link-local, DNS rebinding (çözümleme sonrası özel IP) ve `llmaas` izin listesi dışı alan adını reddeder; `OFFLINE=true` iken her dış adres reddedilir; timeout'suz çağrı yapılamaz (tip düzeyinde).
- (C3) Aynı kullanıcı için 6 dakika arayla imzalanan iki on-behalf-of JWT'si ayrı `aud` ile doğrulanır; süresi dolmuş JWT 401, yanlış `aud` 403.
- **(03c, R2.1)** `scope_type=api_key, budget.daily_usd=1` olan anahtar 1 USD'yi aşınca kota motoru `quota_exceeded` kararı verir (unit test; facade'ın 429 dönmesi 06b kriteri).
- **(03c)** API key oluşturulduktan sonra DB'de ham anahtar yoktur; `key_hash` ile doğrulanır.
- **(03c)** Kota `monthly_usd=0, block` verilen projede kota motoru isteği reddeder (unit test); facade üzerinden gelen istek 429 döner (06b kriteri).
- `audit_events` tablosunda uygulama rolüyle `DELETE` denemesi hata verir.
- **(03c)** Retention `run` 31 gün önceki sahte `content` kayıtlarını temizler, audit kaydı oluşturur.

## Teknik notlar

- Çok kiracılı (tenant) yapı yok; ama `projects` üstüne ileride `tenant_id` eklenebilsin diye proje anahtarları global benzersiz.
- (R2.3, A4) Rate limit ve bütçe sahipliği tek yerde: backend (Redis; 06 scheduler ile ortak sayaç). LiteLLM team/`end_user` bütçesi kullanılmaz.

## Kapsam dışı

Bilgi tabanı (04), araç kaydı (05), agent (06), guardrail (08), önyüz (10).
