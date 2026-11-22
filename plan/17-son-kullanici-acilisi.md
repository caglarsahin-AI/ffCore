# 17. Son kullanıcı açılışı ve AD/LDAP girişi [FFCore Gateway]

**Bağımlılık:** 03a (kimlik, oturum çerezi, `user` rolü rezerve), 03b (audit), 03c (bildirim), 10a (giriş ve kullanıcı ekranları), 11 (`/chat`; `user` rolü tasarımda), 12 (egress izin listesi, TLS ters proxy), 14 (`/memories` `user` rolüne açık). **Tüketici:** 15 (Slack/Teams kimlik eşlemesi bu paketi bekler, A9). **Süre:** 3,5 gün. **Dalga:** M6 sonrası (dalga 10 adayı). **Profil:** her ikisi (LDAP ve OIDC ikisi de iki profilde; `airgap`'te sağlayıcı kurum içindedir, `llmaas`'ta OIDC sağlayıcısı egress izin listesine girer). **PoC:** hayır. Yazan: koordinatör, 22 Kasım 2026 (PLAN 7: "brief M6 sonrası yazılır").

## Amaç

Platformun yüzlerce kurum kullanıcısına açılması: kullanıcılar kurumun dizinindeki (Active Directory / LDAP) ya da kimlik sağlayıcısındaki (Keycloak, Entra ID; OIDC) hesaplarıyla girer, hesapları elle açılmaz, dizinden çıkınca kapanır; `user` rolü aktive olur ve yalnızca `/chat`, kendi hafızası ve kanalları görür; yönetici toplu kullanıcı ve grup → proje/rol eşlemesini ekrandan yönetir. Kimlik tek yerde çözülür; 15'in kanal ve widget kullanıcıları aynı çözümleyiciyle platform kullanıcısına bağlanır.

Bugünkü durum (03a): e-posta/şifre ile yerel kullanıcı, süperadmin tarafından tek tek açılır; roller `admin, developer, analyst` atanabilir, `user` enum'da rezerve (`ASSIGNABLE_ROLES` dışında); `/chat` ve `homePath` `user` rolünü zaten tanır.

## Kapsam

### `user` rolü aktivasyonu (03a/11/14 üstüne)

