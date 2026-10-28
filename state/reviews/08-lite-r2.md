# 08-lite · r2 · Bağımsız delta incelemesi

- İstek `K-08lite-0009`; ACK `R-08lite-0004`.
- İncelenen tam SHA: `7a7dc35e156b17f72e567dad3bfbf584f4f7a898`.
- R1 `21812317c05093658b88a8b0c7bfff0dba7ceb52`; baz `591aac3`.
- **DUZELT / merge-ready değil. BLOCKER0, MAJOR1, MINOR0.** R1 dört MAJOR kapandı; yeni önizleme kodunda performans gerilemesi var.
- İnceleyici `ffcore-inceleyici-20261028-0203`; 28 Ekim2026.

## Yeni MAJOR-1 — Önizleme tekrar taraması küçük geçerli girdide event loop'u uzun süre tutuyor

`guardrails/engine.py:_preview` zincirin `seen` listesindeki her bulgu için aynı ham değerin metindeki bütün tekrarlarını yeniden arayıp span ekliyor. Aynı değer n kez bulunmuşsa her önizlemeye n² kopya ekleniyor. Ardından `resolve_overlaps` her kopyayı tutulan span listesinde tarıyor; gereksiz tekrarlar çok daha yüksek maliyet üretiyor. Her olay için bu iş yeniden yapılıyor; yalnız ilk60 karakter gösterilecek olsa bile tüm metin işleniyor.

Bu, r1 temiz alanının yeniden açılması değil: **r2'de eklenen** zincir-sonu `seen` döngüsünün regresyonu. Örnek girdi yalnız `'a.b@example.org ' * n`; özel regex veya yönetici politikası yok, yerleşik monitor politikası kullanıldı. 10.240 karakter, kabul edilen200.000 sınırının yaklaşık%5'i. `_preview` senkron olarak async evaluate içinde çalıştığından uzun işlem event loop'u bloke eder; route'un bu işi threade aktardığı bir yol yok.

Bağımsız ağsız karşılaştırma, aynı 1CPU/512MB sınırlı konteynerde:

| Kaynak | Tekrar /karakter | Süre |
|---|---|---|
| R1 exact engine | 640 /10.240 | **0,345sn**, tamamlandı |
| R2 exact engine | 320 /5.120 | **5,481sn**, tamamlandı |
| R2 exact engine | 640 /10.240 | **12,007sn**, review alarmıyla kesildi; tamamlanmadı |

R1 engine'in Git blob'u `1a310d95280cc5dc7f03939e8beb7af9a7d968ce` karşılaştırma öncesi doğrulandı. Her ölçüm12sn alarmıyla sınırlandı; alarm yalnız bağımsız probe konteynerindeydi, ürün davranışı değil. Bunlar tek koşu regresyon ölçümleri; boşta P95 bütçesi ölçümü diye sunulmuyor. Ön bağımsız örneklemde320/640/1280/2560/5120 karakter için0,006/0,031/0,117/0,756/4,368sn görüldü; büyüme kaynak koduyla uyumlu. Tam200.000 karakter veya OOM deneyi yapılmadı; gerekli değil.

İstenen düzeltme: aynı değer/konumları tekrar tekrar üretmemek; önizleme aralığı ve örtüşmeleri sınırlı maliyetle işlemek, uygun tekilleştirme/ortak hesap kullanmak. **Ham değer gizliliği geri alınmamalı, bulgu atlama veya metin kırpma yapılmamalı.** Aynı girdinin 320/640 tekrarında gerçek engine yolunu ölçen bir regresyon kapısı ve r1 gizlilik negatiflerinin birlikte geçtiği kanıt gerekli. Mevcut quality latency testi yalnız recognizer'ı ölçüyor; bu yeni önizleme maliyetini görmüyor. Event latency_ms de önizleme kurulmadan hesaplandığından bu maliyet kayıtta görünmüyor (kaynak incelemesi).

Tekrar üretim kanıtı için iki yerel yardımcı dosya `.worktrees/review-08lite-r2-evidence/old-engine.py` ve `preview-cost.py` içinde korundu. Bunlar ürün kaynak worktree'sinin dışında, yalnız review kanıtı; çalışan konteyner bırakılmadı.

## R1 bulgularının kapanışı

