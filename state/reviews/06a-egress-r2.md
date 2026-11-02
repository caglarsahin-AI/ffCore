# fix/06a-egress-all-messages · review r2 (delta + yığınlı tur)

**Tam SHA:** 10e86bf0d54215e2783ed304e6af712798666858 (r1 KOD-ONAY SHA b9eefe3 üstüne 2 commit, 4 dosya; `state/` diff'i 0) · **Tarih:** 2026-11-02 11:18 · **Güvenlik turu:** evet · **Karar: ONAY** · BLOCKER 0 · MAJOR 0 · MINOR 1 (yeni, düşük). Yığın review134 (18190/13190), `down -v` ile kapatıldı; worktree temiz doğrulanıp `git worktree remove` ile kaldırıldı.

## Koşular
- Hedefli (birim + iki entegrasyon dosyası, gerçek Postgres+Redis+LiteLLM+fake-llm): **12 passed**.
- Tam entegrasyon llmaas: **682 passed, 4 skipped** (state/evidence/134r2-int-llmaas.log). Unit+contract llmaas **745 passed**; airgap (`DEPLOY_PROFILE=airgap`, `GUARDRAIL_EGRESS_ENABLED=false`) unit+contract+iki 134 entegrasyonu **749 passed**.
- Kendi entegrasyon probe'um (state/reviews/134-r2-probe.py): 4 test, hepsi geçti.
- r1 probe'u (134-r1-probe.py) r2 koduna karşı: beklenen farklar — arguments artık ham kalmıyor, liste içerik artık `StopRun` fırlatıyor (r1'deki "kalıyor/sessiz geçiyor" iddialarım artık yanlış, düzeltmeler bunlar); `egress_cache` iki anahtar tutuyor (girdi ve maskeli çıktı), r1 probe'un "tek anahtar" varsayımı bu yüzden FAIL gösterdi, kusur değil.
- NOT_RUN: lint (işçinin kanıtı), gerçek bir uçtan uca run (API → worker → mcp-sql), bkz. madde 5.

## İstenen noktalar
1. **MINOR 1-3 kapanışı:** (a) `tool_calls[].function.arguments` değer değer egress'ten geçiyor, yapı bozulmuyor; entegrasyon probe: iç içe `{"sql":"-- <<PII_2>>","nested":{"to":["<<PII_4>>",{"phone":"<<PII_3>>"}],"n":3,"flag":true}}`, sağlayıcıya ham e-posta/telefon gitmiyor, `detokenize` hepsini geri getiriyor, çözülmemiş yok. (b) `guard_in`in sonucu `egress_cache`e yazılıyor: `guardrail_hook` satırları [input.pre, egress(user), egress(system)] ve ikinci `model` çağrısı hiç ek denetim eklemiyor (r1'deki çift olay riski kapandı). (c) `unsupported_message_content` (liste içerik ve JSON olmayan arguments) ve `guardrail_text_too_long` (200.001 karakter) kodlu `StopRun`; üçünde de sağlayıcıya hiçbir istek gitmedi (fake-llm `/_requests`). docs/agentlar.md iki kodu listeliyor. ✔
2. **İki entegrasyon testi gerçek Postgres+Redis ile:** `test_134_llmaas_provider_sees_no_raw_identifier` ve `test_134_airgap_has_no_egress_stage_...` geçti; idempotans Redis token deposuyla (kendi probe'umda ikinci `model` çağrısı + yeni bağlam). ✔
3. **Sağlayıcı isteği:** fake-llm `/_requests` gövdesinde system, geçmiş user, assistant içeriği, tool satırı ve `tool_calls.arguments` içinde ham e-posta/telefon aramam (probe'um dahil) sonuç: yok. ✔
4. **Airgap:** `EngineGuard(egress_enabled=guardrail.guardrail_egress_enabled)` (adapters.py:572, yapılandırma değeri, `if profile` yok); egress kapalıyken `check` metni değiştirmeden `allow` dönüyor; airgap testleri geçti. ✔
5. **İşçi sınırı ("kalıcı konuşma + gerçek run_sql yerine aynı model düğümü LiteLLM/fake-llm yoluyla"):** **Kabul edilebilir.** Gerekçe: tek kontrol noktası `model` düğümü (başka `ctx.model.call` yok), kullanılan parçalar gerçek (EngineGuard, Redis token deposu, `resolve_policy`, `LiteLLMModel`, fake-llm istek günlüğü); geçmiş/system/tool mesajlarının nereden geldiği (bağlam fabrikası, mcp-sql) düğümün girdisini değiştirir ama denetim noktasını değiştirmez. Dürüst sınır: gerçek bir API→worker→mcp-sql koşusunu ben koşmadım. İstenirse F4/plan-18 senaryosu e2e aşamasında ayrıca koşulabilir; bunu DUZELT şartı yapmıyorum.
6. **Worker/agent-worker logları:** review134 yığınında worker, agent-worker, agent-worker-bg, backend, litellm ve fake-llm loglarında test kimliklerini (e-posta ×3, telefon, TCKN) aradım: 0 eşleşme. **Sınırlama:** 134 testleri model düğümünü tools konteynerinde sürüyor, worker servislerinde değil; bu 0 sayısı worker kod yolunu ispatlamaz, yalnız bu yığında sızıntı olmadığını gösterir.

## Bulgu
**MINOR-4 (yeni, düşük) — sayısal JSON değerleri egress'ten geçmiyor.** `_egress_json` yalnız string'leri denetliyor; probe: `{"id": 10000000146}` (TCKN sayı olarak) sağlayıcıya **ham** gitti. Etki küçük: argümanı üreten model o değeri zaten tokenlı bağlamdan göremezdi (ham sayı ancak modelin kendi ürettiği/ezberlediği olabilir), ama "tüm değerler" iddiası sayılar için doğru değil. Öneri: PR/doc'ta "yalnız metin değerleri" diye yaz, ya da sayıları da string'e çevirip denetle. Merge'ü engellemez.

## Not
Önbellek hem girdi hem maskeli çıktıyı anahtarlıyor; maskeli bir metne birebir eşit gelen sonraki mesaj tekrar denetlenmez. Maskeli metin zaten denetlenmiş girdinin alt kümesi olduğu için bunu sorun görmüyorum (teorik).

## Güvenlik turu (özet)
Sağlayıcıya giden her metin alanı (system, geçmiş, assistant, tool, tool_calls.arguments metinleri) tokenlı; run kapsamlı token deposu başka run'ın tokenını çözmüyor (probe 4: ikinci run'da `<<PII_1>>` kendi kapsamında çözülüyor, birinci run'ın e-postasına değil); `request_messages` olayı maskeli; hata yolları sağlayıcıya hiçbir şey göndermiyor. Kimlik/ACL/SQL/yeni uç: değişiklik yok.
