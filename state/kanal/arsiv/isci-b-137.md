# Arşiv: isci-b · 137

state/kanal/isci-b.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### B-137-0001 · 2026-11-02 15:50 · → koordinator · DURUM
Paket: fix/04a-gate2-headings   Cevap: -
DURUM: OKUMA-TAMAM (oturum ffcore-isci-b-137-7e3079e2; lease ACTIVE). Bu oturum 28 Ekim'deki tam okumanın (gruplar 1-8, B-01-0001) fork'u; 21d9ba1..d365811 farkı yeniden okundu: CLAUDE.md, PLAN (2d.7, 2.6-2.9), KARARLAR eklemelerinin tamamı, handbook CONTRACTS/RELEASE_AND_ROLLBACK/TERMINOLOGY farkları (FELSEFE, FELSEFE_UYGULAMA, diğer handbook dosyaları değişmemiş). State: WORK_QUEUE fix satırı, BLOCKERS 136-138, K-137-0001, K-06b-0021, B-19-0013. Kod: knowledge/gates.py tamamı, docs/bilgi-tabani.md Kapı 2, plan/04 Kapı 2 satırı, test_04a_text_rules.py, test_19_ingest_raw.py, data/samples/paycore-like 1001/1002.
Not: kullanıcı PAKET=fix/04a-gate2-heading yazdı; GOREV ve WORK_QUEUE adı fix/04a-gate2-headings, onu kullanıyorum.

### B-137-0002 · 2026-11-02 15:50 · → koordinator · ACK
Paket: fix/04a-gate2-headings   Cevap: K-137-0001
GOREV alındı. Anladığım: `#{1,6} ` + metin başlığı kod sayılmaz; `#include`, `#!/bin` gibi `#`+boşluksuz ve kabuk yorumu deseni kod kalır; eşik 0,5 ve diğer kurallar aynı. İlk gözlem: test_19 `convert_without_weights` ile başlıkları ayrı satırda tuttuğu için 1001/1002 orada geçiyor (yalnız 1004 boilerplate); sorun Docling'in paragraf birleştirmesinde. Kırmızı test bu biçimi (başlık + birleşik paragraf, 3/5) birim düzeyinde kurar. Sıradaki: worktree main d365811'den açıldı (.worktrees/fix/04a-gate2-headings), state/pr/04a-gate2-headings.md planı, DURUM: PLANNED. Yığın şimdilik gerekmiyor; entegrasyon kanıtı için gerekirse YIGIN-AÇ (18220/13220).

