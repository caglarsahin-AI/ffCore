# Dalga raporu · 20 Kasım 2026 (dalga 7: kurulum ve triage, kapanış) · TASLAK

Yazan: koordinatör (lease ffcore-koordinator-20261102). Şablon: docs/takim/ajanlarla-gelistirme.md 9.3. Önceki rapor: state/dalga/dalga-6b-kapanis.md (onaylı 20 Kasım, "Onay, A: 12 + triage"). Onay: kullanıcı.

## 1. Dalga, paketler, main, kapı logları

Dalga 7 planı (20 Kasım, onaylı A): paket 12 (kurulum rehberi, daraltılmış kapsam) isci-a şeridinde iki PR; FOLLOWUP triage dilimi isci-b şeridinde; inceleyici tek oturum. Üçü de main'de; kapı logları `state/evidence/`.

| Paket | Merge (20 Kas) | Main kapısı | Log |
|---|---|---|---|
| fix/followup-triage-1: hook PROSES-175 kuralı (207), kota testi kararlı (201), admin kullanıcıya özel belgeyi tekil uçlarda yönetir (202), bir red = tek `denied` audit satırı (203), platform hedefi reddi beş yüzeyde + qdrant `url` (194), plan metni DuckDB cümlesi (DRIFT-198) | e9d0de6 (13:37) | yeşil 2014×2, test-int 1121, hooks host 347, Vitest 279 | gate-trj-20261120.log |
| 12-1: egress forward proxy overlay (Squid, `EGRESS_ALLOWLIST`, uygulama ağı `internal`), TLS ters proxy overlay (nginx; dış yalnız Teams yolu, sabit URI), `scripts/compose_preflight.py` + `make preflight`/`egress-list`, LiteLLM şema sağlığı, docs/kurulum.md 12-1 bölümleri, docs/veri-isleme.md | a7c861f (15:30) | yeşil 2073×2, test-int 1121, config egress+tls | gate-121-20261120.log |
| 12-2: `ffcore_app` en-az-yetkili Postgres rolü + SECURITY DEFINER audit bölüm fonksiyonları (365 gün tabanı), `deploy/backup.sh`/`restore.sh` + host provası, apt'siz tools imajı + iç ayna, vLLM overlay, docs/donanim.md, docs/kurulum.md tam akış, docs/kurulum-kapali-ag.md | 9c65d1f (18:11) | yeşil 2117×2, test-int 1143 (`ffcore_app` ile), config vllm | gate-122-20261120.log |

Test sayısı dalga boyunca 1959 → 2117 (birim+sözleşme, profil başına), 1076 → 1143 (entegrasyon; artık en-az-yetkili rolle). İnceleme turları: triage-1 2, 12-1 2, 12-2 2; toplam B0; MAJOR yalnız 12-2 r1'de (iki güvenlik/fail-loud bulgusu, r2'de kapandı). Push: `origin` ve `paycore` 1d82eba'da (20 Kas 12:0x); üç merge ve state commit'leri yerel.

## 2. Bu dalgada alınan kararlar (KARARLAR; tek cümle)

- 20 Kasım · Dalga 7: 12 (isci-a) + triage dilimi (isci-b), touch-zone ayrımı; dalga 6b raporu onaylı.
- 20 Kasım · triage-1 plan: tekil uçlarda admin muaf, liste süzgeçli; 203 sarmalayıcı tek satır; 207 belge metinleri; 194 beş yüzey; r1: `URL_FIELDS` + `url`, FOLLOWUP-210 çıplak docker build.
- 20 Kasım · 12 plan: 12-1 backend'siz (Squid, nginx, preflight fail-loud) ve 12-2 triage sonrası; D1-D6 hepsi A; `RESERVED_HOSTS` eki; r1: nginx sabit URI, Squid özel aralıklar, port denetimi, preflight yanlış pozitifleri; CONNECT-only FOLLOWUP-211 (B).
- 20 Kasım · 12-2 plan: 46 SECURITY DEFINER göçü, yedek provası host pytest opt-in, bütün test yığınları `ffcore_app` rolüyle; r1: audit bölüm fonksiyonlarına retention tabanı + INSERT/SELECT, `APP_DB_*` birlikte zorunlu.
- 20 Kasım · ENV-209: aynı makinede aynı anda tek tam test-int (sıra koordinatörden); FOLLOWUP-212: kapı hook adımı host `py -3.12`.

## 3. Tersine dönen kararlar

- Hook PROSES-175 kuralı: eski "önce `build --pull=false`, `up --build` yok" metni 5 Kasım kararıyla çelişiyordu; artık `up --build --pull never` kabul, her compose `build` uyarı (207). Belge metinleri (handbook, docs/takim) aynı turda düzeltildi.
- 12-1 r1 NOTE-2: "yalnız 443 CONNECT" karar metni, Squid'in izinli alana düz isteğe de izin verdiği gerçeğine göre düzeltildi; CONNECT-only sıkılaştırma FOLLOWUP-211 (test sahte sağlayıcısı TLS'e geçince).
- plan/04 ve PLAN 7'deki "DuckDB → Postgres göçü" cümleleri gerçek D1 ile değiştirildi (DRIFT-198 kapandı).

## 4. İnsana kalan açık konular

