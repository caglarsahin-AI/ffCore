# 15. Kanallar: web widget, Slack, Teams, Mattermost [FFCore Channels]

**Bağımlılık:** 06a, 07, 11, 03b (`core/egress.py`); Slack ve Teams **17'ye (AD/LDAP) bağlıdır** (A9: kurum kullanıcıları dizin olmadan eşlenemez). **Süre:** 7 gün (inceleme v4-v6: dört adaptör, widget paketi, kart biçimlendiriciler). **Dalga:** PoC sonrası. **Sıra:** önce web widget ve Mattermost (yerel kullanıcılarla çalışır), 17 bitince Slack ve Teams. **Profil:** widget ve Mattermost her ikisi; Slack ve Teams yalnızca `llmaas`. **PoC:** hayır.

## Amaç

Kullanıcının agent'a zaten çalıştığı yerden ulaşması: intranet sayfası, Slack, Microsoft Teams, kurum içi Mattermost. Kanal, agent'a "araç" değil **kullanıcı yüzeyidir** (TERMINOLOGY; "tek giriş kapısı" facade'ın adıdır, N27); mesajı alır, platform kullanıcısına eşler, run başlatır, cevabı kanalın diline çevirir, onayı kanal içinde düğmeyle alır.

## Kapsam

### Ortak kanal çekirdeği (`backend/app/channels/`)

- `channels(id, project_id, kind: widget|slack|teams|mattermost, name, config (şifreli: token, app id, signing secret, workspace/team kısıtı), status, created_by)`
- `channel_bindings(channel_id, agent_id, scope: default|mention|room, room_id nullable)`: kanalda hangi agent cevap verir; birden çok agent varsa `@agent-adı` ile seçim ya da oda bazlı eşleme.
- `channel_identities(channel_id, external_user_id, user_id, verified_at)`: kanal kullanıcısı → platform kullanıcısı. Eşleme e-posta ile otomatik (kanal API'sinden e-posta alınır), bulunamazsa "platformda hesabınız yok" cevabı ve admin'e bildirim. Rol ve erişim modu (03) bu eşlemeden gelir; sohbet salt-okunur kullanıcıya da açık (11 kuralı).
- `channel_threads(channel_id, external_thread_id, conversation_id)`: kanal thread'i = platform konuşması; bağlam thread içinde korunur.
- Akış: gelen mesaj → kimlik → konuşma → 06 `POST /agents/{key}/runs` (channel=`slack` vb.) → event'ler toplanır → kanala tek cevap. Streaming yok; "yazıyor" göstergesi, 15 saniyeyi geçerse "hazırlıyorum" ara mesajı (CPU model için şart).
- Format çevirici: platform Markdown'ı → Slack mrkdwn / Teams Adaptive Card / Mattermost Markdown; kaynak kartları bağlantı listesi; araç çağrıları kısa özet; tablolar kanal desteklemiyorsa kod bloğu.
- Onay: `approval_required` event'i kanalda düğmeli mesaj olur (Onayla / Reddet + not); düğmeye basanın kimliği `channel_identities.verified_at` dolu bir eşlemeyle platform kullanıcısına çözülür ve 07 kuralları (rol, `access=edit`) uygulanır; doğrulanmamış kimlikle düğme 403 ve "platformda hesabınız yok" (C4/C14 istisnası). Karar sonrası thread'de devam.
- Rate limit ve kötüye kullanım: kanal başına dakikada istek sınırı; kanal kimliği doğrulanmamış istek reddedilir (Slack signing secret, Teams JWT).
- Her kanal mesajı `runs.channel` (`slack|teams|mattermost|widget`; enum değerleri 06'da tanımlı, R10.4) ve `run_events`'e yazılır; audit'te kanal kaynağı görünür.

### Web widget (her iki profil)

- `services/widget/`: tek `<script>` etiketiyle intranet sayfasına gömülen sohbet balonu; 11'deki sohbet bileşenlerinin hafif sürümü; tema açık/koyu, Türkçe.
- Kimlik: sayfadan verilen imzalı kısa ömürlü token (kurumun intranet oturumundan türetilir) ya da widget içi giriş.
- Agent sihirbazında "Kanallar > Widget" sekmesi: gömme kodu, izin verilen alan adları, karşılama metni.

### Slack (`llmaas`)

- Socket Mode: sunucu Slack'e dışarı doğru WebSocket açar, içeri port gerekmez; yalnızca `slack.com` çıkış izni.
- Slack uygulaması manifesti `deploy/channels/slack-manifest.yaml` (scopes: `app_mentions:read, chat:write, im:history, users:read.email`...).
- DM ve `@mention`; thread'de bağlam; Block Kit ile onay düğmeleri ve kaynak listesi.

### Microsoft Teams (`llmaas`)

- Bot Framework: Azure Bot kaydı ve Microsoft'un ulaşabileceği HTTPS uç noktası gerekir; ters proxy'de **yalnızca** `/channels/teams/messages` yolu dışarıya açılır (12, C16). Kimlik Microsoft JWT ile doğrulanır; kullanıcı e-postasının Teams etkinliğinde her kiracıda gelip gelmediği **doğrulanmadı** (v4 U7): gelmiyorsa `TeamsInfo.getMember` ile alınır, bu da brief'e işçi tarafından yazılır. Dış HTTP çağrıları `core/egress.py` ile.
- Kişisel sohbet ve kanal `@mention`; Adaptive Card ile onay ve kaynaklar.
- Teams manifesti `deploy/channels/teams-manifest.json`.

### Mattermost (`airgap` isteğe bağlı)

- Kurum içi Mattermost varsa: outgoing webhook ya da bot hesabı + WebSocket; aynı çekirdek, Markdown doğrudan.

### Yönetim ve izleme (10'a ekran)

- Kanallar ekranı: kanal ekle (tür, kimlik bilgileri, bağlantı testi), agent eşleme, kimlik eşleme listesi (eşlenmemişler), son 24 saat mesaj/hata.
- Agent sihirbazında "Kanallar" sekmesi.

## Teslimatlar

- Kanal çekirdeği, dört adaptör, widget paketi, manifest dosyaları, 10'a ekranlar, testler (sahte Slack/Teams olayları ile), `docs/kanallar.md` (kurulum adımları, gerekli izinler, çıkış listesi).

## Kabul kriterleri

- Widget'tan sorulan soru, 11'deki chat ile aynı cevabı ve kaynakları verir; `airgap` profilinde dış ağ olmadan çalışır.
- Slack'te `@asistan fesih süresi nedir` mesajına thread içinde kaynaklı cevap gelir; aynı thread'deki ikinci soru bağlamı korur.
- Onay gerektiren araç çağrısı Slack ve Teams'te düğmeli mesaj üretir; yetkisiz kullanıcı düğmeye basınca "yetkiniz yok" döner, yetkili basınca run tamamlanır.
- E-postası platformda olmayan Slack kullanıcısı nazik bir ret alır ve `channel_identities`'te "eşlenmemiş" olarak listelenir.
- Teams'ten gelen imzasız istek 401 ile reddedilir.
- `airgap` profilinde Slack ve Teams kanal türleri ekranda "bu profilde kullanılamaz" olarak pasiftir.

## Teknik notlar

- Slack için `slack-bolt` (Socket Mode), Teams için `botbuilder-core`; Mattermost için `mattermostdriver`.
- Teams Bot kaydı Azure portalında elle yapılır; adımlar `docs/kanallar.md`'de ekran görüntüsüyle.
- Kanal cevapları için ayrı bir prompt talimatı: kısa, Markdown lehçesine uygun, en fazla 3 kaynak.

## Kapsam dışı

WhatsApp, Telegram, e-posta kanalı, sesli kanal, kanal içinde dosya yükleme, Slack/Teams'ten belge indeksleme (16'nın işi).