- **MAJOR-1 kapandı:** preview artık zincir bittikten sonra regex PII + secrets + zincirdeki tüm bulgularla kuruluyor; sonraki custom desenin önceki olaya sızması testi de var. `masked_value` kısa e-postayı/tek haneyi gizliyor. R1 aynı gerçek DB/API probe'unda sentetik parola iki olayda da yok, response events'te yok; `a@example.org` DB matches'te ham değil. İsim değişikliği C4 donmadan koordinatörce kabul edilmiş; güncel OpenAPI testi geçti.
- **MAJOR-2 kapandı:** ham kimlik nokta/tireyi koruyor. R1 aynı a.b/ab girdisi artık ayrı `<<PII_1>>` / `<<PII_2>>`, tam round-trip=true, unresolved boş. Biçimi değişmiş numaraların ayrı token olması K-08lite-0008'de açık kabul.
- **MAJOR-3 kapandı:** sayaç, forward/reverse ve TTL tek Lua EVAL içinde. Yeni sahte gecikmeli istemci testi eski yarım-publish penceresini yakalıyor; gerçek Redis pozitifinin eski kodda da geçebilmesi PR'da dürüst. Bağımsız gerçek Redis'te100 paralel çağrı/20 farklı değer →20 token, bütün anlık lookup'lar doğru, TTL pozitif, başka run'da çözülmüyor. Script içi adımların dışarıdan yarım gözlenememesi kaynakta doğrulandı; r1'in raw hset bariyeri EVAL'in içine yerleştirilmiş gibi sunulmadı.
- **MAJOR-4 kapandı:** yerleşik zincir de `resolve_pii` ile proje satırını çözüyor. R1 aynı custom PERSON girdisi: doğrudan panel1 bulgu, zincir de1 bulgu/redact; önceki0/allow yok. Satır yoksa builtin, proje/read davranışları testlerde korundu.

## Bağımsız doğrulama

10 dosyalık r1→r2 deltası incelendi; eski temiz alanlar yeniden tasarlanmadı. Backend `sha256:048dcfb037d660c3a665bb9e9378b11041e39d755f9e4a334adea9ace8e6db23` içindeki56 Python dosyası exact SHA ile aynı. Tools bağımlılık imajı `sha256:4c179b8636ca79e522e0792b3b1a177d3dd956719fd65bd010f516b2d2ad52c0`; kaynak `/work:ro`, çalışma dizini `/work/backend`, test/probe importları r2 kaynağından.

Proje `review-08lite-r2`, `FFCORE_VERSION=0.0.0-review-08lite`, backend host18028; kendi PG/Redis ve sahte `.env.test`. Yeni derleme/indirme, gerçek secret veya kurum verisi yok.

| Kontrol | Sonuç |
|---|---|
| llmaas lint + unit/contract + integration | **passed**; format116, 184 test12,63sn, 110 entegrasyon52,77sn |
| airgap aynı kapılar | **passed**; format116, 184 test14,90sn, 110 entegrasyon100,86sn |
| R1 aynı olay/e-posta/default probe'ları | **passed**, yukarıdaki kapanışlar |
| Bağımsız gerçek Redis100 çağrı | **passed**,20 token, tam reverse,TTL/run sınırı |
| R1/R2 exact engine maliyet probe'u | **FAILED**, yeni MAJOR1 |
| OpenAPI08/03a bayt sözleşmeleri | **passed**, kapılar içinde |
| Baz `state/` diff /delta diff --check | **boş /passed** |

## Güvenlik turu ve sınırlar

- **Kimlik/ACL:** servis-only ve proje/read/OBO testleri yeniden geçti; kimlik kodu delta yok. Test paneline analyst erişimi olması performansın yalnız admin regex riskine indirgenemeyeceğini de gösteriyor; metin güvenilmeyen girdidir.
- **Secret/PII/log:** r1 sentetik credential ve kısa PII olay sızıntıları kapandı; DB/API negatifleri tekrarlandı. Ham değerler rapor/loga basılmadı. `masked_value` alanı sözleşmede açık. Önizleme gizliliği korunurken yeni maliyet düzeltilmeli.
- **SQL:** yalnız kendi UUID fixture DB'leri; aynı migration döngüsü ve audit negatifleri geçti. Yeni SQL/migration yok.
- **Egress:** kapalı egress409 iki profil matrisinde; dış sağlayıcı isteği yok. Lua yalnız kendi Redis hash'lerini kullandı/temizledi.
- **Kaynak kullanımı:** yeni senkron preview yolu geçerli küçük metinle uzun CPU işi;1CPU/512MB sınırıyla ölçüldü, kurum sunucusunda yük deneyi yapılmadı.

**NOT_RUN:** r2 full stack/LiteLLM/Langfuse smoke (compose/altyapı delta yok, r1 geçti); NER/injection/C17/dış satıcı/kurum bağlantısı;200.000 karakter/OOM ve Redis crash deneyi. Bu sınırlar passed sayılmadı. Redis5.3.1/04a merge uyumu r2'ye dahil değil; mevcut imajda Redis8 bağımlılığı kullanıldı, sonraki rebase kapısı koordinatörde.

## Temizlik

Kendi stack down-v ile temizlendi; exact HEAD7a7dc35e156b17f72e567dad3bfbf584f4f7a898 ve boş git status doğrulandı. Worktree remove exit0, --force yok. Kendi iki evidence dosyası tekrar üretim için korunuyor; ürün kodu değil. İşçi stack/korunan volume'ları silinmedi; main checkout/switch, kaynak edit/commit/push ve dış sistem erişimi yok. ffcore/backend:0.0.0-review-08lite ve ffcore/tools:0.0.0-review-08lite koordinatörce temizlenebilir.