### B-137-0003 · 2026-11-02 15:53 · → koordinator · DURUM
Paket: fix/04a-gate2-headings   Cevap: K-137-0001
DURUM: PLANNED. Plan: C:\ai_paycore\ffcore\state\pr\04a-gate2-headings.md. Worktree .worktrees/fix/04a-gate2-headings @ d365811, temiz; kod yok.
Özet: tek değişiklik `gates.py:66` `#` dalı → `#(?!#{0,5}\s+\S)` (`#`…`######` + boşluk + metin başlık, kod değil; `#include`, `#!/bin`, `#define`, `#`, 7+ `#` kod kalır; regex host'ta doğrulandı). Eşik 0,5 aynı. Testler `tests/unit/test_137_gate2_headings.py` (6 kriter; önce 1. kırmızı), docs/bilgi-tabani.md Kapı 2 cümlesi. Regresyon: 04a birim + test_19/04a ingest entegrasyon.
Onay istediğim varsayım (planda 1): `# metin` biçimindeki kabuk yorumu satır düzeyinde H1 başlıktan ayırt edilemez; varsayımım "her zaman başlık", kod bloğunu öteki satırlar taşır (test 4 kanıtlar). Fence içi bağlam takibi kapsam dışı (ARCH-07). Aksini istersen durup KARAR-GEREK yazarım.
Gözlem (değişmiyor): `--` dalı `---` yatay çizgisine de uyuyor; ölçülmedi, kalan risk.
Plan onayını bekliyorum; onaydan sonra kırmızı test → düzeltme → kapı (tam tee).

### B-137-0004 · 2026-11-02 16:09 · → koordinator · KARAR-GEREK
Paket: fix/04a-gate2-headings   Cevap: K-137-0003
Kırmızı → düzeltme yapıldı (commit yok): 137 testlerinden 8'i önce doğru nedenle kırmızıydı (`code_heavy`, state/evidence/137-red-20261102.log). Düzeltmeden sonra lint 0; make test iki profilde 873 geçti / **1 kaldı** (state/evidence/137-gate-20261102.log): `test_137_4[python_with_comments]` artık `code_heavy` değil, `no_prose` ile eleniyor.
**Onaylattığım varsayım 1 kısmen yanlış çıktı** ("kod bloğunu öteki satırlar taşır"). Python'da girintili gövde satırları (`return …`, `pass`) zaten kod sayılmıyor. Yorum satırları da düşünce oran düşüyor. Ölçüm (sonra / önce):
- A: yorumlu Python 4/8 kod, stopword 0,036 → `no_prose` ile elenir (önce `code_heavy`): elenme sürüyor, gerekçe değişiyor.
- B: **Türkçe düzyazı yorumlu** Python 3/8, stopword 0,238 → **ok, indekslenir** (önce 6/8 `code_heavy`): gerçek gerileme.
- C: yorumlu kabuk betiği 1/6 → ok (önce 3/6 = 0,5, o da geçiyordu): değişiklik yok.
Seçenekler:
- **A (önerim): fence farkındalığı.** `text_quality` içinde ```` ``` ```` ya da `~~~` arasındaki satırlar desen ne olursa olsun kod sayılır. Fence dışında başlık kuralı geçerli. ~5 satır. `_FENCE_LINE` zaten gates.py'de var. Etki: B, Docling'in kod makrosunu fence'li vermesi durumunda yine `code_heavy` olur. Docling'in Confluence kod makrosunu fence'lediği **doğrulanmadı** (ağırlıksız HTML yolu denenebilir, denemedim). Fence'siz yorumlu kod B gibi geçmeye devam eder. Fence'li ama kod olmayan içerik (log, yapılandırma örneği) kod sayılır, bu zaten amaç.
- B: değişiklik yok, sınır belgelenir. test_137_4'ün Python örneği "elenmeye devam eder (no_prose)" diye yazılır, B vakası kalan riske. Etki: düzyazı yorumlu kod parçaları indekse girer (arama gürültüsü; güvenlik değil). Kapsam en dar.
- C: başlık kuralını vazgeçip yalnız Docling biçimine özel (yalnız belge başı, ilk N satır) uygulamak. Kırılgan, önermiyorum.
Cevabına göre A'da testler + fence vakası eklenir, B'de test ve PR metni düzeltilir; sonra test-int (yığın gerekirse YIGIN-AÇ fix137, 18220/13220) ve PR-HAZIR. O zamana kadar commit yok.

### B-137-0005 · 2026-11-02 17:27 · → koordinator · ACK
Paket: fix/04a-gate2-headings   Cevap: K-137-0004
Karar A alındı ve uygulandı (geç ACK, özür; uzun make test koşusu sırasında yazmadım). Fence farkındalığı `gates._code_lines` (`_FENCE_LINE` yeniden kullanıldı): fence içindeki her satır kod, kapanmayan fence sonrası kod. Testler: 4 (fence'li yorumlu Python ``` ve ~~~ → code_heavy), 7 (fence'li log), 8 (kapanmamış fence fail-safe + kapalı fence karşılaştırması), 9 (fence'siz düzyazı yorumlu kod geçer, bilinen sınır sabitlendi). Kırmızı kanıt: state/evidence/137-red2-20261102.log (4 kırmızı). Kapı (çalışma ağacı, commit yok): lint 0; make test llmaas 878/878, airgap 878/878 (state/evidence/137-gate2-20261102.log).

### B-137-0006 · 2026-11-02 17:27 · → koordinator · YIGIN-AÇ
Paket: fix/04a-gate2-headings   Cevap: K-137-0004
YIGIN-AÇ fix137 kısa (yalnız postgres + redis, 0.0.0-main + worktree kodu, imaj derlemesi yok, temiz volume): `test_19_ingest_raw.py` + `test_04a_ingest.py` + 04a entegrasyon gerilemesi, iki profil. Koşullar: C: 45 GB boş; açık FF yığını 0 (ffmain kapalı). Bitince `down -v` + YIGIN-KAPA.

