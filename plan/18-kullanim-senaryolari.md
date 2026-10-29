# 18. Kullanım senaryoları: kabul kanıtı haritası [FFCore Platform]

**Kaynak:** kullanıcı listesi, 29 Ekim 2026 (F1-F9). **Sahip:** koordinatör (harita ve takip), test işçisi (kanıt). **Bağımlılık:** her satırda. **Evre:** PoC senaryoları M3 kapısına girer; PoC sonrası senaryolar ilgili paketin kabul kriterine eklenir.

## Amaç

Her kullanım senaryosunun hangi paketlerle mümkün olduğunu, hangi test düzeyinde ve hangi veriyle kanıtlanacağını, kimin yazacağını ve hangi aşamada koşulacağını tek yerde tutmak. Senaryo kanıtı paket kabulünün yerine geçmez; paketlerin üstünde uçtan uca kabuldür (13b `make e2e` ve `make eval`).

## Kurallar

- Kanıt yalnızca sentetik veriyle (13a kuralları; gerçek belge, bilet, e-posta depoya girmez).
- Her senaryo için en az bir olumsuz test (sınır ihlali kodlu ret ile görünür, sessiz değil).
- Dış sisteme gerçek bağlantı yok: bilet, e-posta, kanal gibi dış uçlar `data/samples/` altında sahte MCP ya da OpenAPI sunucusuyla temsil edilir.
- Koşulamayan ölçüt `NOT_RUN` ve gerekçeli; "geçti" sayılmaz.
- Test adları `test_18_<senaryo>_<n>_<slug>`; sınav setleri `data/samples/eval/`.

## Harita

| # | Senaryo | Gerekli paketler | Kanıt | Veri | Yazan | Aşama | Durum |
|---|---|---|---|---|---|---|---|
| F1 | Kaynaklı doküman asistanı | 04a, 02, 06a, 13b (`make eval`) | `make eval`: `sozlesme-33.json` (DRIFT-28) belge soruları ≥ %80 kaynak doğru (cpu ≥ 16/20), her cevapta `sources` olayı dolu, atıfsız cevap yok (olumsuz test: kaynaksız soruda `outcome_label=declined`) | 13a sözleşmeler + `sozlesme-33.json` | test (13b) | 06a merge sonrası | bekliyor |
| F2 | Talep triyajı ve onaylı taslak yanıt | 05a, 06a, 07, 08-lite | e2e: sahte bilet kaynağı (örnek MCP aracı), triyaj sınıfı isabeti ≥ %80 (20 sentetik bilet), taslak yanıt `needs_approval` aracıyla; onaysız hiçbir "gönder" çağrısı sahte uca ulaşmaz (olumsuz), PII'li bilet metni maskelenmiş geçer | `data/samples/tickets/` (test işçisi yazar: 20 sentetik bilet + beklenen sınıf), sahte `ticket-desk` MCP aracı | test (veri + e2e), B (sahte araç, 13b touch-zone) | 07 merge sonrası | bekliyor |
| F3 | Doğal dil veri sorgusu, salt okunur | 05a, 06a, 13a | `make eval`: `sql-20.json` 20 soru ≥ %80 doğru sonuç; yazma yasağı: `DELETE/UPDATE/INSERT/DROP` ve CTE/UNION/yorum ile gizlenmiş yazma 400, DB'de satır sayısı değişmez (olumsuz, gerçek DB) | 13a demo DB + `sql-20.json` (13a'daki 5 + 15 yeni; test işçisi yazar, beklenen sonuçlar seed'den) | test | veri hazırlığı şimdi; koşu 06a merge sonrası | bekliyor |
| F4 | Yönetilen LLM geçidi | 01, 02, 08-lite, 06a (maske bağlama), 03c (kota) | e2e: dış sağlayıcıya giden gövdede sentetik PII 0 (sahte sağlayıcı yakalama ya da LiteLLM erişim logu), model kataloğu ve iz zinciri (run → LiteLLM call id → Langfuse); kota aşımı 429 → 03c'ye kadar `NOT_RUN` | `data/samples/pii/` | test | PII kısmı 06a sonrası; kota 03c sonrası | bekliyor |
| F5 | Kalite izleme ve regresyon sınavı | 09 | 09 kabul kriterleri; sürüm değişiminde otomatik sınav ve düşüş uyarısı | 13a sınav seti | 09 işçisi | PoC sonrası | planlı |
| F6 | Uzun belge özeti ve karşılaştırma | 04b | 04b kabul: maddeye atıf, iki sürüm farkı | sentetik şartname çiftleri (üretilecek) | 04b işçisi | PoC sonrası | planlı |
| F7 | Ekip ve kişisel hafıza | 14, 08 | 14 kabul: PII hafızaya girmez (`data/samples/memory/`) | 13a hafıza seti | 14 işçisi | PoC sonrası | planlı |
| F8 | Kanal asistanı | 15, 17 | 15 kabul: kanalda kimlik eşleme ve ACL korunur | sentetik kimlik eşlemesi | 15 işçisi | PoC sonrası | planlı |
| F9 | Uzman değerlendirme kuyruğu (PoC-lite) | 06a (`POST /runs/{id}/feedback`, additive), 02 (Langfuse score), 10b-poc-2 (Koşular ekranı: oy + not, "bekleyenler"), 09 (dataset otomasyonu, PoC sonrası) | e2e: koşu detayında "doğru / kısmen / yanlış" + not → `messages.feedback` ve Langfuse `score`; "bekleyenler" görünümü yalnız değerlendirilmemiş koşuları listeler; değerlendirmeyi yalnız proje üyesi (`write`) verir (olumsuz: `read` 403); düzeltilmiş kayıtların dataset'e girmesi 09'da `NOT_RUN` | 13a sınav seti koşuları | A (06a uç), C (10b-poc-2 ekran), test (e2e) | 06a + 10b-poc-2 sonrası | bekliyor |

