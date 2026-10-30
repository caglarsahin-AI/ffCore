# 13b test tarafı

**Paket:** 13b (test alt-claim'i) · **Sınıf:** [A] · **Branch:** feat/13b-test @ fa437b12dde76776ad5d4f2c628f35ef88df4a88 (main caa2dfd üstünde, 4 commit) · GOREV K-13b-0001 · Durum: PR-HAZIR

## Sonuç (yığın ffcore-13bt, 18020/13020, `--profile test` + `e2e.env`, seed + `pytest tests/e2e --f-table`)

Seed 0. `pytest tests/e2e`: **49 passed, 2 failed (bilinen: FOLLOWUP-103, FOLLOWUP-108), 25 NOT_RUN**. Negatif testlerin 12'si geçti; TTL NOT_RUN (FOLLOWUP-111). `ruff check/format tests/e2e` temiz.

F tablosu (üretilen dosya, `eval/results/e2e-13bt.md`; dizin depoya girmez):

| Use case | Status | Passed | Failed | NOT_RUN | Failing tests | NOT_RUN reasons |
|---|---|---|---|---|---|---|
| F1 | passed | 2 | 0 | 2 |  | NOT_RUN: gerçek model gerekir (PayCore S1 / llmaas); fake-llm 'hello' der (declined = the model's unknown_reply); NOT_RUN: gerçek model gerekir (PayCore S1 / llmaas); fake-llm 'hello' der (make eval sozlesme-33, 13b) |
| F2 | passed | 5 | 0 | 3 |  | NOT_RUN: gerçek model gerekir; outcome_label=declined the model's own reply after the rejection (fake-llm answers 'hello …', DECLINE_PATTERN does not match); NOT_RUN: triage class accuracy >= 80 % on tickets/tickets-20.jsonl (labels.json); gerçek model ve triyaj agent'ı gerekir; NOT_RUN: PII tickets reach the model masked (fake-llm /_requests); gerçek model ve triyaj agent'ı gerekir |
| F3 | passed | 2 | 0 | 1 |  | NOT_RUN: gerçek model gerekir (PayCore S1 / llmaas); fake-llm 'hello' der (sql-20 ≥ 80 % via make eval, 13b) |
| F4 | passed | 4 | 0 | 2 |  | NOT_RUN: quotas are package 03c (PoC sonrası); NOT_RUN: gerçek model gerekir (the model must call a tool with the value) |
| F9 | passed | 2 | 0 | 1 |  | NOT_RUN: corrected answers into a dataset is package 09 (PoC sonrası) |
| F10 | failed (known: FOLLOWUP-103, FOLLOWUP-108) | 2 | 2 | 0 | test_18_f10_4_direct_ids_are_404 (FOLLOWUP-103: a non-member gets 403 insufficient_role instead of 404 on 12 endpoints); test_18_f10_7_deleted_source_keeps_reference_without_content (FOLLOWUP-108: the sources breadcrumb keeps a deleted document's heading text) |  |
| F11 | passed | 5 | 0 | 7 |  | NOT_RUN: gerçek model gerekir (PayCore S1 / llmaas); fake-llm 'hello' der (canary absent and fact present in a real answer); NOT_RUN: gerçek model ve triyaj agent'ı gerekir (ticket-desk ve onay kapısı hazır: test_18_f2_7); NOT_RUN: injection recognizer is 08 full (plan/18 F11) |
| F12 | passed | 2 | 0 | 4 |  | NOT_RUN: Langfuse stopped: run completes, trace_delivery_failed recorded; service stop needs a compose-level runner (13b); NOT_RUN: Qdrant stopped: search returns a coded error, worker stays healthy; service stop needs a compose-level runner (13b); NOT_RUN: LLM_SLOTS full: run queued, the wait is visible as an event; service stop needs a compose-level runner (13b); NOT_RUN: airgap: provider down, no request to an external host; service stop needs a compose-level runner (13b) |
| F13 | NOT_RUN | 0 | 0 | 4 |  | NOT_RUN: FOLLOWUP-101 (uploads get no updated_at_source, so by_recency cannot order v2 first; 04a, K-SEN-0028). The check stays for when the date is set.; NOT_RUN: gerçek model gerekir (PayCore S1 / llmaas); fake-llm 'hello' der (answer has the v2 value and 01.09.2025) |
| Negative | passed | 12 | 0 | 1 |  | NOT_RUN: FOLLOWUP-111 (no way to trigger 07's TTL sweep from a test; APPROVAL_TTL_MIN is 60 min on the stack) |
| Setup | passed | 13 | 0 | 0 |  |  |

Kırmızı → yeşil:
- dilim 1 (full_name): `test_13b_1` önce kırmızı, sonra yeşil; `test-samples` 54 OK (deterministik üretim dahil).
- dilim 3 (F tablosu): `test_13b_ftable_*` önce import hatası, sonra 5/5.
- dilim 2 (negatif): yığınsız 12 kırmızı (bağlantı), yığında 12/12 geçti.

Yol üstünde düzeltilen iki hata:
1. `tests/e2e/scenarios/conftest.py`'nin skip kancası oturumdaki tüm öğeleri işaretliyordu; F tablosu testleri ve negatifler sessizce NOT_RUN olurdu. Artık yalnız kendi klasörü.
2. `tests.e2e.*` importları yalnız `python -m pytest` ile çalışıyordu; konteynerdeki `pytest` ile `ModuleNotFoundError`. Importlar `tests/e2e` köküne göre (rootdir sys.path).

Notlar:
- Run girdisi sınırı 20.000 karakter (`RunCreate.input`), plandaki 200.000 guardrail metin sınırı değil; test 20.001 ile 422 `validation_error` ve sağlayıcıya istek 0.
- `eval/results/` .gitignore'da yok: isci-a'nın `make eval` alt-claim'i ekler; bu dalda dosya bırakılmadı.
- `make e2e` (isci-a) tabloyu `pytest tests/e2e --f-table eval/results/e2e-<tarih>.md` ile alır; bilinen bulgular `tests/e2e/known_findings.json`'da (test adı → FOLLOWUP, not).

## Plan (hazırlık)

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
