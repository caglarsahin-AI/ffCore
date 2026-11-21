# Dalga raporu · 21 Kasım 2026 (dalga 8: son kullanıcı chat arayüzü + hook/egress dilimi, kapanış) · TASLAK

Yazan: koordinatör (lease ffcore-koordinator-20261102). Şablon: docs/takim/ajanlarla-gelistirme.md 9.3. Önceki rapor: state/dalga/dalga-7-kapanis.md (onaylı 20 Kasım, "Onay, A: 11"). Onay: kullanıcı.

## 1. Dalga, paketler, main, kapı logları

Dalga 8 planı (20 Kasım, onaylı A): paket 11 (kendi `/chat` ekranı, DECISION-193 A) isci-c şeridinde iki PR; hook/egress küçük dilimi (block geçişi, FOLLOWUP 208/210/212/213) isci-b şeridinde; inceleyici tek oturum. Hepsi main'de; kapı logları `state/evidence/`.

| Paket | Merge | Main kapısı | Log |
|---|---|---|---|
| fix/hook-egress-1: `FFCORE_GUARD_MODE=block`, KAPI heredoc daraltması, çıplak `docker build` kuralı, hook testi host `py -3.12` (212), initdb metni (213), backend egress proxy taşıyıcısı `_ProxyTransport` (208) | c1d79f4 (20 Kas 22:17) | KIRMIZI: `McpServiceSettings` `egress_proxy_url` yok → mcp-sql 500 | gate-hke-20261120.log |
| fix/hke-mcp-settings: paylaşımlı `EgressProxyUrl` alanı, MCP servisleri proxy ayarını okur | f088aa8 (20 Kas 23:10) | yeşil 2159×2, test-int 1164, hooks host 421 | gate-hkefix-20261120.log |
| 11-1: `/chat` rotaları, yayınlanmış agent listesi, konuşma listesi + mesajlar, token akışı (SSE bekçisi + `events?since=`), araç ve kaynak kartları (parça metni ucu, ACL'li), `declined`/güven rozetleri, soft delete, mobil + iki tema | 15f1da9 (20 Kas 23:40) | KIRMIZI: test-int 2 parity (`conversation_id`, `chunk_id` fikstürsüz); e2e 35 düşüş kapı betiği hatası (yalnız backend+worker FAKE_EMBED=1) | gate-111-20261120.log |
| fix/11-1-parity: `PARITY_EXEMPT` + 11-1 kendi parity testi (yalnız test) | d3f96ed (21 Kas 01:25) | yeşil (ENV-217/218 sonrası): 2159×2, test-int 1167/42, Vitest 296, e2e @model-missing 1/1 + tam yığın 197/0 | gate-111p-20261121b.log |
| 11-2: satır içi onay, `ask_user` cevap kutusu, kullanıcı oyu (`messages.user_feedback` + Langfuse `user_feedback`, `source: chat`), agent Portal ayarı (`agents.portal_config`, karşılama, 3 örnek, vurgu rengi; konsol Portal sekmesi), göç `11_0001` | 6590719 (21 Kas 08:41) | yeşil: 2159×2, **test-int 1190/42**, Vitest 323 (60 dosya), e2e @model-missing 1/1 + **tam yığın 203/0** (ilk koşuda `npm ci` registry soket kopması, ortam; tekrar yeşil) | gate-112-20261121.log, gate-112-20261121-e2e-rerun.log |

Test sayısı dalga boyunca 2117 → 2159 (birim+sözleşme, profil başına), 1143 → 1190 (entegrasyon), Vitest 279 → 323, hook testleri 347 → 421, e2e tam yığın 186 → 203. İnceleme turları: hook-egress-1 2 + fix 1, 11-1 2 + parity 1, 11-2 2; toplam B0 M0; r1 MINOR'lar r2 kısa dilimlerle kapandı (11-2 MINOR-1 veri sınırı sınıfı: `user` rolü + `source=review` → 403 `not_reviewer`). Push: `origin` ve `paycore` 1d82eba'da; **beş merge ve state commit'leri yerel** (push kullanıcı talimatıyla).

## 2. Bu dalgada alınan kararlar (KARARLAR; tek cümle)

- 20 Kasım · Dalga 8: 11 (isci-c) + hook/egress dilimi (isci-b); dalga 7 raporu onaylı; hook block geçişi dilim kapsamında.
- 20 Kasım · hook-egress-1 plan: KAPI heredoc daraltması A, 208 proxy taşıyıcı backend'de + ad kuralları, adres kuralları Squid'de; r1 ONAY m2 (sarmalayıcı kabuk gövdeleri komut sayılır, ENV mesajı, proxy red kodu); kapı KIRMIZI → fix/hke-mcp-settings (paylaşımlı `EgressProxyUrl`); yeşil, block etkin, 208/210/212/213 kapandı.
- 20 Kasım · 11 plan S1-S6 A: `conversations.py`, başlık 60, run sources ucu ACL'li, `user_feedback` score, `/chat/agents`, proje seçici; r1 ONAY m1 (axe opacity beklemesi, docs red kodları; kopuş testi 11-2'ye).
- 20 Kasım · 11-2 plan S1-S4 A: `messages.user_feedback` ayrı kolon + `FeedbackRequest.source` (F9 kuyruğu dokunulmaz), Portal sekmesi, vurgu tonu önyüzde türetilir, onay bildirimi yok.
- 21 Kasım · 11-1 kapısı KIRMIZI (parity fikstür) → DUZELT-MAIN fix/11-1-parity; e2e 35 düşüşü kapı betiği hatası (tüm yığın `up -d` kuralı).
- 21 Kasım · 11-1 kapısı YEŞİL, MERGED; ENV-218 dersi: `docker image prune` digest-pinli imajları siler, temizlik öncesi `compose config --images` korunur.
- 21 Kasım · 11-2 r1 ONAY m2 → r2 kısa dilim: `user`+`review` 403 `not_reviewer` (B sessiz varsayılan reddedildi), docs tablo; NOTE-1 `partial` kalır.

