# Dalga raporu · 19 Kasım 2026 (dalga 6b: PoC sonrası ikinci yarı, kapanış) · TASLAK

Yazan: koordinatör (lease ffcore-koordinator-20261102). Şablon: docs/takim/ajanlarla-gelistirme.md 9.3. Önceki rapor: state/dalga/dalga-17kasim-rapor.md (onaylı 17 Kasım; bölüm 9 bu dalganın planı). Onay: kullanıcı.

## 1. Dalga, paketler, main, kapı logları

Dalga 6b planı (17 Kasım, onaylı): 10c-2 ve 05b önce; sonra 04b (isci-b) ve 10c-3 (isci-c) paralel; inceleyici tek oturum. Hepsi main'de; kapı logları `state/evidence/`.

| Paket | Merge (19 Kas aksi yazılmadıkça) | Main kapısı | Log |
|---|---|---|---|
| 05b OpenAPI → uzak MCP yayınlama (`/mcp/{key}/`, `mcp_servers`, guardrail/denied, origin eşitliği) | 2e75ba2 (18 Kas 16:36) | kaynaktan yeşil 1903×2, test-int 1004; imaj build ertesi gün doğrulandı (ENV-196 kapalı) | gate-05b-20261118.log |
| 10c-2 yönetişim konsolu (kullanım/maliyet, API anahtarları, kotalar, uyarılar, retention, salt-okunur), sınav öğesi ucu, tipli `EvalSummary` | b93cd96 (12:54) | yeşil 1918×2, test-int 1010, Vitest; e2e r1 kanıtıyla atlandı | gate-10c2-20261119.log |
| 10c-3 MCP Sunucuları ekranı + İzleme, skaler özet düzeltmesi | 0a92084 (17:01) | yeşil 1925×2, test-int 1012, Vitest 279 | gate-10c3-20261119.log |
| 04b-1 `migrate-vectors`, `chunks.sparse`, ingest raporu, belge ACL düzenleme (admin), preset'li yeniden dönüştürme, yükleme yolunda ACL yetkisi | ef2ee83 (19:17) | yeşil 1937×2, test-int 1056, Vitest 279 | gate-04b1-20261119.log |
| 04b-2 TR normalizer katman A + 409, video bayrağı + `video` preset'i, eşik tablosu + `query-stats`, `knowledge[].filter.scope`, `/readyz` `ingest_queue` + `ollama_runtime_context`, Markdown `text_formats` | d096bb3 (22:41) | yeşil 1959×2, test-int 1076, Vitest 279 | gate-04b2-20261119.log |

Test sayısı dalga boyunca 1903 → 1959 (birim+sözleşme, profil başına), 1004 → 1076 (entegrasyon). İnceleme turları: 05b 3, 10c-2 2, 10c-3 2, 04b-1 3, 04b-2 2; toplam B0; MAJOR yalnız 04b-1 r2'de (iki yetki atlatması, r3'te kapandı). Push: `origin` ve `paycore` 10f92e9'da (17 Kas); beş merge ve state commit'leri yerel, kullanıcı talimatı bekliyor.

## 2. Bu dalgada alınan kararlar (KARARLAR; tek cümle)

- 18 Kasım · 05b r2 kararları (yüzde kodlu nokta/bölü anahtarı 422; r3 kısa dilim); 05b main kapısı kaynaktan yeşil, imaj build ENV-196 istisnası (ertesi gün kapandı).
- 18-19 Kasım · 10c-2 r1/r2 kararları (kısmi sınav özeti 500 → null + log; skaler özet FOLLOWUP-197 → 10c-3 ilk commit).
- 19 Kasım · Dalga 6b ikinci yarı: 04b (isci-b) + 10c-3 (isci-c) paralel; `rewrite` (DECISION-2) ve Türkçe embedding karşılaştırması 04b dışı.
- 19 Kasım · 10c-3 plan (mutasyon admin, e2e upstream litellm, izleme fikstür+gerçek) ve r1 kararları (durum kodu belgesi; FOLLOWUP-199/200).
- 19 Kasım · 04b plan kararları: FFCore'da DuckDB yok (DOC-17), D1 = `migrate-vectors`; iki PR; S1-S7 A; DEBT-10 kanıtla kapandı.
- 19 Kasım · 04b-1 r1: belge ACL değişikliği yalnız admin; r2: yükleme yolunda admin dışı ACL farkı 403, gizli aynı adlı kayıt 409 `document_name_taken`; r3 eki: admin/süperadmin ad kontrolünden muaf (FOLLOWUP-202).
- 19 Kasım · 04b-2 plan: eşik tablosu ölçülmemiş değer uydurmaz + `query-stats` salt bilgi; `.md` Docling'e gitmez; `/readyz` Ollama `/api/ps`; şemalar aynı commit; S7 gerçek imajsız kodlandı (ENV-204); compose anchor'a iki ayar (fail-loud).
- 19 Kasım · 04b-2 r1: `:latest` eşlemesi, `FULL=1` ipucu, `/api/ps` biçim hatası `ollama_ps_unexpected`, scope 200; front matter FOLLOWUP-206.

## 3. Tersine dönen kararlar

