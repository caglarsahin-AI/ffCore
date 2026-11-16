# Arşiv: koordinator · 10af

state/kanal/koordinator.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### K-10af-0000 · 2026-10-28 20:44 · → kullanici · DURUM
Paket: 10a-formlar   Cevap: -
TASLAK, GOREV DEĞİL; 01 MERGED olunca branch feat/10a-forms ve worktree ile K-10af-0001 olarak yeni isci-c oturumuna (boşta duran "C Workers sonraki" kullanılabilir) yazılır. İçerik:
Kapsam (K-10ab-0004 C-10ab-0006): sağlayıcı ve model formları: sürücüye göre dinamik alanlar (`GET /provider-drivers`), şifreli kimlik alanları (secret alanlar "***" döner, düzenlemede boş = değişmez), `POST /providers/test` (kaydetmeden) ve `/providers/{id}/test`, proje atama adımı (`provider_projects` boş olamaz), model formu: kategori önce zorunlu, `GET /model-catalog` ile "katalogdan doldur", `embed_dim` probe hataları (409 `embedding_probe_unavailable`, 400 `embed_dim_mismatch`) açık mesaj, `upstream_api`/`request_policy` alanları (`forward_unknown_params` yalnız false, DRIFT-72), pasifleştirmede 409 `provider_in_use` mesajı; 01 merge sonrası model kaydı LiteLLM'e uzlaştırıcıyla yansır (e2e: model ekle → `/model/info`'da görünür, iç anahtarla değil API ile doğrulanır).
Bağımlı teslimatlar: 10a-bağlama (main: QueryError/ListState kalıbı, `data ?? []` yasağı, 401 → `goToLogin`/`safeNext`, `errors.ts`, `WriteGate projectId`, C-10ab-0019 HANDOFF), 03a (OpenAPI, `backend/openapi/03a.yaml` main), 01 (uzlaştırıcı, `litellm_name`).
Kurallar: FOLLOWUP-67 (üye ekleme yolu) bu pakette değil (03 additive); şema üretilir, elle tip yok; EN kaynak + TR; sabit renk/metin yok; her ekran iki tema PNG; volume'lar `ffcore-10a-nm(-pw)`; `FFCORE_VERSION=0.0.0-10af`; Playwright gerçek backend; önce PLANNED (state/pr/10a-forms.md). Touch-zone: frontend/** (providers, models ekranları ve formları, tests), docs/onyuz.md.

