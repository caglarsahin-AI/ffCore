# 11. Son kullanıcı chat arayüzü [FFCore Console]

**Bağımlılık:** 06a, 07. **Süre:** 3 gün. **Dalga:** PoC sonrası (karar 7: PoC chat'i Open WebUI; kaynak kartları ve ilerleme `x_platform` alanıyla metin olarak taşınır). **PoC:** hayır.

## Amaç

Yayınlanmış agent'ları son kullanıcının (çağrı merkezi, İK, yönetim) kullanacağı sade bir sohbet ekranı. Cognipeer'in "Portals" karşılığı. Yönetim önyüzünden ayrı rota (`/chat`), aynı Next.js uygulaması içinde.

## Kapsam

- (P4 kararı) Pilotta sohbeti analist ve bilgi işlem kullanıcıları kullanır; "son kullanıcı" ifadeleri bu sürümde o kullanıcıları kapsar. Yüzlerce son kullanıcı ve `user` rolü aktivasyonu 17'de (M6 sonrası); ekran tasarımı `user` rolünü (yalnızca `/chat`, yönetim menüsü yok) şimdiden destekler.
- Giriş sonrası kullanıcının erişebildiği yayınlanmış agent listesi (`project_members` ve agent `status=published`). Sohbet, salt-okunur (`access=read`) kullanıcılar için de açıktır: soru sorar, cevap alır, kendi konuşmalarını siler; ancak onay verme ve "sınava ekle" gibi platform mutasyonları yalnızca `edit` modunda aktiftir.
- Sohbet: konuşma listesi (sol), mesajlar (orta); token akışı; araç çağrısı kartı ("SQL çalıştırılıyor…", sonuç özeti, açılır ayrıntı); kaynak kartları (belge adı, sayfa, tıklayınca parça metni); onay istemi inline (kullanıcı yetkiliyse onaylar, değilse "onay bekleniyor" durumu ve bildirim); agent sorusu (ask_user) için cevap kutusu.
- Dosya eki: ilk sürümde yok.
- Geri bildirim: her cevapta beğen/beğenme + isteğe bağlı not; `messages.feedback` alanına; Langfuse'a score olarak da gönderilir (02).
- Konuşma başlığı otomatik, **model çağrısı olmadan** ilk mesajın ilk 60 karakterinden türetilir (PayCore düzeltmesi D6: Open WebUI benzeri istemciler her sorudan sonra başlık/etiket/takip önerisi için ek model çağrısı yapar; CPU'da her biri tam bir çağrıdır). Takip sorusu önerisi, otomatik etiket gibi arka plan model çağrıları yoktur. Silme (soft delete, retention `content` sınıfı).
- Cevapta güven rozeti **varsayılan kapalı** (06, PayCore kontrolü K3): yalnızca agent'ta `show_confidence: true` ve kalibre edilmiş `confidence_threshold` ayarlanmışsa eşik altı cevap "düşük güven" rozeti alır; aksi halde skor yalnızca run detayında (10) görünür. `declined` cevap (modelin kendi "bulamadım" demesi) her zaman "kaynaklarda bulunamadı" rozetiyle gösterilir; kaynak kartlarında güncelleme tarihi yazılır.
- Mobil uyumlu düzen.
- Açık ve koyu tema: 10'daki token altyapısı ve tema anahtarı aynen kullanılır; mesaj balonları, kaynak ve araç kartları, kod blokları, onay istemi iki temada okunabilir; portal ayarındaki tema rengi (vurgu) iki temada da kontrastı korur (açık ve koyu için ayrı ton türetilir).
- Yönetim tarafı için "Portal" ayarı: agent başına karşılama metni, örnek sorular (3 adet), tema rengi; `agents.portal_config jsonb` (06 modeline küçük ekleme, bu pakette migration).

## Teslimatlar

- `/chat` rotaları, bileşenler, Playwright testi (soru sor, kaynak kartı gör, onay ver).
- `docs/chat.md`.

## Kabul kriterleri

- Yayınlanmamış agent listede görünmez.
- Kaynak kartına tıklayınca ilgili parça metni ve sayfa görünür.
- Onay yetkisi olmayan kullanıcıda onay düğmeleri yoktur; onay başka kullanıcı tarafından verilince akış ekranda devam eder (SSE yeniden bağlanma ile).
- Geri bildirim Langfuse'ta ilgili trace'te score olarak görünür.

## Teknik notlar

- 10'daki test paneli ile aynı sohbet bileşenleri kullanılır; bileşenler `frontend/components/chat/` altında paylaşımlı.
- SSE bağlantısı koparsa `GET /runs/{id}/events?since=seq` ile tamamlama.

## Kapsam dışı

Ses, dosya eki, Slack/Teams kanalı, gömülebilir widget (ileride `services/widget`).
