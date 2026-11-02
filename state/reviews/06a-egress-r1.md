# fix/06a-egress-all-messages · review r1 (KOD TURU, yığınsız)

**Tam SHA:** b9eefe3b93bd1d6ca55b5a4a22c26db45111a20d (baz 07dc421, 1 commit, 4 dosya; `state/` diff'i 0) · **Tarih:** 2026-11-02 10:01 · **Güvenlik turu:** evet (aşağıda) · **Karar: KOD-ONAY (ön)** — BLOCKER 0 · MAJOR 0 · MINOR 3. İstek yığınsız bir kod turuydu; yığınlı tur (gerçek Redis/Postgres entegrasyonu, (e)/(f) senaryoları) yapılmadan **nihai ONAY değildir**. Yazan oturum Sonnet 5.5 olduğu için kodu satır satır okudum ve gerçek motorla probe yazdım.

## Koşular
- Birim paketi tamamı (`tests/unit`, tools imajı `0.0.0-06b`, worktree salt-okunur bağlandı): **669 passed**. Contract ve ruff **koşmadım** (ruff salt-okunur bağlamda cache yazamadı; işçi "ruff temiz" diyor, doğrulanmadı).
- **Kendi probe'um** (state/reviews/134-r1-probe.py): GERÇEK guardrail motoru (built-in default politika, `engine.evaluate`, MemoryTokenStore) arkasında `graph._egress_messages`; 17 kontrol, FAIL yok.
- NOT_RUN: `test_134_llmaas_every_message_tokenized_and_idempotent`, `test_134_airgap_has_no_egress_stage` (Postgres+Redis), (e) kalıcı konuşma + run_sql satırı → fake-llm `/_requests`, (f) F4 genişletmesi, `make test` iki profil. Disk 21 GB olduğu için yığın açmadım.

## İstenen noktalar
- **Tek kontrol noktası:** `ctx.model.call` yalnız `graph.model` düğümünde (grep: başka çağrı yok); `outgoing = await _egress_messages(...)` hemen öncesinde. ✔
- **Sistem prompt'u, geçmiş (user/assistant), araç sonuçları:** probe — e-posta/telefon system, geçmiş user, assistant ve tool mesajında gerçek motorla tokenize; ham değer kalmadı; aynı e-posta system ve tool'da aynı `<<PII_1>>`. ✔
- **tool_calls.arguments:** egress'e girmiyor (yalnız `content`). PR "tool_guard'da zaten maskeli" diyor; ama built-in politikada PII kuralı yalnız `egress` aşamasında ve `tool.pre` aşamasındaki PII kuralı `monitor` modda (uygulanmaz, yalnız kaydeder). Probe: `{"q": "ali.veli@example.com"}` olduğu gibi geri gidiyor. → **MINOR-1**.
- **Önbellek anahtarı:** `sha256(content)` → maskeli metin, `RunContext` örneğine ait sözlük (modül/küresel değil; yalnız `adapters.py:582` oluşturuyor); iki bağlam birbirinin önbelleğini görmüyor (probe). Run/proje kimliği anahtarda yok ama paylaşılan bir yapı da yok → sızıntı yok. Tokenlar run kapsamlı (`scope=run_id`); `<<PII_1>>` benzeri sahte metin taze kapsamda hiçbir şeye çözülmüyor (probe). ✔
- **Idempotans:** maskeli çıktı taze önbellek + aynı token deposuyla tekrar verildiğinde aynen dönüyor (probe, gerçek motor). Redis'li hali koşulmadı. ✔ (kısmen)
- **block:** `enforce` politikada araç sonucundaki sır → `StopRun(failed, "guardrail_block")`, model çağrılmıyor (probe + birim). Not: default politika `monitor` modda olduğu için `secrets` kuralı egress'te de yalnız kaydediyor, engellemiyor (probe: AWS anahtarı geçti). Bu 08'in mevcut anlamı, bu PR'ın değişikliği değil; yine de "block = failed" yalnız enforce politikada geçerli, PR metni bunu söylemeli. ✔ (not)
- **request_messages:** `outgoing` (maskeli) yazılıyor, birim test eşitliği kanıtlıyor. ✔
- **Airgap:** `EngineGuard.check("egress")` `egress_enabled=False` iken `allow` + aynı metin döndürüyor; ek `if profile` yok; birim test geçti. Entegrasyon NOT_RUN.

## Bulgular
**MINOR-1 — assistant `tool_calls[].function.arguments` egress'ten geçmiyor** (graph.py `_egress_messages`: yalnız `content`). Default politikada `tool.pre` PII'yı uygulamıyor; yani "modele giden tüm mesajlar egress'ten geçer" ilkesinin bu alanı boşta. Gerçek etki küçük: argümanı üreten modelin kendisi, ona yalnız tokenlı metin gitti; yeni ham değer ancak modelin kendi ürettiği/ezberinden geleni olur. Yine de K-134-0002 "tool_calls.arguments"u özellikle sordu. Öneri: argüman JSON'unu da aynı noktadan geçir (yeniden `json.dumps`) ya da PR'daki "zaten maskeli" cümlesini düzelt ve default politikada ham kalabileceğini testle belgele.
**MINOR-2 — `guard_in`in zaten egress'ten geçirdiği kullanıcı mesajı model düğümünde ikinci kez denetleniyor** (önbellek `guard_in`de beslenmiyor; probe: ek `check` çağrısı). Tokenlı çıktıda ikinci geçiş bir şey değiştirmiyor, ama `monitor` modlu bir kural (örn. secrets) iki kez olay/`guardrail_hook` yazar → telemetri ve `guardrail_block_rate` çift sayım riski. Bu çıkarım koddan; gerçek DB'de **gözlemlemedim**. Öneri: `guard_in`de `ctx.egress_cache[sha(outgoing.text)] = outgoing.text`.
**MINOR-3 — sessiz atlamalar/ayrı hata kodu:** (a) `content` str değilse (liste/bölümlü) mesaj denetlenmeden geçiyor (fail-loud ilkesi); bugün üreten yok (system, geçmiş, user, tool hep str), ama bir gün biri çıkarsa sessiz delik; açık hata fırlat ya da testle sabitle. (b) >200.000 karakterlik tek mesaj `TextTooLong` fırlatır, runner bunu genel `run_error`a çevirir (`guardrail_block` değil); araç sonucu `TOOL_RESULT_MAX_CHARS` ile, geçmiş/sistem bütçeyle sınırlı, bu yüzden pratikte ulaşılmaz — yine de `guardrail_block`/açık kodla eşlemek daha okunur.

## Test boşlukları (bulgu değil, öneri)
Birim testler sahte guard kullanıyor (gerçek motor yalnız entegrasyonda, o da koşulmadı); `tool_calls.arguments` ve `guard_in` çift denetimi için test yok. Yığınlı turda mutlaka: gerçek Redis'le idempotans, (e) fake-llm `/_requests` içinde ham e-posta/telefon aranmaması, iki profil.

## Güvenlik turu (özet)
Kimlik/ACL ve SQL: değişiklik yok. **Gizlilik/egress:** yukarıdaki tablo; sağlayıcıya giden her `content` tokenlı (default politika, probe). **Log/PII:** `request_messages` olay yükü artık maskeli (öncekinden güvenli); tokenlar run kapsamlı, kapsamlar arası çözüm yok. Yeni bağımlılık, yeni uç nokta yok.
