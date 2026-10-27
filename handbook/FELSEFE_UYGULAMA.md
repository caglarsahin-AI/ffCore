# Felsefenin FFCore'daki Karşılığı

`FELSEFE.md` genel ilkeleri verir (bölüm D: "somut projede örneklerle bağla"). Bu dosya her ilkeyi FFCore'daki somut kurala bağlar. İkisi birlikte okunur; bir karar bir ilkeyle çelişiyorsa agent **durur ve işaret eder**, sessizce ihlal etmez.

## A. Meta-ilkeler → oturum davranışı

| İlke | FFCore'da |
|---|---|
| META-01 Pozisyon al ve yapılandırılmış sor | Koordinatör kullanıcı kararı gereken her soruyu **2-3 birbirini dışlayan A/B/C seçeneğiyle** sorar; önerdiği seçeneği önce “Önerilen” diye işaretler ve gerekçesini, ardından her seçeneğin etkisini/bedelini bir cümleyle yazar. Serbest metin yalnız seçenekler kararı dürüstçe ifade edemiyorsa kullanılır. İşçi teknik belirsizlikte varsayımını seçer, PR notuna yazar ve durmaz; kullanıcı kararı gerekiyorsa aynı yapıda `DECISION-` kaydı hazırlar. |
| META-02 Sycophancy yok | Review'de "iyi iş" yok; bulgu listesi var. Brief'teki bir madde yanlışsa işçi PR'da "brief hatalı, çünkü" yazar. |
| META-03 Karşı çık | Brief, PLAN ya da kullanıcı kararı zayıfsa argüman + alternatif `state/BLOCKERS.md` `DECISION-` kaydına yazılır; karar kullanıcının. |
| META-04 Doğrula | Kod hakkında cümle kurmadan önce `rg` ile bak (CODE_MAP keşif kuralı); PayCore'dan alınan her mekanizmanın **ölçülmüş varsayılanı** ile alınır (K1/K3 dersi: normalizer ve güven rozeti). |
| META-05 Açık noktayı açık bırak | KARARLAR.md'de üç durum: çözüldü / bilinçli ertelendi / reddedildi. Agent kendi başına "çözüldü" yazamaz; açık konu `DECISION-` kaydıdır. |
| META-06 80/20 | Bir özellik çekirdek 8 özelliğe, hafızaya, kanala ya da kaynağa hizmet etmiyorsa brief'e girmez; "düşük öncelik" diye bırakılmaz, ya kapsam dışına yazılır ya da reddedilir. |

## B. Mimari ilkeler → FFCore kuralları

| İlke | FFCore'da | Örnek |
|---|---|---|
| ARCH-06 Fail-loud | Sessiz fallback, kırpma, atlama yok. Her red kayıtlı ve gerekçeli. | Kapı 0-2 her elemeyi gerekçeyle yazar; `OLLAMA_CONTEXT_LENGTH` doğrulanmazsa `make smoke` kırmızı; model fallback'i yalnızca açık `chat-fallback` kaydıyla ve `run_events`'e `fallback` olayıyla; airgap'te dış sağlayıcıya düşüş **yok**, 503 `model_unavailable`. |
| ARCH-07 Çekirdeği ağırlaştırma | %1 senaryo + kalıcı karmaşıklık → reddet; `state/BLOCKERS.md`'ye gerekçeyle. | Postman içe aktarma reddedildi (OpenAPI yeter); composite MCP, npx köprüsü, web crawler kapsam dışı. |
| ARCH-08 Ağır işi doğru katmana | Dönüşüm ve hesap platformda değil uzman katmanda. | Text-to-SQL hesabı DB'de (salt-okunur sunum DB'si); raporlama Superset'te; veri hareketi FFEngine'de; model yönlendirme LiteLLM'de; izleme Langfuse'ta. Backend ince orkestratördür. |
| ARCH-09 Var olanı yeniden inşa etme | Alt platform yeteneği varsa onu kullan; kendi paralel sistemini kurma. | LangGraph `interrupt()` → onay kuyruğu (ayrı durum makinesi yok); Langfuse → trace, prompt yönetimi, maliyet; LiteLLM → router, retry, model DB API'si; Alembic → şema; `arq` → tek kuyruk. **Açık nokta:** 09 sınav tabloları Langfuse datasets/experiments üzerine kurulabilir mi (BLOCKERS `DECISION-4`). |
| ARCH-10 Açık kontrol | "auto" seçim yok; yöntem açık tercih, yoksa belirgin varsayılan ve ekranda görünür. | `VECTOR_BACKEND`, `INFERENCE_BACKEND`, `DEPLOY_PROFILE` açık; reranker açıkken `min_score` kapalı (tek eşik kuralı, ekranda yazılı); kanal kimlik eşlemesi e-postayla, bulunamazsa açık hata; güven rozeti varsayılan kapalı ve açılması bilinçli. |
| ARCH-11 Donmuş sözleşme | `handbook/CONTRACTS.md`: 13 sözleşme, kilometre taşında donar, sonra yalnızca additive; kırma = `BREAKING-` + kullanıcı onayı. | |
| ARCH-12 Dar ve derin | Cognipeer'in 31 servisiyle genişlikte yarışılmaz; 8 çekirdek + hafıza + kanal + kaynak derin yapılır (PLAN 9 kapsam dışı). Taban korunur: OpenAI-uyumlu facade, MCP, iki tema, salt-okunur mod. | |
| ARCH-13 Belirsiz terim | `handbook/TERMINOLOGY.md` bağlayıcı; "araç / aksiyon / MCP sunucusu", "kanal / kaynak / araç", "raw-silver-gold / bronze-silver-gold" ayrıştırıldı. | |
| ARCH-14 Reddedileni kaydet | KARARLAR.md "Reddedilenler" bölümü gerekçeli. | |

## C. Dokümantasyon ilkeleri → süreç

| İlke | FFCore'da |
|---|---|
| DOC-15 Kod-temelli | CODE_MAP keşif kuralı; PR planı bölüm 1 "bulunan semboller" zorunlu; `docs/` aynı PR'da. |
| DOC-16 Karar-tam | KARARLAR.md üç durumlu; "sonra bakarız" yasak, ya `DECISION-` kaydı ya "bilinçli ertelendi (yön + kısıt)". |
| DOC-17 Tek tek denetle | Dış inceleme listeleri (D, K, P, R maddeleri) tek tek sınandı; yeni liste gelince aynı yöntem: çözülü / tasarım-niyeti / gerçek açık. |
| DOC-18 Evrim izlenebilir | PLAN.md "Sürüm geçmişi" bölümü; KARARLAR tarihli; tersine dönen karar eski kararı silmez, "tersine karar" diye işaretler. |
| DOC-19 İç tutarlılık | Her dalga kapanışında koordinatör denetimi: sürüm etiketi, çapraz referans, terim, karar-içerik çelişkisi (EXECUTION_HANDBOOK 8). |
| DOC-20 Sürüm disiplini | PLAN.md sürüm numarası + geçmiş; kod `docs/degisiklikler.md`; bağlı belgeler aynı PR'da. |

## Felsefe kontrolü (her PR planında zorunlu üç soru)

1. **ARCH-07:** Bu değişiklik kaç senaryoya değer katıyor, çekirdeğe kalıcı karmaşıklık ekliyor mu?
2. **ARCH-09:** LiteLLM, Langfuse, LangGraph, Postgres, `arq` ya da Next.js bunu zaten sunuyor mu?
3. **ARCH-10 / ARCH-06:** Gizli otomatik davranış ya da sessiz fallback var mı; varsa açık tercih ve kayıtlı olaya çevrildi mi?
