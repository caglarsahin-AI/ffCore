# Kanal: isci-c

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-c-10c2
- Aktif paket: 10c-2 (governance ekranları + FOLLOWUP-185, FOLLOWUP-192)
- Durum: ACTIVE
- Son okunan: koordinator K-10C2-0002; son yazılan C-10C2-0005 (YIGIN-AC)
- Önceki lease: ffcore-isci-c-sse RETIRED (fix/10b-sse-bekci MERGED 4216718; son C-SSE-0011 RETIRED); ondan önce ffcore-isci-c-10c1 RETIRED (10c-1 MERGED; son C-10C1-0015 RETIRED); ondan önce ffcore-isci-c-10bp2 RETIRED (10b-poc-2 MERGED b43770d; son C-10bp2-0019 HANDOFF)

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/isci-c-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 97 mesaj); ID ile atıf orada bulunur.

### C-10C2-0001 · 2026-11-17 13:04 · → koordinator · ACK
Paket: 10c-2 · Cevap: K-10C2-0001
Lease ffcore-isci-c-10c2 ACTIVE (önceki ffcore-isci-c-sse RETIRED C-SSE-0011). Dal feat/10c-2-governance-ui (baz main) açılıyor; okuma ve keşiften sonra PLANNED gelecek, PLAN-ONAY öncesi kod yok.

### C-10C2-0002 · 2026-11-17 13:12 · → koordinator · DURUM
Paket: 10c-2 · Cevap: K-10C2-0001 · Durum: PLANNED
Plan, dosya listesi, kabul→test tablosu ve felsefe kontrolü: `state/pr/10c-2.md` "Plan". Dal feat/10c-2-governance-ui (baz 10f92e9, main; e56bcfa sonrası yalnız state). Dilim sırası: D1 tipler+SPECS (03c, 06b) → D9 koşu sayfası (192) → D8 185 backend+tablo → D3 anahtarlar → D4 kotalar → D5 uyarılar+bildirim+rozet → D6 retention → D2 Genel Bakış+Kullanım → D7 read taraması, iki tema, axe. Rotalar: /overview, /usage, /api-keys, /quotas, /alerts (yeni menü maddesi, İşletme), /retention.
**185 taslağı:** `GET /projects/{pid}/eval-runs/{id}/items?status=all|failed|passed|not_run&limit=50(≤200)&offset=0` → `EvalRunItemList{data, total, limit, offset}`; `EvalRunItem{item_id, style, scored, passed|null, mean|null, outcome|null, note, repeats_not_run, attempts, run_ids[], scores[{name, value|null, passed|null, comment, status}]}`; sıra: başarısız, koşulmadı, geçti, sonra item_id (`combine` ile, compare'in okuduğu biçim; puanlanmamış madde `scored:false`). `EvalSummary` = `summarize()`'in 16 anahtarı tipli; `EvalRunOut.summary: EvalSummary|null`; `summarize()` çıktısının şemaya uyduğunu birim testi kanıtlar.
**Sorular (hepsinde önerim A):**
S1 Retention menüsü: backend okuma dahil yalnız süperadmin. A: `superadmin:true` (menü admin+süperadmin, diğerine "yetkiniz yok") — B: admin'e açık, 403'ü ekranda göster (her admin hata sayfası görür) — C: backend'i admin'e aç (185 dışı backend, kapsam dışı).
S2 API Anahtarları: R10.5 admin; backend analyst'e kendi anahtarını verir. A: menü admin (R10.5 değişmez; admin `all=true` ile hepsini görür, `impersonate` seçimi yalnız admin) — B: analyst+ kendi anahtarları (rol matrisi değişir, kullanıcı kararı) — C: developer+.
S3 Uyarılar: `NAV_GROUPS`'ta madde yok. A: İşletme'ye `alerts` (developer görür ve ack eder (backend analyst+write), kural ve bildirim ayarı admin, rozet developer+) — B: ack de yalnız admin (backend'den dar, ekran kuralı) — C: analyst'e de aç.
S4 Tenant kapsamı (service_down, disk_memory kuralları; tenant SMTP): A: Uyarılar ekranında süperadmine "Proje / Kurulum" anahtarı, aynı bileşenler — B: yalnız proje, tenant FOLLOWUP.
S5 Genel Bakış koşu sayısı: sayaç ucu yok. A: kullanım toplamları (istek/token/maliyet), bekleyen onay ve açık uyarı sayaçları + son 10 koşu listesi (sayı değil) — B: runs listesinden say (limitle kırpılmış sayı: fail-loud ihlali) — C: runs/count ucu (yeni backend, kapsam dışı).
S6 Kabul 2 tetikleme: A: gerçek kullanım (warn kotası rpd=1 + quota_warn kuralı + anahtarla iki facade çağrısı, FAKE_LLM) — B: e2e için internal test kancası (yeni backend yüzeyi). A tutmazsa KARAR-GEREK.
S7 Onay diyaloğu: `components/ui`'de dialog yok, dış ağ yok. A: `@base-ui/react` AlertDialog üstüne elle `ui/alert-dialog.tsx` (yeni bağımlılık yok, shadcn base-ui kalıbı) — B: mevcut `sheet` ile onay paneli.
S8 `summary` tipi: A: 09.yaml'da `EvalSummary` ref (tel biçimi aynı, additive sayıyorum; eski geliştirme satırları şemaya uymazsa 500 riski yalnız dev DB) — B: `summary` serbest kalır, `EvalSummary` yalnız ayrı bileşen olarak eklenir (önyüz zod okuyucusu sürer).

### C-10C2-0003 · 2026-11-17 13:30 · → koordinator · YIGIN-AC
Paket: 10c-2 · Cevap: K-10C2-0002 · Yigin: ffcore-10c2
D8 (FOLLOWUP-185) backend kırmızı/yeşil testleri: tools (`ffcore/tools:0.0.0-10c2` = main imajının etiketi; bağımlılık değişmedi) + test-int için postgres/redis; `--env-file .env.test`, `--pull never`, portlar 18420/13420. Önyüz lint/Vitest ayrı: `docker run --rm --network none node:20.19.5-alpine` + mevcut `ffcore-10a-nm` volume'u (compose yığını değil, yeni volume açmaz).

### C-10C2-0004 · 2026-11-17 13:52 · → koordinator · YIGIN-KAPA
Paket: 10c-2 · Cevap: C-10C2-0003 · Yigin: ffcore-10c2
`down -v`: konteyner 0, volume 0. D1 (03c/06b tipleri + SPECS), D9 (FOLLOWUP-192, Vitest 5/5), D8 (FOLLOWUP-185: uç + EvalSummary + madde tablosu; backend birim 12 + hedefli test-int 27 yeşil, Vitest 220/220) commit'li. Sıradaki D3-D6; e2e için yığın yeniden açılacak.

### C-10C2-0005 · 2026-11-17 14:22 · → koordinator · YIGIN-AC
Paket: 10c-2 · Cevap: K-10C2-0002 · Yigin: ffcore-10c2
e2e + backend kapısı: `--profile test` yığını (`FFCORE_VERSION=0.0.0-10c2`, 18420/13420, `--env-file .env.test`, `up -d --wait --build --pull never backend worker`; backend imajı daldan derlenir, D8 backend eki için), seed-prompts, create-superadmin, e2e (node_modules `ffcore-10a-nm` kopyası, `npm ci` yok, `--workers=1`). Açık FF yığınları: ffcore-05b + bu = 2.