- **Push:** `FFCORE_PUSH_OK=1` ile origin ve paycore aynası (merge'ler e9d0de6, a7c861f, 9c65d1f + state; son push 1d82eba).
- **Hook kipi:** `FFCORE_GUARD_MODE` warn → block (önerim A: block; 207 kural düzeltmesi main'de, dünkü yanlış pozitif sınıfı kalktı; 210/212 küçük kalan).
- **Oturum arşivleri:** isci-b-04b, isci-b-triage1, isci-a-12 (HANDOFF sonrası) ve 6b'den kalan dokuz oturum.
- **Worktree ve imaj temizliği:** `.worktrees/` altında on iki worktree (04b ×2, 05b, 10c-2, 10c-3, hook ×2, sse, triage-1, 12 ×2 ...); imaj etiketleri 0.0.0-05b/10c2/10c3/04b/trj/12.
- **ENV-204:** `ollama/ollama:0.12.6` ile `/readyz` `ollama_runtime_context` doğrulaması.
- **ENV-209:** Docker Desktop iç DNS kesintileri (20 Kas üç kez); eş zamanlı tam test-int kuralı koordinatörde, Docker tarafı sizde.
- **12 PENDING_ENV (kullanıcı donanımı):** GPU vLLM sunumu + 10 eşzamanlı RAG P50/P95; ağsız tools derlemesi (iç ayna); test VM'de 1 saat kurulum provası; iki sürüm geri alma; kurumsal CA sertifikası; gerçek sağlayıcıya proxy'den çıkış.
- **Sunucu:** `.env` `FFCORE_VERSION=0.1.0-m3`; mevcut volume için `app-role.sql` tek seferlik komut (docs/kurulum.md); `APP_DB_*` çifti.
- **DECISION-1/2/3** açık (alan adı; `rewrite`/judge; NER eşiği).

## 5. Açık kayıt sayıları ve en riskli üçü

BLOCKERS.md 46,0 KB (>30 KB; DRIFT'lerin arşive taşınması önerisi sürüyor). Açık: FOLLOWUP 61, DRIFT 35, ENV 8, DECISION 3, DEBT 0. Bu dalgada kapanan: FOLLOWUP 202, 203, 194, 201, 207, 35, 66, 82, 46, 95; DRIFT-198. Açılan: FOLLOWUP 208-213; ENV-209.

En riskli üçü:
1. **FOLLOWUP-208** (03b egress): backend'in kendi dış çağrıları proxy'yi kullanamıyor; egress profilinde kanal/kaynak bağdaştırıcıları ve uzak MCP bağlantı hatası verir (belgeli, sessiz değil). Backend proxy desteği küçük PR.
2. **FOLLOWUP-211** (12 egress): Squid CONNECT dışı method'lara izin veriyor (tek port 443, pratik etki yok); sıkılaştırma test sağlayıcısı TLS'e bağlı.
3. **FOLLOWUP-213** (12 initdb/preflight): yalnız-parola durumunda initdb durmuyor, metin çelişkili; preflight yakalıyor.

## 6. Hook kayıtları (20 Kas 00:00 - 18:50; 32 satır, hepsi warn)

KAPI 25 (komut metninde test sözcükleri; kanal ve log komutları), PROSES-175 3 (eski kural; 207 ile kapandı), TEK-YAZAR 2 (işçilerin kendi PR notları), ENV 2 (compose/Makefile düzenlemeleri, onaylı touch-zone). Gerçek ihlal yok. Not: işçi A bir kez `state/` yazımını kabuk hatasıyla kaçırdı (zil dosyadan önce gitti), düzeltildi; işçi A bir kez kapı duyurusundan önce başlamış koşuyla ffmain'e ~10 dk çakıştı, kendisi kapattı.

## 7. Sıradaki dalga için seçenekler (karar kullanıcıda; önerim A)

- **A (önerim): 11 son kullanıcı chat arayüzü (DECISION-193 A, kendi `/chat` ekranı) + paralel küçük hook/egress dilimi.** 11: 06a/07 üstüne kaynak kartları, ilerleme (`x_platform`), onay akışı; isci-c (önyüz) şeridi. Paralel küçük dilim (isci-b, backend/hook): `FFCORE_GUARD_MODE=block` geçişi + FOLLOWUP-210 (çıplak docker build) + 212 (hook testi `py`) + 213 (initdb metni) + 208 (backend proxy desteği, `EGRESS_PROXY_URL`). Etki: kurulum (12) hazırken kullanıcıya görünen özellik; 14/15/17 11'e bağlı olduğundan kritik yol.
- **B: 14 kullanıcı hafızası.** Etki: 11 olmadan yalnız backend yarısı; ekran bekler; önerilmez.
- **C: 12 PENDING_ENV ölçümleri + FOLLOWUP-208 önce.** Etki: üretim kanıtı güçlenir ama kullanıcı donanımı ve zaman ister; A'nın paralel dilimi 208'i zaten alır, ölçümler kullanıcı tarafında sürer.

Her seçenekte: inceleyici tek oturum sürer; triage-1 ve 12 kanal arşivleri HANDOFF sonrası.

## Onay

Kullanıcı bu raporu okuyup onaylar ya da bir maddeyi geri çevirir; koordinatör onayı WORK_QUEUE "Kapılar" tablosuna tarih ve rapor yoluyla yazar. Onayla birlikte seçilen dalganın GOREV'leri yazılır.