## Aşamalar

1. **Şimdi (05a incelemede):** test işçisi veri hazırlığı: `sql-20.json` (F3), `data/samples/tickets/` 20 sentetik bilet + beklenen sınıf (F2), F2 için sahte `ticket-desk` MCP aracı tasarımı (05a `services/mcp-*` deseni, 13b touch-zone), F4 için sahte sağlayıcı yakalama planı (01 `fake-llm` genişletme ya da LiteLLM erişim logu). Her set için üretim scripti ve doğrulama testi.
2. **06a merge sonrası:** F1 `make eval`, F3 koşu, F4 PII kısmı, F9 uç testi.
3. **07 merge sonrası:** F2 uçtan uca.
4. **10b-poc-2 merge sonrası:** F9 ekran e2e'si; 13b `make e2e` tam tablo.
5. **PoC sonrası:** F4 kota (03c), F5 (09), F6 (04b), F7 (14), F8 (15/17), F9 dataset otomasyonu (09).

## Sonuç beklenenin altındaysa

1. **Eşik değiştirilmez, test gevşetilmez.** Kırmızı sonuç olduğu gibi raporlanır: ölçülen sayı, eşik, koşu komutu, örnek başarısız kalemler (sentetik veri olduğu için tamamı yazılabilir).
2. **Teşhis önce.** Test işçisi başarısız kalemleri aşamaya göre ayırır (09'un aşama teşhisi deseni): arama mı bulamadı (`sources` boş/yanlış), model mi yanlış cevapladı (kaynak doğru), araç mı yanlış çalıştı (SQL hatalı/ret), koruma mı engelledi, veri mi hatalı (beklenen sonuç yanlış). Her kalem bir aşamaya düşer; "bilinmiyor" kalemi NOT_RUN gibi gerekçeli yazılır.
3. **Sahibine düzeltme.** Koordinatör aşamaya göre DUZELT açar: arama/parçalama → 04a sahibi (A/04b), model davranışı ve prompt → 06a sahibi (prompt değişikliği Langfuse'ta sürümlü, 02), araç → 05a sahibi (B), koruma → 08, veri/beklenen sonuç → test. Düzeltme önce kırmızı testle, sonra aynı set yeniden koşulur; sonuç tabloya yeni satır olarak girer (eski silinmez).
4. **Ürün dışı neden.** Donanım (CPU süreleri) ya da model yeteneği (Qwen tool-calling) kaynaklıysa KARARLAR'a ölçümle yazılır ve kullanıcıya seçenek sunulur: GPU/llmaas ile tekrar (NOT_RUN sütunu), model değişikliği (01 kataloğu), kapsam daraltma. Koordinatör kendi başına kabul etmez; eşik kararı kullanıcınındır.
5. **M3 kapısı.** PoC senaryolarından biri eşiğin altındayken M3 "kapandı" denmez; kullanıcıya açık kırmızı listesiyle gidilir.

## Teslimatlar

- Bu dosyanın "Durum" sütunu koordinatörce güncellenir; kanıt PR'larda (13b ve ilgili paket).
- `data/samples/eval/sql-20.json`, `data/samples/tickets/`, sahte `ticket-desk` aracı, `tests/e2e/scenarios/test_18_*.py`.
- `docs/demo.md` (13b) her PoC senaryosunu bir sunum adımıyla gösterir.

## Kapsam dışı

Gerçek bilet/e-posta/kanal sistemine bağlantı; gerçek kurum belgesi; PoC sonrası senaryoların kanıtı (ilgili paketlerde).