### B-137-0007 · 2026-11-02 17:44 · → koordinator · KARAR-GEREK
Paket: fix/04a-gate2-headings   Cevap: K-137-0004
**Karar A (fence = kod) entegrasyonda gerçek bir gerileme açtı; durdum.** Commit d358bae2624a2ad9b6c352941b8d222c4465d4d5 (Karar A, birim testler yeşil). Kısa yığın fix137'de `test_19_ingest_raw` iki profilde düştü (78 geçti / 1 kaldı; state/evidence/137-test-int-20261102.log): `indexed 3, skipped 2`, ek bir `gate2:code_heavy` var.
Neden (ölçüm: state/evidence/137-probe-samples-20261102.log): `convert/text_formats.py:44` düz metin dönüştürücüsü **her .txt'yi tek ```` ``` ```` bloğuna sarıyor** (satır düzenini korumak için, PayCore mirası). Karar A ile her düz metin belgesi %100 kod sayılıyor. Örnekler: DEMO-7.txt 7/7, 1003-kontrol-listesi.txt 6/6, PRSIM-1.txt 4/4 → `code_heavy`. Main'de üçü de 0 kod. M3'te PayCore Jira/PRSIM raw'ı .txt olduğu için bu kabul edilemez.
Ek ölçüm (ağırlıksız Docling HTML ve MD yolu, `--network none`): Docling `<pre>` ve fence'li Markdown kodunu **dil etiketsiz** ```` ``` ```` ile veriyor. Dolayısıyla "yalnız dil etiketli fence kod" ayrımı işe yaramaz. Bu kısa denemeyle Docling fence'i doğrulandı (yalnız HTML/MD; gerçek Confluence dışa aktarımı denenmedi).
Seçenekler:
- **A' (önerim): fence içinde main kuralı, dışında başlık kuralı.** Fence içinde `# metin` satırı yine kod sayılır (main davranışı). Öteki satırlar desene göre sayılır; fence çizgisi kod sayılmaz. Etki: düz metin belgeleri tam olarak main gibi davranır (gerileme yok). Fence'li düzyazı yorumlu Python main'deki gibi 6/8 → `code_heavy` (B vakası kapanır). Fence'li log yalnız deseni varsa kod sayılır (K-137-0004 şartı (1)'in "fence'li log kod" maddesi düşer). Kapanmamış fence'te kalan satırlar main kuralıyla sayılır (fail-safe = main). ~3 satır değişiklik.
- B: fence farkındalığını geri al, yalnız başlık kuralı (eski B). Etki: fence'li ve fence'siz düzyazı yorumlu kod geçer, kalan risk.
- C: düz metin dönüştürücüsünün sarmalamasını kaldır. Touch-zone dışı (convert/), tüm düz metin silver'ı değişir, parçalama etkisi ölçülmedi; önermiyorum.
Yığın fix137 açık (postgres + redis, ~0,3 GB); cevap gecikirse kapatırım. Cevabına göre testler güncellenir, birim + entegrasyon iki profil yeniden koşulur, PR-HAZIR.

### B-137-0008 · 2026-11-02 18:02 · → koordinator · ACK
Paket: fix/04a-gate2-headings   Cevap: K-137-0006
Karar A′ alındı ve uygulandı: commit 0eed4c868f0d993d6d5bb62555acc8a894d5b5b7. `_CODE_LINE` main ile birebir aynı. `_HEADING_LINE` + `_is_code_line(fenced)`: fence dışında başlık kod değil, fence içinde main kuralı geçerli; fence çizgisi kod değil; kapanmamış fence'ten sonra fence içi kural. Testler A′'ye göre: 7 fence'li .txt (DEMO-7 biçimi) geçer, 8 kapanmamış fence = main, 4 fence'li yorumlu Python `code_heavy`; test_137 + test_04a_text_rules 52/52. docs cümlesi güncellendi. Tam kapı (lint, make test ×2, test_19 + 04a entegrasyon ×2) şu an koşuyor, tam tee state/evidence/137-gate3-20261102.log. Bitince down -v + YIGIN-KAPA + PR-HAZIR. PR taslağı state/pr/04a-gate2-headings.md.

### B-137-0009 · 2026-11-02 18:05 · → koordinator · YIGIN-KAPA
Paket: fix/04a-gate2-headings   Cevap: K-137-0005
fix137 kapatıldı: `down -v` exit 0, kalan konteyner 0, volume 0. İmaj derlenmedi (0.0.0-main), temizlenecek paket etiketi yok.

### B-137-0010 · 2026-11-02 18:05 · → koordinator · PR-HAZIR
Paket: fix/04a-gate2-headings   Cevap: K-137-0006
DURUM: VERIFIED. PR açıklaması C:\ai_paycore\ffcore\state\pr\04a-gate2-headings.md · Sınıf [A].
Branch fix/04a-gate2-headings · worktree .worktrees/fix/04a-gate2-headings · baz main d365811 · SHA **6c0271846e26d7d2241827348c0b2fe697e73e7f** (3 commit: d358bae A, 0eed4c8 A′, 6c02718 docstring satır boyu). 3 dosya: knowledge/gates.py, tests/unit/test_137_gate2_headings.py (yeni), docs/bilgi-tabani.md; migration yok, state yok.
Kanıt (tam tee state/evidence/137-gate3-20261102.log): 0eed4c8'de make test llmaas 878/878, airgap 878/878; test_19_ingest_raw + test_04a_* entegrasyon iki profil 79 geçti / 11 bayraklı NOT_RUN (main ile aynı; test_19 `indexed 4, skipped 1`, `gate2:boilerplate 1`). İlk lint E501 (test docstring) 6c02718'de düzeldi; son HEAD'de lint 0 + test_137/test_04a_text_rules 52/52. Kırmızı kanıtlar 137-red, 137-red2, A'nın entegrasyon gerilemesi 137-test-int ve 137-probe-samples.
Kalan riskler PR'da: fence dışında düzyazı yorumlu kod geçer (test 9 sabitledi); Docling fence'i yalnız HTML/MD örneğinde ölçüldü (dil etiketsiz), Confluence dışa aktarımı denenmedi; `---` / `--` main davranışı, 19 ağacında 0 satır.
Branch'e başka commit atmıyorum.

### B-137-0011 · 2026-11-02 18:56 · → koordinator · HANDOFF
Paket: fix/04a-gate2-headings   Cevap: K-137-0010
### fix/04a-gate2-headings · ffcore-isci-b-137-7e3079e2 · 2026-11-02 18:56
- Durum: MERGED (main e9ad4b5, 6c02718'den; koordinatör doğruladı). BLOCKERS 137 kapandı.
- Tam sonraki adım: yok. Takip adayı (kayıt koordinatörde): Confluence dışa aktarımında Docling fence biçimi doğrulanmadı (yalnız HTML/MD ölçüldü); `---` / `--` main davranışı; fence dışı düzyazı yorumlu kod test_137_9 ile sabit.
- Değişen dosyalar: backend/ffcore/knowledge/gates.py, backend/tests/unit/test_137_gate2_headings.py, docs/bilgi-tabani.md.
- Koşan testler: lint 0; make test 878/878 iki profil; test_19 + test_04a_* entegrasyon iki profil 79 + 11 bayraklı NOT_RUN (state/evidence/137-*). Kalan: gerçek Docling ingest (make models, kullanıcı).
- Kararlar: K-137-0003 (plan, varsayım 1), K-137-0004 (A), K-137-0006 (A′, son kural).
- Blocker'lar: yok. Yığın fix137 kapalı (B-137-0009).
- Commit edilmemiş durum: yok. Worktree ve branch koordinatörce kaldırılıyor.
- Branch ve son commit: fix/04a-gate2-headings @ 6c0271846e26d7d2241827348c0b2fe697e73e7f → main e9ad4b5.
Lease: RETIRED.
