# 14. Kullanıcıya özel kalıcı hafıza [FFCore Agents]

**Bağımlılık:** 03, 04a (embedding), 06a, 08, 11, 13a (test seti). **Süre:** 3,5 gün (inceleme v4-v6). **Dalga:** PoC sonrası (M6). **Profil:** her ikisi (airgap ve llmaas). **PoC:** hayır.

## Amaç

Kurumun kalıcı kullanıcılarının (yöneticiler, bölüm sorumluları, uzmanlar) rolü, bağlamı, tercihleri ve geçmiş kararları hakkında öğrenilenlerin kurum içinde saklanıp her soruda modele kısa bir not olarak verilmesi. Kullanıcı her seferinde kendini anlatmaz; asistan zamanla o kişiye göre çalışır. Hafıza kullanıcının kontrolündedir ve hiçbir zaman kurum dışına çıkmaz.

Örnek: CFO ilk hafta "aylık özetleri bölüm bazlı ve TL cinsinden isterim, karşılaştırma geçen yılın aynı ayıyla olsun" der. Sonraki her soruda bu kural kendiliğinden uygulanır.

## Kapsam

### Veri modeli

- `memories(id, project_id, user_id, agent_id nullable, kind: profile|preference|fact|decision, text, embedding vector(EMBED_DIM), source_run_id, confidence 0-1, created_at, updated_at, last_used_at, use_count, expires_at, status: active|archived|deleted_by_user)`
  - `agent_id` boşsa hafıza o projedeki tüm agent'larda geçerli (profil ve tercih); doluysa yalnızca o agent'ta (karar ve gerçek).
- `memory_settings(project_id, agent_id nullable, enabled, allowed_kinds[], max_items_per_user, recall_top_k, ttl_days, extraction_model)`
- Retention sınıfı `memory` (03): varsayılan 365 gün, `min 30, max 1095`; kullanıcı silince anında ve kalıcı.

### Yazma: çıkarma

