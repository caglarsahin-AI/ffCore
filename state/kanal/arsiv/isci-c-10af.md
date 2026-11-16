# Arşiv: isci-c · 10af

state/kanal/isci-c.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### C-10af-0001 · 2026-10-28 22:40 · → koordinator · ACK
Paket: 10a-formlar   Cevap: K-10af-0001
DURUM: OKUMA-TAMAM. Okunan gruplar 1-8 bu oturumda (C-10ab-0001); o okumadan bu yana main'de değişenler ayrıca okundu: KARARLAR 03a/04a/10a-bağlama/01/08-lite/imaj etiketi eklemeleri, docs/gateway.md, docs/onyuz.md farkı. K-10ab-0019 HANDOFF ve K-10af-0000/0001 okundu; kalıplar (ListState/QueryError, `data ?? []` yok, 401 → goToLogin/safeNext, errors.ts, WriteGate projectId) bağlayıcı.
Worktree `.worktrees/feat/10a-forms` @ 070d8b0, temiz. `FFCORE_VERSION=0.0.0-10af`, compose proje adı `10af`, volume'lar `ffcore-10a-nm(-pw)`.
Touch-zone: frontend/** (providers, models ekranları ve formları, tests), docs/onyuz.md. FOLLOWUP-67 kapsam dışı.
Sıra: 03a OpenAPI (sağlayıcı/model/sürücü/katalog uçları) ve mevcut ekranlar okunur → state/pr/10a-forms.md planı → DURUM: PLANNED; onaysız kod yok.

### C-10af-0002 · 2026-10-28 22:43 · → koordinator · DURUM
Paket: 10a-formlar   Cevap: K-10af-0001
DURUM: PLANNED. Plan: state/pr/10a-forms.md (kapsam, 12 e2e + birim test eşlemesi, felsefe kontrolü).
KARAR-GEREK (ayrıntı ve etkiler planda, öneri önce):
- D1 Proje admin'i `GET /providers` okuyamıyor (require_superadmin), model formu sağlayıcı seçemez. A (öneri): model ekleme bu PR'da süper yöneticiye, düzenle/sil proje admin'ine; FOLLOWUP 03 additive `GET /projects/{id}/providers`. B: backend ucu bu PR'da. C: elle kimlik (önermem).
- D2 e2e'den LiteLLM `/model/info` doğrulaması. A (öneri): compose `e2e.environment`'a `LITELLM_URL` + `LITELLM_MASTER_KEY` (test değeri, başlıkta; touch-zone +2 satır). B: Playwright sonrası `render-litellm CHECK=1` ayrı adım. C: yok.
- D3 e2e sağlayıcı adresi. A (öneri): ollama `http://fake-llm:11434` + komut satırında `ALLOWED_INTERNAL_HOSTS=litellm,fake-llm` (dosya değişmez). B: `http://litellm:4000`. C: .env.test değişikliği.
- D4 `upstream_api=responses`. A (öneri): görünür ama pasif, varsayılan chat. B: seçilebilir + uyarı. C: gizli.
Bulgu: `merge_config` config'i tamamen değiştirir; UI tam config + boş gizli alan için `"***"` gönderir. Gizli alanı silmek UI'dan mümkün değil (risk, planda).
Onaysız kod yok; yanıt bekliyorum.

### C-10af-0003 · 2026-10-28 22:45 · → koordinator · ACK
Paket: 10a-formlar   Cevap: K-10af-0002
Alındı: D1-D4 A koşullarıyla (ekle düğmesi proje admin'inde pasif + neden; compose iki satır yalnız interpolasyon + rapor dizininde sahte anahtar araması 0; tam komut docs/onyuz.md'ye; responses pasif seçenek açıklaması + listede "LiteLLM'de değil" işareti), FOLLOWUP-79/80. Koda geçiyorum, önce kırmızı test.

### C-10af-0004 · 2026-10-28 23:23 · → koordinator · KARAR-GEREK
Paket: 10a-formlar   Cevap: -
Bulgu (backend, touch-zone dışı, doğrulandı): çözülemeyen sağlayıcı host adı bağlantı testinde 500 veriyor. `POST /providers/{id}/test` (ve `/providers/test`) → `SafeOutboundClient` → `_PinnedBackend.connect_tcp` → `system_resolver` (`backend/ffcore/core/egress.py:187`) `anyio.getaddrinfo` → `socket.gaierror: [Errno -3] Temporary failure in name resolution`. gaierror httpx2.HTTPError değil, `_follow`'un except'leri yakalamıyor, `test_connection` da yalnız Egress* yakalıyor → ASGI 500. Kanıt: 10af stack backend logu, e2e test_10af_4 kurulumunda 500. Etki: host adı yazım hatası olan sağlayıcıda kullanıcı "Connection test failed" yerine 500 görür; aynı yol SafeOutboundClient kullanan her çağrıda (uzlaştırıcı dahil, doğrulanmadı) olabilir.
Seçenekler:
- A (öneri): backend sahibine küçük düzeltme (resolver'da OSError → `EgressRequestFailed`/connect hatası, `connection_failed` sonucu + negatif test), 10a-formlar'dan önce ya da ona paralel merge. Benim testlerim (D3 fake-llm, çözülemeyen host) düzeltme sonrası yeşil; o zamana kadar test_10af_3/4 kırmızı kalır.
- B: düzeltmeyi bu PR'a ben eklerim (backend/ffcore/core/egress.py + test, touch-zone genişlemesi, [A]). Etki: tek PR, ama backend review'u da gerekir.
- C: e2e'de fake-llm'i de başlatırım (`--profile test`, host çözülür) ve "başarısız test" kabulünü kapalı bir portla kanıtlarım. Etki: D3 değişir, backend hatası açık kalır (FOLLOWUP).
Ara durum: kırmızı koşu tamam (tests-only 86c04d8: 22/22 kırmızı, sebep eksik UI; tek istisna bu 500). Yeşil koşuya geçiyorum, sonuçları DURUM ile yazarım.

### C-10af-0005 · 2026-10-28 23:31 · → koordinator · ACK
Paket: 10a-formlar   Cevap: K-10af-0003
B alındı. Yapıldı: b1d07f6 `fix(03b): unresolvable host is a failed egress, not a 500` (egress.py `_PinnedBackend.connect_tcp`: resolver OSError → `EgressRequestFailed("egress_dns_failed", host:port)`, `from None`; politika kontrolleri önce ve aynı). Önce kırmızı: `test_03b_2_unresolvable_host_is_request_failed` (gerçek resolver, `no-such-provider.invalid`) ve `test_03b_2_resolver_os_error_is_request_failed` kırmızıydı (gaierror / OSError), `test_03b_2_unresolvable_host_still_needs_the_policy` baştan yeşil (politika lookup'tan önce). Şimdi egress + provider servis birim testleri 59/59, ruff temiz. API testi `test_03a_9_unresolvable_host_is_a_failed_test` (unsaved + stored → 200 + connection_failed) eklendi; test-int ve iki profil make test e2e koşusu bitince (aynı stack, fake-llm başlatınca e2e etkilenir).

### C-10af-0006 · 2026-10-29 00:27 · → koordinator · PR-HAZIR
Paket: 10a-formlar   Cevap: K-10af-0003
Branch `feat/10a-forms` · SHA 851de1d8991736850f1144a0d05d303910f436fc (070d8b0 üstüne 6 commit, ağaç temiz) · Sınıf [A] · Kanıt: state/pr/10a-forms.md.
Commitler: 86c04d8 test (önce kırmızı: 22/22 e2e), c66408c feat, c28eaf9 docs, b1d07f6 fix(03b) (touch-zone eki, K-10af-0003 B), 82219e6 test (DNS beklemesi), 851de1d docs (PNG).
Kapılar: önyüz tsc/eslint/vitest 89/check:api 0; backend make lint + make test 292/292 iki profil; make test-int 134/134 iki profil; compose config (varsayılan + e2e) 0.
e2e (gerçek backend + LiteLLM): 22 `test_10af_*` testi geçti. Tam takım temiz stack'te `--workers=2` ile 71/74; 3 hata değişmemiş eski testlerde (`test_10a_4_axe_contrast: providers light`, `test_10ab_3_members` ×2) 5 s zaman aşımı, aynı iki dosya tek worker 16/16. Varsayılan worker'la 60/74 (makine yükü: 02 + 04a stack'leri açık). Yani tek seferde 74/74 kanıtım YOK; PR'da NOT_RUN ve risk olarak açık yazdım.
D2 kontrolü: LiteLLM master key `frontend/test-results` ve 6 e2e logunda 0 (sınır: test-results yalnız son koşu).
Stack `down -v` (0 konteyner/volume). İmajlar `ffcore/backend:0.0.0-10af`, `ffcore/tools:0.0.0-10af` duruyor.
İnceleyiciye not: backend kısmı (egress.py) ayrı bölümde; compose iki satırı paylaşılan değişiklik (04a ile rebase sırası).

### C-10af-0007 · 2026-10-29 08:59 · → koordinator · PR-HAZIR
Paket: 10a-formlar   Cevap: K-10af-0007
r2 delta. Branch `feat/10a-forms` · SHA 275d06d8224e40a02b0dfc1d2bfbcba0b014c98a (851de1d üstüne 3 commit, ağaç temiz) · kanıt state/pr/10a-forms.md "Review r1 bulgu → düzeltme → kanıt".
MINOR-1: c13cb2b test (önce kırmızı: e2e `test_10af_16_project_switch` 2/2, birim `test_10af_17_form_save_gate` 2/2), f08b5b6 fix (`ModelList key={projectId}`; model ve sağlayıcı formunda Kaydet WriteGate içinde), 275d06d PNG.
Ek bulgu, aynı commit'te kapandı: `Models.extraBodyHint` JSON örneği ICU argümanı sanılıyordu (INVALID_MESSAGE); EN/TR tırnaklandı, `test_10af_18_messages_parse` önce kırmızı sonra yeşil.
Kapılar: tsc/eslint/vitest 93/93 (18 dosya); tam Playwright tek worker temiz stack **76/76** (4,8 dk) f08b5b6'da; master key araması 0; stack `down -v`. Backend değişmedi (r1 sonuçları geçerli).

### C-10af-0008 · 2026-10-29 09:31 · → koordinator · HANDOFF
Paket: 10a-formlar   Cevap: K-10af-0011
### 10a-formlar · ffcore-isci-c-10af · 2026-10-29 09:31
- Durum: MERGED (r2 ONAY 275d06d → main 7457e82). Lease RETIRED.
- Tam sonraki adım: 10b-poc, yeni oturumda (GOREV koordinatörden).
- Kararlar (K-10af-0002/0003, hepsi bağlayıcı):
  - D1 A: model ekleme yalnız süper yönetici (sağlayıcı listesi `require_superadmin`); proje admin'i düzenler/siler, ekle düğmesi nedenli pasif (`data-needs-superadmin`); düzenlemede `/providers` çağrısı yok. FOLLOWUP-79: 03 additive `GET /projects/{id}/providers` gelince kısıt kalkar (`app/(console)/models/page.tsx` `DisabledWithReason`, `components/model-form.tsx` `useProviders(!model)`).
  - D2 A: compose `e2e.environment`'a `LITELLM_URL` + `LITELLM_MASTER_KEY` (yalnız interpolasyon, test tarafında başlıkta; `tests/e2e/api.ts` `expectInLiteLLM`).
  - D3 A: e2e sağlayıcı adresi `http://fake-llm:11434`, stack komut satırında `ALLOWED_INTERNAL_HOSTS=litellm,fake-llm`; fake-llm başlatılmaz (başarısız test yolu). fake-llm `--profile test` ile açılırsa test_10af_3/12 beklentisi değişir: test-int'ten önce e2e, sonra `rm -sf fake-llm`.
  - D4 A: `upstream_api=responses` yeni modelde pasif; mevcut model düzenlenebilir, listede "Not in the gateway" rozeti (`lib/model-form.ts notInGateway`). `forward_unknown_params` her zaman `false` gönderilir.
  - FOLLOWUP-80: gizli alan UI'dan silinemez (boş = `***` = koru; `lib/provider-config.ts buildConfig`).
  - K-10af-0003 B: `core/egress.py` resolver `OSError` → `EgressRequestFailed("egress_dns_failed")` (b1d07f6); bağlantı testi 200 + `connection_failed`.
- Kalıplar (10a-bağlama'nınkilere ek):
  - Form parçaları `components/form-parts.tsx` (`FieldShell`, `TextField`, `CheckGroup`, `CheckField`); yeni formlar bunları kullanır.
  - Proje kapsamlı liste ekranı proje kimliğiyle key'li (`<ModelList key={projectId}>`); her Kaydet `WriteGate` içinde (açma düğmesi yetmez) — review r1 MINOR-1.
  - Mesajda süslü parantezli örnek ICU tırnağı ister (`'{...}'`); `test_10af_18_messages_parse` her EN/TR mesajı denetler.
  - Sürücü alanı etiketleri `ProviderFields.<alan>`; canlı `/provider-drivers`'ta mesajı olmayan alan `test_10af_1`'i kırmızı yapar.
- e2e komutları (docs/onyuz.md "Acceptance tests"): `export ALLOWED_INTERNAL_HOSTS=litellm,fake-llm FFCORE_VERSION=0.0.0-<paket>` (+ `BACKEND_PORT=<boş port>` başka stack 8000'deyse); `up -d --wait --build backend` → `create-superadmin` (stdin) → `--profile e2e run --rm e2e` → `down -v`. Paylaşılan makinede `--workers=1` önerilir (varsayılan worker'da 5 s beklemeler yük altında düştü; tek worker temiz stack 76/76). Aynı stack'te tekrarlı koşu sağlayıcı biriktirir (4. koşuda 68), kanıt koşusu temiz stack'te. Docker içinde çözülemeyen ad 4-8 s'de düşer; bağlantı testi beklemeleri 20 s. e2e `npm ci` bazen ağ hatası verir, tekrar denenir; `ffcore-10a-nm-pw` volume'u 10a-bağlama öncesinden, `@tanstack/react-query` yok (kopyalamayın, `npm ci`).
- Koşan / kalan testler: Vitest 93/93 (18 dosya), Playwright 76/76 tek worker (f08b5b6), backend make test 292/292 ve test-int 134/134 iki profil (b1d07f6/82219e6). NOT_RUN: Lighthouse (FOLLOWUP-37), iki profil e2e (önyüz profil bağımsız).
- Blocker'lar: yok.
- Commit edilmemiş durum: yok (worktree ve branch koordinatörce kaldırıldı).
- Branch ve son commit: feat/10a-forms (silindi) @ 275d06d8224e40a02b0dfc1d2bfbcba0b014c98a → main 7457e82.
- Ortam: `10af` stack'i `down -v` (konteyner/volume 0). Scratchpad'deki loglar oturuma özel, depoya girmedi.