- `ASSIGNABLE_ROLES`'a `user` eklenir; `user` yalnız `/auth/*`, `/chat` uçları (konuşma, koşu, onay cevabı yalnız kendi koşusu), `/memories/*`, 15 kanal uçları; konsol uçlarında 403 (`require_role` sırası değişmez: `user < analyst`). Önyüz: `user` yalnız `(chat)`; `(console)` rotaları `/chat`'e yönlendirir.
- plan/03 yetki matrisi `user_edit`, `user_read` fikstürleri açılır; parametrik yetki testleri bütün matriste koşar (PoC'de atlanan iki sütun).
- `user` + `read` erişimi: sohbet yapar, kendi hafızasını siler/kapatır, şifre/tema/dil değiştirir (plan/03 salt-okunur istisnaları); onay verme ve "sınava ekle" `write` ister (değişmez).

### Kimlik sağlayıcıları

Yapılandırma `.env` ile (secret içerir; 12 kuralı), ekranda yalnız durum ve bağlantı testi. Aynı kurulumda LDAP ve OIDC birlikte açık olabilir; giriş ekranı açık olanları gösterir.

- **LDAP / Active Directory (bind):** `LDAP_URL` (ldaps:// zorunlu; `ldap://` yalnız `LDAP_ALLOW_PLAINTEXT=1` ile ve preflight uyarısıyla), servis hesabı bind DN + parola, `LDAP_USER_BASE`, `LDAP_USER_FILTER` (varsayılan `(|(mail={login})(userPrincipalName={login})(sAMAccountName={login}))`), `LDAP_GROUP_ATTR` (`memberOf`), `LDAP_CA_FILE` (kurumsal CA, 12 PENDING_ENV). Akış: giriş formu aynı (kullanıcı adı/e-posta + parola) → servis hesabıyla kullanıcı arama → kullanıcının DN'i ile bind → başarıysa **JIT provisioning** (yoksa `users` satırı açılır: `auth_source=ldap`, `external_id=objectGUID|entryUUID`, `password_hash NULL`) → grup eşlemesi uygulanır → oturum çerezi (03a, değişmez). Yanlış parola, bulunamayan kullanıcı ve bind hatası aynı 401 gövdesi (`invalid_credentials`); neden yalnız audit'te. Dizin erişilemezse 503 `identity_provider_unavailable` (sessiz yerel girişe düşüş yok).
- **OIDC (Keycloak, Entra ID, başka OIDC):** authorization code + PKCE; `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` (isteğe bağlı, public client olabilir), `OIDC_SCOPES` (`openid profile email groups`), `OIDC_GROUPS_CLAIM` (`groups`), `OIDC_REDIRECT_URL` (konsol origin'i, C6). Keşif belgesi (`/.well-known/openid-configuration`) açılışta bir kez çekilir ve önbelleklenir; `id_token` imzası JWKS ile doğrulanır (`iss`, `aud`, `exp`, `nonce`); `state` ve `nonce` sunucu tarafında (Redis, kısa ömür). Başarıda JIT provisioning (`auth_source=oidc`, `external_id=sub`) ve grup eşlemesi; sonra platformun kendi oturum çerezi (IdP token'ı saklanmaz; yenileme yok, oturum süresi `SESSION_TTL_S`). Sağlayıcı adresi `llmaas`'ta egress izin listesine girer (12); `airgap`'te sağlayıcı kurum içidir, dış adres kayıt anında reddedilir (`ALLOWED_INTERNAL_HOSTS`).
- **Yerel giriş politikası** `LOCAL_LOGIN=all|superadmin_only|off` (varsayılan `all`; dizin açılınca öneri `superadmin_only`): süperadmin için kilit-dışı giriş her zaman kalır (`off` bile süperadmini kapatmaz; kurtarma yolu). Dış kimlikli kullanıcıda `/auth/password` 400 `external_identity`.
- **Eşleme:** `identity_group_mappings(id, provider: ldap|oidc, external_group (DN ya da claim değeri), project_id nullable, role, access, created_by)`; `project_id` boşsa kurulum geneli (süperadmin değil: her projeye aynı rol) değil, **yalnız `user` rolü için varsayılan**: eşlenmeyen grup üyesi platforma girer ama hiçbir projede üye olmaz; `DEFAULT_PROJECT_FOR_NEW_USERS` (isteğe bağlı) verilmişse o projeye `user/read` (güvenli taraf). Birden çok grup eşleşirse en yüksek rol ve `edit` > `read`. Grup eşlemesi her girişte yeniden uygulanır: eşlemeden çıkan üyelik kaldırılır (`membership_source=idp` olanlar; elle verilenler dokunulmaz, `membership_source=manual`). Çakışma: aynı kullanıcı için elle verilen rol dizinden geleni ezmez; yüksek olan geçerli, kaynak kolonu ikisini de tutar.
- **Pasifleştirme:** LDAP için günlük `identity_sync` işi (arq cron, C9; `llm-background` dışı küçük iş): dizinde bulunamayan ya da `userAccountControl` pasif kullanıcılar `is_active=false`, oturumları `token_version` ile düşer; OIDC için IdP'nin işi (giriş reddedilir), ek olarak `OIDC_INACTIVE_AFTER_DAYS` (varsayılan 90) girişsiz kullanıcıyı pasife alır. Pasif kullanıcı girişte 403 `user_inactive`; audit'e yazılır.
- **Toplu kullanıcı (yerel):** `POST /users/import` (süperadmin) CSV (`email, full_name, role, access, project_keys`), `dry_run=true` ile ön rapor (yeni, güncellenecek, hatalı satırlar), sonra uygulama; parola yok: `must_change_password=true` ile geçici parola yalnız dönüş gövdesinde bir kez (03c e-posta bildirimi yapılandırılmışsa davet e-postası, `invite` şablonu). Dizin kullanan kurulumda içe aktarma yalnız istisna kullanıcılar içindir; belge bunu söyler.

### Kanal ve widget kimlik eşlemesi (15'in tüketeceği yüzey)

- `core/identity.py::resolve_external_identity(email | upn | external_id) -> User | None` tek çözümleyici; 15'in `channel_identities` eşlemesi ve widget token değişimi bunu kullanır. `AUTO_PROVISION_FROM_CHANNELS` (varsayılan kapalı): kapalıyken platformda hesabı olmayan kanal kullanıcısı nazik ret alır (15 kabul kriteri); açıkken LDAP/OIDC'de bulunan kullanıcı JIT açılır (`user` rolü, varsayılan proje).
- Widget için imzalı kısa ömürlü token değişimi (`POST /auth/exchange`, kurum intranet oturumundan türetilen `idp_token` → platform oturumu) OIDC doğrulayıcısını yeniden kullanır; 15 yalnız çağırır.

### Yönetim ekranları (10'a ekler)

- **Kullanıcılar** (süperadmin): kaynak rozeti (`local/ldap/oidc`), son giriş, pasif/aktif, içe aktarma (CSV yükle → ön rapor → uygula), geçici parola gösterimi bir kez.
- **Kimlik sağlayıcıları** (süperadmin, salt durum): hangi sağlayıcı açık, keşif belgesi/LDAP bağlantı testi düğmesi (servis hesabıyla arama; sonuç ve süre), `LOCAL_LOGIN` değeri, son `identity_sync` koşusu; secret gösterilmez.
- **Grup eşlemeleri** (süperadmin ve proje admin'i kendi projesi için): tablo (sağlayıcı, grup, proje, rol, erişim), ekle/sil, "kim etkileniyor" sayısı (üye sayısı, metin değil).
- **Giriş ekranı** (10a): yerel form + "Kurum hesabıyla gir" (OIDC) düğmesi; LDAP yerel formla aynı alanlardan girer (kullanıcı adı ya da e-posta); hata metinleri `messages/{en,tr}.json`; iki tema.

### Güvenlik

- Giriş denemeleri 03a kilitleme kuralıyla (varsa) aynı sayaçta; LDAP bind hatası sayılır. Audit: `login_success`/`login_failed` (`source`, neden yalnız audit'te), `user_provisioned`, `membership_synced`, `user_deactivated`, `user_imported` (`audit_payload=False` parola içeren hiçbir gövde yok).
- OIDC: `state`/`nonce` tek kullanımlık, 10 dk; geri dönüş yalnız kayıtlı `OIDC_REDIRECT_URL`; `id_token` `alg=none` ve HS* reddi; JWKS yenilemesi `kid` bulunamayınca bir kez. LDAP: filtre enjeksiyonu için `ldap3` kaçışı; `ldaps` ve CA doğrulaması; servis hesabı parolası log ve API'de maskeli.
- Dış kimlikli kullanıcı parola uçlarını kullanamaz; süperadmin dış kimlikli olamaz (yerel kurtarma hesabı kuralı; `is_superadmin` yalnız `auth_source=local`).

## Teslimatlar

- Göç `17_0001` (`users.auth_source, external_id, last_login_at, must_change_password`; `project_members.membership_source`; `identity_group_mappings`), `core/identity.py` (çözümleyici, JIT, eşleme), `core/ldap_auth.py`, `core/oidc_auth.py`, `identity_sync` işi, `api/auth.py` ekleri (`/auth/oidc/start`, `/auth/oidc/callback`, `/auth/exchange`, `/auth/providers`), `api/users.py` ekleri (import, mappings, providers status), `openapi/17.yaml`, konsol ekranları + giriş ekranı ekleri, `docs/kimlik.md` (LDAP ve Keycloak/Entra adım adım; Keycloak örnek realm dışa aktarımı `deploy/keycloak/` **yalnız geliştirme ve test için**), `.env.example` bölümü, preflight denetimleri (ldaps, redirect origin, airgap dış issuer).
- Testler: sahte LDAP (`ldap3` `MOCK_SYNC` sunucusu, ağsız) ve sahte OIDC sağlayıcısı (test-int'te küçük FastAPI, `fake-llm` deseni; JWKS + token ucu), yetki matrisi `user_*` sütunları, e2e: OIDC ile giriş → yalnız `/chat`, konsol rotası yönlendirir; içe aktarma ön rapor → uygula.

## Kabul kriterleri

- Dizindeki bir kullanıcı ilk girişte açılır (`auth_source=ldap`), grup eşlemesine göre projeye `user/read` üyeliği alır, `/chat`'te yayımlanmış agent'ları görür; konsol rotası 403/yönlendirme.
- Kullanıcı dizindeki gruptan çıkarılınca sonraki girişte üyeliği düşer; elle verilen üyelik kalır. Dizinde pasifleştirilen kullanıcı `identity_sync` sonrası giremez ve açık oturumu düşer.
- Dizin erişilemezken giriş 503 `identity_provider_unavailable`; yerel kullanıcıya sessiz düşüş yok; süperadmin yerel girişi `LOCAL_LOGIN=off` iken de çalışır.
- OIDC: sahte sağlayıcıyla tam akış; bozuk `state`, yanlış `nonce`, süresi geçmiş ya da yanlış `aud` id_token 400 kodlu ret; `alg=none` red; geri dönüş adresi dışı 400.
- `airgap` profilinde dış OIDC issuer kayıt anında red; `llmaas`'ta issuer egress izin listesinde değilse preflight uyarısı ve çağrı `EgressDenied`.
- Eşlenmemiş grup üyesi girer ama hiçbir projede üye değildir (varsayılan proje tanımlı değilse); eşlemeler ekrandan değişince sonraki girişte uygulanır.
- CSV içe aktarma: hatalı satır bütün dosyayı durdurmaz, ön raporda satır numarasıyla görünür; geçici parola bir kez döner, audit'te yoktur; `must_change_password` ilk girişte parola ekranına zorlar.
- 15 için: `resolve_external_identity` e-posta ile platform kullanıcısını bulur; bulunamayınca `None` (ret 15'te); `AUTO_PROVISION_FROM_CHANNELS` kapalıyken hesap açılmaz.
- Yetki matrisi `user_edit`/`user_read` dâhil bütün sütunlarda yeşil; `user` rolü `/memories` kendi verisine erişir, başkasınınkine 403.
- Kimlik bilgileri (bind parolası, client secret) hiçbir API cevabında ve logda yok (tarama testi).

## Teknik notlar

- Kütüphaneler: `ldap3` (saf Python, `MOCK_SYNC` test sunucusu), OIDC için `authlib` ya da `PyJWT` + httpx (JWKS); 80/20: tam bir OIDC istemci çerçevesi değil, authorization code + PKCE + id_token doğrulaması yeter. Yeni bağımlılıklar pinli, `deploy/offline/` manifestine (12).
- Oturum modeli değişmez: dış kimlik yalnız girişte çözülür, sonrası platformun çerezi (C6 aynı origin kuralı). IdP `refresh_token` saklanmaz (veri sınırı: platform IdP'ye yalnız girişte gider).
- Grup eşlemesi veritabanında, sağlayıcı yapılandırması `.env`'de: eşleme sık değişir ve projeye özgüdür; sağlayıcı bilgisi secret taşır ve kurulum başına birdir.
- `user` rolü `require_role` sırasında zaten en altta; aktivasyon yetki matrisini değiştirmez, yalnız atanabilirliği açar (plan/03 "sonradan migration ve yetki matrisi değişikliği gerekmez" taahhüdü tutar).
- Entra ID: grup claim'i boyut sınırında `groups` yerine `_claim_names` döner; brief kapsamında yalnız düz `groups` claim'i, taşma durumunda açık hata `groups_claim_overflow` (sessiz boş grup yok); Graph ile grup çekme kapsam dışı (ileride).
- Çok kiracılı yapı yok (PLAN kapsam dışı): tek kurulum = tek kurum; `identity_group_mappings.project_id` ile proje ayrımı yeter.

## Kapsam dışı

SAML, SCIM provisioning, MFA (IdP'nin işi), kullanıcı self-signup, proje başına farklı IdP, Entra Graph ile grup çözümü, IdP token'ıyla dış API çağrısı (OBO), parola politikası motoru (yerel kullanıcı için 03a kuralı sürer).