1. Run tamamlanınca (06 `finalize`) arka plan işi kuyruğa girer; kullanıcı deneyimini geciktirmez.
2. Ucuz model çağrısı (LiteLLM `<proje>.memory-extract` sanal modeli; 01 seed'lerinde tanımlı: `llmaas`'ta sağlayıcının küçük modeli, `airgap`'ta Qwen; R10.2): girdi son konuşma turu + mevcut hafızanın ilgili 5 maddesi; çıktı JSON: 0-3 aday madde, her biri `kind, text, confidence, supersedes_id?`.
3. Kurallar: yalnızca kullanıcı hakkında kalıcı bilgi (rol, tercih, tekrar eden bağlam, açık karar); geçici istekler, belge içeriği, üçüncü kişiler hakkında bilgi yazılmaz. Hasta ve kişi verisi kesinlikle yazılmaz; 08 guardrail `pii` kuralı `block` modunda çalışır, eşleşme varsa aday atılır ve `guardrail_events`'e düşer.
4. Tekilleştirme: aday embedding'i mevcut maddelerle karşılaştırılır; benzerlik > 0,9 ise birleştirilir (`supersedes`), eskisi `archived`.
5. `confidence < 0,6` adaylar yazılmaz. `max_items_per_user` aşılırsa en az kullanılan arşivlenir.
6. Açık komut: kullanıcı "bunu hatırla: ..." yazarsa çıkarma modeli atlanır, doğrudan `kind=preference, confidence=1`; **ama 08 `pii` kuralı (`block`) bu yolda da zorunlu çalışır (C19):** PII tespit edilirse madde yazılmaz, istek 400 `memory_pii_blocked` döner ve `guardrail_events` + audit'e yazılır.

### Okuma: geri çağırma

- 06 `prepare` düğümünde: soru embedding'i ile kullanıcının aktif hafızasından `recall_top_k` (varsayılan 5) madde; `profile` türü her zaman eklenir.
- Sistem prompt'una ayrı blok: "Kullanıcı hakkında bilinenler (kullanıcı bunları görebilir ve silebilir): ...". Modele talimat: bunlar bağlamdır, soru yerine geçmez; çelişkide kullanıcının güncel sözü geçerlidir.
- `last_used_at` ve `use_count` güncellenir; hangi maddelerin kullanıldığı `run_events`'e yazılır (şeffaflık).
- Token bütçesi: hafıza bloğu en çok `MEMORY_MAX_TOKENS` (varsayılan 300).

### Kullanıcı kontrolü (11 chat arayüzü)

- "Hafızam" sayfası: madde listesi (tür, metin, ne zaman öğrenildi, kaç kez kullanıldı), düzenle, sil, tümünü sil, hafızayı kapat (kullanıcı bazlı `opt_out`).
- Cevapta kullanılan hafıza maddeleri küçük bir "Bunları dikkate aldım" notuyla gösterilir; tek tıkla "bunu unut".
- Yeni madde öğrenildiğinde sessiz bildirim: "Şunu not ettim: ... [Sil]".

### Yönetici kontrolü (10 önyüz)

- Agent sihirbazına "Hafıza" sekmesi: açık/kapalı, izin verilen türler, madde sınırı, süre, çıkarma modeli.
- Proje ayarlarında varsayılan politika ve "hafıza içeriğini yöneticiler göremez" ilkesi: yöneticiler yalnızca sayı ve tür istatistiği görür, metni değil. (Kullanıcı güveni için şart; audit'te de metin yok, yalnızca olay.)
- Rapor: kullanıcı başına madde sayısı, kullanım oranı, silme oranı.

### Profil farkları

- `airgap`: çıkarma modeli Qwen; kalite için çıkarma prompt'u kısa ve JSON şema zorunlu; `confidence` eşiği 0,7.
- `llmaas`: çıkarma için küçük sağlayıcı modeli; hafıza metni çıkarma çağrısında dışarı gider, bu yüzden 08 `egress` aşaması çıkarma girdisine de uygulanır. Hafıza tablosu her zaman kurum içinde.

## Teslimatlar

- Migration, çıkarma işi, geri çağırma düğümü, API (`/memories` CRUD, `/memories/opt-out`, istatistik), önyüz ve chat ekranları, testler, `docs/hafiza.md`.
- Sentetik test seti `data/samples/memory/` 13a'da bağımsız üretilir (40 konuşma, beklenen hafıza çıktısı; C18); bu paket onu tüketir.

## Kabul kriterleri

- "Ben kardiyoloji bölüm sorumlusuyum" dedikten sonraki oturumda "bu ayki doluluk" sorusu bölüm sormadan kardiyoloji için cevaplanır.
- "Tabloları TL cinsinden isterim" tercihi sonraki cevaplarda uygulanır; kullanıcı sildikten sonra uygulanmaz.
- Test setinde TC kimlik ya da hasta adı içeren konuşmalardan hiçbir hafıza maddesi üretilmez (0 kaçak).
- Çıkarma, cevap süresini uzatmaz (arka planda; cevap `done` event'i hafıza işinden önce gider).
- Yönetici API üzerinden başka kullanıcının hafıza metnini okuyamaz (test: admin rolüyle 403); hafıza mutasyonları `@audited(audit_payload=False)` ile kaydedilir, audit'te metin yoktur (R10.1). Veritabanı ve yedek erişimi ayrı bir konudur (12 güvenlik sıkılaştırma).
- Kullanıcı hafızayı kapattığında yazma ve okuma tamamen durur.

## Teknik notlar

- pgvector ve 04'teki embedding kullanılır; ayrı altyapı yok. (P5) Kurulum başına tek embedding modeli kuralı burada da geçerli: `memories.embedding vector(EMBED_DIM)`; model değişince hafıza vektörleri de yeniden üretilir (metin saklı, kaynağa gidilmez). (P7, A8, 06 C12 tablosu) Hafıza çıkarma **etkileşimli-düşük** sınıftadır: `llm-background` kuyruğunda koşar ama pencere kuralına tabi değildir, gün içinde etkileşimli iş yokken hemen çalışır; mesai içinde etkileşimli kuyruk boşken, aksi halde pencerede koşar; kullanıcı deneyimini geciktirmez ama "şunu not ettim" bildirimi gecikebilir.
- Hafıza ile sohbet geçmişi farklıdır: geçmiş `messages` tablosunda, konuşmaya bağlı; hafıza konuşmalar arası, damıtılmış.
- Çelişki yönetimi: yeni madde eskisini `supersedes` ile geçersiz kılar, eski silinmez (arşiv), kullanıcı isterse görür.
- İleride: ekip hafızası (`scope: team`), kurumsal sözlük (`scope: project`). `scope` kolonu **şimdiden eklenmez** (N26 reddedildi, ARCH-07: additive olarak gerektiğinde eklenir; ilk sürümde yalnızca kullanıcı hafızası).

## Kapsam dışı

Ekip ve kurum hafızası, otomatik görev takibi, hafızadan proaktif hatırlatma.