## 3. Tersine dönen kararlar

- 11 plan S4 ("son kullanıcı oyu `messages.feedback`'e"): işçi gerekçesiyle değiştirildi; ayrı kolon + `source` (F9 uzman kuyruğu ve uzman oyu korunur). r1'de API'den hâlâ delinebildiği görüldü, 403 ile kapatıldı.
- 11-1 kapısındaki e2e kırmızısı 11-1'e yazılmıştı; tekrar koşu kapı betiğinin hatası olduğunu gösterdi (agent-worker `FAKE_EMBED` almamıştı). Kapı betiği artık tüm yığını yeniden yaratır.
- hook-egress-1 kapısında proxy ayarı MCP servislerine taşınmamıştı; "ayar bir yerde tanımlanır" kuralı paylaşımlı Annotated tiple sağlandı.

## 4. İnsana kalan açık konular

- **Push:** `FFCORE_PUSH_OK=1` ile origin ve paycore aynası (c1d79f4, f088aa8, 15f1da9, d3f96ed, 6590719 + state; son push 1d82eba).
- **`docs/images` yeniden üretimi (çözüldü, FOLLOWUP-221):** kapının e2e B aşaması ekran görüntülerini ana kopyaya yazıyor; kullanıcı komutu: `git checkout -- docs/images` ve `git stash drop` (stash `koordinator-docs-images-regen-20261121`); kalıcı çözüm triage-2'de.
- **Oturum arşivi:** isci-c-11 (HANDOFF sonrası RETIRED). Worktree'ler (16): feat/04b-2, 04b, 05b, 10c-2, 10c-3, 11-chat, 11-2-chat, 12, 12-2, fix/10b-sse-bekci, 11-1-parity, ajan-hooklari ×2, followup-triage-1, hke-mcp-settings, hook-egress-1; imaj etiketleri `0.0.0-11`.
- **ENV-204:** küçük modelle (`qwen2.5:0.5b`) yerel doğrulama sürüyor (kullanıcı yığını açık); FOLLOWUP-219 nedeniyle yayımlanmış agent gerekir.
- **ENV-217/218 kalıntısı:** `04a-knowledge-core_*` PoC volume'ları (~14 GB) kullanıcı kararı; Docker Desktop VM 11,7 GB bellek ile iki tam yığın + Ollama sınırda.
- **12 PENDING_ENV** (kullanıcı donanımı): GPU vLLM + 10 eşzamanlı RAG ölçümü, ağsız tools derlemesi, test VM provası, iki sürüm geri alma, kurumsal CA, gerçek sağlayıcıya proxy çıkışı.
- **DECISION-1/2/3** açık (alan adı; `rewrite`/judge; NER eşiği).