- Plan/04 ve PLAN 7 "DuckDB → Postgres belge deposu göçü (DEBT-1)": FFCore'da DuckDB hiç olmadı; D1 `migrate-vectors` oldu (DRIFT-198 açık, metin düzeltmesi bekliyor).
- 17 Kasım planı 05b'yi isci-a'ya vermişti; isci-a HANDOFF'u gelmediği için isci-b şeridinde yapıldı (koordinatör isci-a lease'ini RETIRED yazdı).

## 4. İnsana kalan açık konular

- **Push:** `FFCORE_PUSH_OK=1` ile origin ve paycore aynası (beş merge: 2e75ba2, b93cd96, 0a92084, ef2ee83, d096bb3 + state).
- **Hook kipi:** `FFCORE_GUARD_MODE` warn → block (önerim A: block; 30 uyarının hepsi bilinen yanlış pozitif sınıfı, gerçek ihlal yok; FOLLOWUP-207 kural düzeltmesiyle birlikte).
- **Oturum arşivleri:** isci-a-hook, isci-b-hook2, isci-b-05b, isci-c-sse, isci-c-10c1, isci-c-10c2, isci-c-10c3, inceleyici-09-2, belge-ajanli-surec; 04b HANDOFF sonrası isci-b-04b.
- **Worktree ve imaj temizliği:** `.worktrees/` altında fix/ajan-hooklari, fix/ajan-hooklari-2, fix/10b-sse-bekci, feat/05b-openapi-mcp, feat/10c-2-governance-ui, feat/10c-3-mcp-ui, feat/04b-knowledge-ext, feat/04b-2-knowledge-ext; imaj etiketleri 0.0.0-05b/10c2/10c3/04b.
- **ENV-204:** `ollama/ollama:0.12.6` imajı çekilince `make up` (profil ollama) + `GET /readyz` → `ollama_runtime_context` çıktısı.
- **Sunucu:** `.env` `FFCORE_VERSION=0.1.0-m3`; ENV-117 model volume bağlama (12 kapsamı).
- **DECISION-1/2/3** açık (alan adı; `rewrite`/judge; NER eşiği), bu dalgada değişmedi.

## 5. Açık kayıt sayıları ve en riskli üçü

BLOCKERS.md 46,9 KB (>30 KB; DRIFT'lerin arşive taşınması önerilir). Açık: FOLLOWUP 66, DRIFT 36, ENV 7, DECISION 3, DEBT 0. Bu dalgada kapanan: FOLLOWUP 157, 133, 195, 197, 87, 145, 31, 89, 86 + 10c-2 ile 6; DEBT-10; ENV-196. Açılan: FOLLOWUP 199-203, 205-207; ENV-204.

En riskli üçü:
1. **FOLLOWUP-202** (04a): `acl_users` ile kullanıcıya özel belgede proje admin'i GET/PATCH/DELETE 404 alıyor; admin ACL'in tek yetkilisiyken belgeyi yönetemiyor (yükleme yolunda muafiyet var, yönetim uçlarında yok).
2. **FOLLOWUP-194** (01/03c): `ALLOWED_INTERNAL_HOSTS` kalan yarısı (egress sınırı).
3. **FOLLOWUP-203** (02/04a): bir ACL reddi iki `denied` audit satırı (audit sayımı yanıltır).

## 6. Hook kayıtları (17 Kas 09:00 - 19 Kas 23:12; 30 satır, hepsi warn)

KAPI 25 (komut metninde `pytest`/`make test` sözcükleri; log tail'leri ve kanal betikleri), PROSES-175 2 (inceleyici `up --build --pull never`; kural eski, FOLLOWUP-207), YIGIN 1 (işçinin kendi imaj etiketi), TEK-YAZAR 1 (işçinin kendi PR notu), ENV 1 (compose anchor düzenlemesi, onaylı). Gerçek ihlal yok; `block` geçişi bu sınıflar için kuralda düzeltme ister (207), aksi hâlde işçi akışını keser.

## 7. Sıradaki dalga için seçenekler (karar kullanıcıda; önerim A)

- **A (önerim): 12 + FOLLOWUP triage dilimi.** 12 kurulum rehberi `llmaas` ana + egress proxy'ye daraltılmış kapsam (17 Kas raporu); PayCore sunucu kurulumu için gerekli ilk şey. Paralel şeritte küçük backend dilimi: FOLLOWUP-202/203/194/201 + DRIFT-198 metni (isci-b devam, aynı lease). Etki: üretime en yakın değer; 11/14 beklemez çünkü DECISION-193 A ile 11 kendi ekranı ama 12 olmadan sunucuda koşmaz.
- **B: 11 son kullanıcı chat arayüzü (DECISION-193 A) önce.** Etki: kullanıcıya görünen özellik; ama kurulum olmadan yalnız geliştirme makinesinde; 12 bir dalga kayar.
- **C: 14 kullanıcı hafızası.** Etki: 11'e bağımlı (brief); 11 yokken yalnız backend yarısı yapılabilir, ekran bekler; önerilmez.

Her seçenekte: inceleyici tek oturum sürer; hook block geçişi ve FOLLOWUP-207 ilk küçük PR.

## Onay

Kullanıcı bu raporu okuyup onaylar ya da bir maddeyi geri çevirir; koordinatör onayı WORK_QUEUE "Kapılar" tablosuna tarih ve rapor yoluyla yazar. Onayla birlikte seçilen dalganın GOREV'leri yazılır.