### K-10af-0001 · 2026-10-28 21:29 · → isci-c · GOREV
Paket: 10a-formlar (sağlayıcı ve model formları)   Cevap: -
Taslak K-10af-0000'ın tamamı bu GOREV'in parçasıdır (kapsam, bağımlı teslimatlar, kurallar, touch-zone). Somut: Branch feat/10a-forms (main 070d8b0'dan; 01 uzlaştırıcısı main'de) · Worktree C:/ai_paycore/ffcore/.worktrees/feat/10a-forms · Sınıf [A] · `FFCORE_VERSION=0.0.0-10af`; volume'lar `ffcore-10a-nm(-pw)`; Playwright imajı digest pinli. Uçtan uca: form ile model kaydı → 01 uzlaştırıcısı → LiteLLM `/model/info`'da görünür (API ile doğrula; iç anahtar URL'de değil, 01 kuralı). Yeni oturum: ilk mesaj BASLATMA §3 şablonu `ROL=isci-c PAKET=10a-formlar`; okuma sonrası K-10ab-0019 HANDOFF'u ve bu GOREV'i oku. Önce PLANNED (state/pr/10a-forms.md).

### K-10af-0002 · 2026-10-28 22:46 · → isci-c · CEVAP
Paket: 10a-formlar   Cevap: C-10af-0002
Plan onaylı, dört kararın hepsi önerdiğin A; koşullarla:
- D1 A: model ekleme bu PR'da süper yöneticiye; proje admin'i düzenler ve siler (sağlayıcı alanı düzenlemede salt okunur gösterilir, liste çağrısı yapılmaz). Proje admin'i için `GET /projects/{id}/providers` FOLLOWUP-79 (03 additive). Proje admin'i ekranında ekle düğmesi gizli değil, WriteGate gibi açık nedenle pasif.
- D2 A: compose `e2e.environment`'a `LITELLM_URL` ve `LITELLM_MASTER_KEY`; değer yalnız `${LITELLM_MASTER_KEY}` interpolasyonuyla (.env.test), dosyada değer yok. Anahtar yalnız başlıkta; Playwright trace/rapor/konsolunda görünmediğine dair negatif kontrol (rapor dizininde sahte değer araması 0). Compose satırları PR'da paylaşılan değişiklik olarak işaretli; 04a da compose'a dokunuyor, sonra merge olan rebase eder.
- D3 A: `ALLOWED_INTERNAL_HOSTS=litellm,fake-llm` komut satırında; tam komut docs/onyuz.md "Acceptance tests" bölümüne yazılır (tekrarlanabilir olsun).
- D4 A: pasif seçeneğin açıklaması uzlaştırıcının `upstream_api_unsupported` reddine dayansın (metin en/tr json'da); kayıtlı `responses` modeli düzenlemede görünür, kaydedilebilir, ayrıca modelin LiteLLM'de olmadığı listede görünür olsun (sessiz değil).
Bulgu (gizli alan UI'dan silinemiyor): kabul, bu PR'da çözme; FOLLOWUP-80 (03 additive: gizli alanı açıkça temizleme). Planda risk olarak kalsın.
Not: "C Main" adlı başka bir oturum var; isci-c tek oturum sensin (ffcore-isci-c-10af). Kullanıcıya soruyorum; o oturumdan 10a-forms worktree'sine dokunan bir şey görürsen kanala yaz. Koda geç; önce başarısız test.

### K-10af-0003 · 2026-10-28 23:26 · → isci-c · CEVAP
Paket: 10a-formlar   Cevap: C-10af-0004
Koordinatör kararı: **B**, bu PR'da sen düzeltirsin. Gerekçe: egress.py'ye şu an başka branch dokunmuyor (04a ve 02 kontrol edildi), B ve A oturumları dolu, düzeltme küçük ve hata kullanıcıya ilk dokunan sensin. Touch-zone eki: `backend/ffcore/core/egress.py` + backend testi; sınıf [A]. Koşullar:
- Ayrı commit (`fix(03b): unresolvable host is a failed egress, not a 500`), PR'da "touch-zone dışı backend düzeltmesi" bölümü; inceleyici bu kısma backend gözüyle bakacak.
- Önce kırmızı test: gerçek resolver ile çözülemeyen host (`*.invalid`, RFC 6761) → bugün 500 / yakalanmamış gaierror.
- Düzeltme resolver noktasında: `OSError` (gaierror dahil) → `EgressRequestFailed` (kod ör. `egress_dns_failed`, mesajda host adı olabilir, upstream/sistem metni ham taşınmaz); politika kontrollerini (allowlist, private address) gevşetme, resolve sonrası kontrol sırası aynı kalsın.
- Testler: birim (resolver hatası tipli hata), API (`POST /providers/test` ve `/providers/{id}/test` → 200 + `connection_failed` sonucu, 500 değil), mevcut 03b/01 egress testleri yeşil; backend `make test` iki profil. Uzlaştırıcı yolu aynı resolver'dan geçtiği için ayrıca kod gerekmez, ama bir regresyon testi iyi olur.
D3 değişmez (fake-llm başarılı yol için; çözülemeyen host başarısız yol için kalır).

### K-10af-0004 · 2026-10-28 23:35 · → isci-c · CEVAP
Paket: 10a-formlar   Cevap: C-10af-0005
Alındı; b1d07f6 kırmızı→yeşil kanıtı iyi. test-int ve iki profil `make test` sonucu PR'a. Devam.

### K-10af-0005 · 2026-10-29 00:30 · → inceleyici · REVIEW-ISTEK
Paket: 10a-formlar (sağlayıcı ve model formları)   Cevap: C-10af-0006
PR: state/pr/10a-forms.md · Branch feat/10a-forms · Baz main 070d8b0 · SHA 851de1d8991736850f1144a0d05d303910f436fc (koordinatör doğruladı: 070d8b0 üstünde, ağaç temiz; 6 commit, 49 dosya, +2639/-34) · Sınıf [A]. Tur: r1.
Öncelikli bakılacaklar: (1) **backend kısmı** b1d07f6 `fix(03b)`: egress.py resolver OSError → `EgressRequestFailed("egress_dns_failed")`; politika kontrolleri (allowlist, private address, offline) gevşemedi mi, sıra aynı mı, sistem hata metni ham taşınmıyor mu; API testi 200 + `connection_failed`. (2) Gizli alanlar: secret config alanları API'de `***`, düzenlemede boş = değişmez, form state/URL/log/konsolda ham değer yok; FOLLOWUP-80 (silinemiyor) bilinen. (3) D1: proje admin'i model ekleyemiyor, ekle düğmesi pasif + neden; düzenle/sil yetkileri WriteGate ile; sağlayıcı listesi çağrısı proje admin'inde yapılmıyor. (4) D2: compose e2e env iki satır (`${LITELLM_MASTER_KEY:?}` interpolasyon, değer yok); anahtar yalnız başlıkta; Playwright rapor/trace/log negatif kontrolü. (5) D4: `responses` pasif seçenek + "LiteLLM'de değil" işareti, sessiz değil. (6) 10a-bağlama kalıpları (ListState/QueryError, `data ?? []` yok, 401 → goToLogin/safeNext, errors.ts yeni kodlar, en/tr json, iki tema PNG).
Bilinen sınır: tam e2e takımı tek koşuda 74/74 değil (`--workers=2` 71/74; 3 zaman aşımı değişmemiş eski testlerde, tek başına 16/16; makinede 02 + 04a yığınları açıktı). Bağımsız olarak tam takımı `--workers=1` ile koşmaya çalış; yine düşerse aynı üç test mi, bulguyu flake mi ürün mü diye ayır. Volume'lar `ffcore-10a-nm(-pw)`, review imajı `0.0.0-review-10af`.

### K-10af-0006 · 2026-10-29 00:30 · → isci-c · CEVAP
Paket: 10a-formlar   Cevap: C-10af-0006
PR-HAZIR alındı; SHA 851de1d doğrulandı (070d8b0 üstünde, temiz). REVIEW-ISTEK K-10af-0005 inceleyiciye gitti. Review bitene kadar yeni commit yok. `0.0.0-10af` imajları review sonrasına kadar kalsın.

### K-10af-0007 · 2026-10-29 00:54 · → isci-c · DUZELT
Paket: 10a-formlar   Cevap: R-10af-0004 (state/reviews/10a-forms-r1.md)
Review r1: ONAY, BLOCKER 0, MAJOR 0, MINOR 1. Koordinatör kararı: MINOR-1 merge'den önce bu PR'da kapanır (küçük, kabul kriteri "yetkisizde salt okunur" bu geçişte ihlal; backend 403 koruyor ama UI yanlış söz veriyor). Yeni commit, yeni tam SHA ile PR-HAZIR; r2 yalnız delta.
MINOR-1: alpha'da düzenleme yetkisiyle model formu açıkken üst çubuktan yalnız okuma yetkisi olan beta projesine geçince form açık ve Kaydet etkin kalıyor; PATCH beta/alpha-model gidiyor. Beklenen: (1) proje değişince açık form kapanır ve state sıfırlanır (liste ve form proje kimliğiyle key'li); (2) Kaydet düğmesi o anki projenin güncel yetkisine bağlı (WriteGate/useAccess kaydetme anında da); (3) aynı desen sağlayıcı formunda varsa orada da. Önce kırmızı Playwright testi (inceleyicinin probe'u: .worktrees/review-10af-r1-evidence/ ve rapordaki negatif test), sonra düzeltme. Kapılar: tsc/eslint/vitest + 10af e2e; tam takım tek worker.

### K-10af-0008 · 2026-10-29 00:54 · → inceleyici · CEVAP
Paket: 10a-formlar   Cevap: R-10af-0004
Alındı. MINOR-1 merge öncesi düzeltilecek (DUZELT K-10af-0007); r2 yalnız delta + 10af e2e. Review imajlarını ben siliyorum. Evidence dizini r2'ye kadar kalsın. 04a r2 ve 02 r1 sırada.

### K-10af-0009 · 2026-10-29 09:01 · → inceleyici · REVIEW-ISTEK
Paket: 10a-formlar   Cevap: C-10af-0007
r2 delta. Branch feat/10a-forms · SHA 275d06d8224e40a02b0dfc1d2bfbcba0b014c98a (koordinatör doğruladı: 070d8b0 üstünde, 851de1d..275d06d 3 commit, 23 dosya +204/-9, ağaç temiz). Kapsam yalnız delta: MINOR-1 (ModelList proje key'li, iki formda Kaydet WriteGate içinde; senin probe'unla `project-transition` senaryosu tekrar), ek düzeltme `Models.extraBodyHint` ICU tırnaklama (en/tr), yeni testler test_10af_16/17/18 (önce kırmızı kanıtı PR'da). Kapı: 10af e2e + vitest; isci-c tam takım tek worker 76/76 bildirdi. ONAY ise merge ederim.

### K-10af-0010 · 2026-10-29 09:01 · → isci-c · CEVAP
Paket: 10a-formlar   Cevap: C-10af-0007
r2 PR-HAZIR alındı; 275d06d doğrulandı. REVIEW-ISTEK K-10af-0009 inceleyiciye gitti. Review bitene kadar yeni commit yok.

### K-10af-0011 · 2026-10-29 09:31 · → isci-c · CEVAP
Paket: 10a-formlar   Cevap: R-10af-0008
10a-formlar MERGED: r2 ONAY (275d06d, state/reviews/10a-forms-r2.md); main'e `--no-ff` merge 7457e82; main'de lint + compose config + smoke passed. Worktree, branch ve `0.0.0-10af`/review imajları kaldırıldı; `ffcore-10a-nm(-pw)` volume'ları 10b için kalıyor. Kapanışın: HANDOFF yaz (FOLLOWUP-79/80, D1-D4, egress düzeltmesi, e2e komutları, BACKEND_PORT notu), lease RETIRED. C kuyruğunda sıradaki 10b-poc; GOREV taslağını ayrıca yazacağım, yeni oturumda.

### K-10af-0012 · 2026-10-29 09:31 · → inceleyici · CEVAP
Paket: 10a-formlar   Cevap: R-10af-0008
Alındı; 10a-formlar main'de (7457e82). r1/r2 evidence dizinlerini kaldırabilirsin. Kuyrukta 04a r2 ve 02 r1 geliyor.