## 5. Açık kayıt sayıları ve en riskli üçü

BLOCKERS.md 49,1 KB (>30 KB; DRIFT'lerin arşive taşınması önerisi sürüyor). Açık: FOLLOWUP 59, DRIFT 34, ENV 7, DECISION 3, DEBT 0. Bu dalgada kapanan: FOLLOWUP 135, 208, 210, 212, 213; ENV 217, 218. Açılan: FOLLOWUP 214, 215, 216, 219, 220, 221; ENV 217, 218.

En riskli üçü:
1. **FOLLOWUP-219** (04b-2 readiness / 01 seed): `_context_needs` model `limits.context_tokens` okur, şema ve seed `context_window` yazar; Ollama bağlam denetimi yalnız yayımlanmış agent varsa çalışır. Önerim A: anahtar `context_window`.
2. **FOLLOWUP-216** (süreç): ortak modül/OpenAPI/test sözleşmesi dokunan PR'lar PR-HAZIR öncesi tam test-int slotu alır; kural handbook'a yazılmadı (11-2'de fiilen uygulandı, 11-1'de uygulanmadığı için parity kırmızısı kapıda görüldü).
3. **FOLLOWUP-220** (test/e2e): `e2e_node_modules` volume'u her `down -v` ile silinir, `npm ci` her kapıda registry'ye çıkar; kesintide e2e düşer (bugün iki aşama). Kalıcı adlandırılmış volume ya da imajda bağımlılık.

## 6. Hook kayıtları (20 Kas 19:00 - 21 Kas 09:30; 9 satır, hepsi warn; block kipi 20 Kas 22:17'den beri, red 0)

KAPI 6 (heredoc ile `state/pr/*.md` ve test dosyası yazımı: komut metninde test sözcükleri), ENV 2 (py ile test dosyası düzenleme; onaylı touch-zone), PUSH 1 (inceleyici betik metninde "push" sözcüğü). Gerçek ihlal yok; block kipinde hiçbir komut reddedilmedi. Not: block geçişinden sonra işçiler kanal/PR yazımını Python betiğine taşıdı (uyarı sayısı dalga 7'de 32 → 9).

## 7. Sıradaki dalga için seçenekler (karar kullanıcıda; önerim A)

- **A (önerim): 14 kullanıcı hafızası + paralel triage-2 dilimi.** 14'ün bağımlılıkları (03, 04a, 06a, 08, 11, 13a) tamam; brief 3,5 gün: kullanıcıya özel kalıcı hafıza (çıkarım `memory-extract` modeli, onaylı yazım, konsol/chat hafıza paneli, silme hakkı). isci-c şeridi. Paralel küçük dilim (isci-b): FOLLOWUP-219 A, 216 handbook kuralı, 220 e2e node_modules, 214/215 hook/egress test küçükleri. Etki: çekirdek 8 özellikten hafıza kapanır; chat ekranı ilk gerçek "kişiselleşme" özelliğini alır; triage borcu büyümez.
- **B: 15 kanallar (yalnız web widget).** Etki: 11 üstüne gömülebilir widget; Slack/Teams 17'ye (AD/LDAP) bağlı olduğu için yarım paket; önerilmez.
- **C: 16 veri kaynağı bağlayıcıları (Confluence/Jira önce).** Etki: 8 günlük büyük paket, PayCore Data Center bağlayıcıları terfi; egress profili ve FOLLOWUP-211 ile birlikte; kullanıcı ortamı (Confluence erişimi) ister.

Her seçenekte: inceleyici tek oturum sürer; 11 kanal arşivi HANDOFF sonrası.

## Onay

Kullanıcı bu raporu okuyup onaylar ya da bir maddeyi geri çevirir; koordinatör onayı WORK_QUEUE "Kapılar" tablosuna tarih ve rapor yoluyla yazar. Onayla birlikte seçilen dalganın GOREV'leri yazılır.
