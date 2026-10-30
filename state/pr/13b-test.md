# 13b test tarafı: PLANNED hazırlığı (taslak, GOREV bekleniyor)

Kaynak: K-13b-0000 (GOREV-TASLAK), K-SEN-0055. Branch feat/13b-e2e-eval (isci-a ile tek worktree, iki alt-claim). Test alt-claim'i: `tests/e2e/negative/`, `data/samples` tamamlama (projects.json 6 kullanıcı), F-tablosu çıktısı. Sınıf [A] · `FFCORE_VERSION=0.0.0-13b` · portlar 18050/13050.

## Bulunanlar (main, okuma)

- `data/samples/projects/projects.json` (gen/projects.py): 2 proje × 3 üye = **6 kullanıcı zaten var** (`<proje>-<rol>-<erişim>@example.test`; admin/edit, admin/read, analyst/edit = brief 13 A3 kalıbı). Eksik: `full_name` alanı (seed bugün e-postayı ad olarak kullanıyor) ve parolanın `E2E_PASSWORD`'den geldiğinin belgede yazılması.
- `tests/e2e/scenarios/`: seed.py, e2e.env, F1-F13 testleri (18). Test adları `test_18_f<N>_<n>_<slug>` → F satırına eşlenebilir.
- `.gitignore`'da `eval/results/` yok (isci-a'nın `make eval` alt-claim'i ekler; ben dokunmam).
- Brief 13 madde 6'nın olumsuz adımları: belgede olmayan soru "yok" (gerçek model), PII maskesi (F4'te var), audit'te adımlar (henüz test yok).

## Dilimler (her biri önce kırmızı)

1. **projects.json 6 kullanıcı tamamlama**: `gen/projects.py` her üyeye `full_name` (rol biçimli, kişi adı değil: "Proje A yönetici (düzenleme)"), projects.json yeniden üretilir; `test_18_f10_*` + 13a/18 örnek veri testleri (`full_name` var, kişi adı tanıyıcısıyla PERSON bulgusu yok, e-posta kalıbı). Seed `member["full_name"]`'i kullanır (isci-a'nın seed'iyle koordineli; seed bugün `get("full_name", email)` okuyor, değişiklik gerekmeyebilir).
2. **`tests/e2e/negative/`**: PoC senaryolarının (F1-F4, F9) ve güvenlik sınırlarının olumsuz yolları, her biri kodlu ret ile; fake-llm ile koşabilen ve henüz başka testte olmayanlar:
   - kimlik: oturumsuz istek 401; yabancı `Origin` 403 (C6); başka projenin üyesi (FOLLOWUP-103 düzelince 404; şimdilik bilinen kırmızı, F10'da var, tekrar yazılmaz);
   - erişim: `read` üye her mutasyon ucunda 403 `read_only_access` (KB yükleme, agent yayın, araç çağrısı, onay, geri bildirim) tek parametreli test;
   - koşu: yayınlanmamış agent 404 `agent_not_published`; bilinmeyen değişken 422; bitmiş koşuya resume/feedback 409;
   - araç: SSRF uç kayıt reddi (iç olmayan host + forward_user 400; özel IP 400 egress_*); onaysız `needs_approval` eylemi masaya ulaşmaz (F2'de var, tekrar yazılmaz);
   - koruma: secrets enforce'ta API anahtarı içeren mesaj → run failed `guardrail_block`, sağlayıcıya istek gitmez; metin sınırı 200.000 → 422;
   - onay: süresi dolan onay (TTL kısa ayarlı test projesi ya da 07'nin `approval_expired` olayı) koşuyu kapatır;
   - audit: brief 13 madde 6 "audit'te bu adımlar görünür": seed + bir koşu + bir onay sonrası audit kayıtlarında beklenen eylem adları.
   Her test `test_13b_neg_<alan>_<n>`; kodlar kaynaktan doğrulanarak yazılır (tahmin yok).
3. **F-tablosu çıktısı**: `tests/e2e/` için pytest eklentisi (conftest kancası `pytest_terminal_summary` + `-p` ile): test adından F satırı (`test_18_f<N>` → F<N>, `test_13b_neg_*` → "Olumsuz"), sonuç (geçti / kaldı / NOT_RUN + skip gerekçesi), bilinen bulgular (FOLLOWUP-103/105/108…) tek bir eşleme dosyasından (`tests/e2e/known_findings.json`: test → FOLLOWUP, gerekçe) "kaldı (bilinen: FOLLOWUP-…)" olarak. Çıktı Markdown: stdout + `--f-table <yol>` (varsayılan `eval/results/e2e-<tarih>.md`, gitignore isci-a'da). Birim testi: sahte sonuç listesinden tablo (yığınsız). plan/18 "Durum" sütunu bu tablodan üretilebilir (koordinatör).

## Açık sorular (GOREV'de netleşsin)

- S1: `full_name` biçimi rol tabanlı mı ("Proje A yönetici (düzenleme)") yoksa e-postanın kendisi mi? Öneri: rol tabanlı, kişi adı değil (DECISION-24).
- S2: F-tablosu eklentisi `tests/e2e/conftest.py` (test alt-claim) mi, `make e2e` betiği (isci-a) mi? Öneri: eklenti test tarafında, `make e2e` onu `-p` ile çağırır; tablo biçimi tek yerde.
- S3: TTL testi için kısa `APPROVAL_TTL_MIN` gerekiyorsa e2e.env'e ek mi (ayrı yığın yapılandırması) yoksa NOT_RUN mı? Öneri: e2e.env'e değil, testte 07'nin süpürücüsünü tetikleyen bir yol yoksa NOT_RUN gerekçeli.
