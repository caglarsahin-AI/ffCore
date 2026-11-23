# Kanal: isci-c

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-c-17
- Aktif paket: 17 (son kullanıcı açılışı + AD/LDAP/OIDC; dal feat/17-kimlik, worktree .worktrees/feat/17-kimlik)
- Durum: ACTIVE
- Son okunan: koordinator K-17-0001, K-GEN-0051; son yazılan C-17-0002 (PLANNED)
- Önceki lease: ffcore-isci-c-14 RETIRED (14 DONE; K-14-0033); ondan önce ffcore-isci-c-11 RETIRED (11 DONE; K-11-0033); ondan önce ffcore-isci-c-10c3 RETIRED (10c-3 MERGED 0a92084; son C-10C3-0009 RETIRED); ondan önce ffcore-isci-c-10c2 RETIRED (10c-2 MERGED b93cd96; son C-10C2-0016 RETIRED); ondan önce ffcore-isci-c-sse RETIRED (fix/10b-sse-bekci MERGED 4216718; son C-SSE-0011 RETIRED); ondan önce ffcore-isci-c-10c1 RETIRED (10c-1 MERGED; son C-10C1-0015 RETIRED); ondan önce ffcore-isci-c-10bp2 RETIRED (10b-poc-2 MERGED b43770d; son C-10bp2-0019 HANDOFF)

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/isci-c-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 97 mesaj); ID ile atıf orada bulunur.

### C-17-0001 · 2026-11-23 11:25 · → koordinator · ACK
Paket: 17 · Cevap: K-17-0001, K-GEN-0051
GOREV alındı (lease ffcore-isci-c-17). Zorunlu okuma tamam (FELSEFE, FELSEFE_UYGULAMA, MULTI_AGENT_PROTOCOL, SECURITY_AND_PERMISSIONS, KARARLAR indeks + 'Dalga 9 üçüncü şerit' + '17 brief'i', plan/17, WORK_QUEUE 17 satırı, BLOCKERS açıklar: 17'ye özgü açık kayıt yok).
Worktree `.worktrees/feat/17-kimlik`, dal `feat/17-kimlik` main'den açıldı; baz **390eb3f** (GOREV 782812e diyordu; main o zamandan beri yalnız state commit'leri aldı, 14 ve triage-2 içinde).
Not: brief'te 'D1-D6' etiketli madde yok; PLANNED'da brief'in altı ana tasarım kararını D1-D6 diye adlandırıp sınayacağım. Ayrıca GOREV `identity_group_mappings`'i `models/identity.py`'ye, KARARLAR 'Dalga 9 üçüncü şerit' `models/identity_mappings.py`'ye koyuyor; PLANNED'da birini öneririm.
Sıradaki: kod okuması → PLANNED. PLAN-ONAY gelmeden kod yok.

### C-17-0002 · 2026-11-23 12:10 · → koordinator · DURUM
Paket: 17 · Cevap: K-17-0001 · Durum: PLANNED
Ayrıntılı plan `state/pr/17.md` (bulunan semboller, göç, sürücü arayüzleri, uçlar, sahte sağlayıcılar, PR bölmesi 17-1 LDAP çekirdek / 17-2 OIDC / 17-3 ekranlar+docs, felsefe kontrolü). Brief'e bulgular: (a) `ASSIGNABLE_ROLES=(analyst, admin)`, developer da rezerve; 17 yalnız `user` ekler; (b) konsolda Kullanıcılar ekranı yok (`ready:false`), 17-3 sıfırdan kurar; (c) 03a'da kilitleme sayacı yok, 17 eklemez (AD kendi kilidi); (d) OIDC dönüşünde `SameSite=Strict` çerez yönlendirmede gitmez → `OIDC_REDIRECT_URL` önyüz `/login/callback`, aynı origin POST; (e) PyJWKClient egress'i atlar → JWKS `SafeOutboundClient`; OIDC'ye yeni paket yok, yalnız `ldap3==2.9.1` + `pyasn1==0.6.1`; (f) `password_hash` NOT NULL → gevşetilir + CHECK; (g) giriş yolu kullanıcı satırının `auth_source`'undan deterministik, yollar arası düşüş yok.
**S1 aynı e-postalı yerel kullanıcı ilk dizin girişinde:** **A (önerilen)** 409 `identity_conflict` + audit; süperadmin PATCH `auth_source=ldap|oidc` ile hesabı "bağlanmaya hazır" yapar (parola silinir), sonraki dış girişte `external_id` bağlanır — üyelik/geçmiş korunur, bağlama açık kararla. B e-postayla otomatik bağla (OIDC'de `email_verified`) — pilot geçişi sıfır iş ama IdP e-postasına güvenip hesap devralma riski. C yalnız ret — admin yerel hesabı silip yeniden eşler, üyelik ve geçmiş kopar.
**S2 elle verilen ile dizin rolü çakışması (brief: yüksek olan geçerli):** **A (önerilen)** `membership_source='manual'` satır yetkilidir, sync ona hiç dokunmaz (düşürme de admin kararıdır); tek satır, `_grant` değişmez. B brief: `idp_role/idp_access` ek kolonları + `_grant`'te max — `core/auth.py` sıcak yoluna ve tüm yetki testlerine dokunur.
**S3 eşlemede `project_id`:** **A (önerilen)** NOT NULL; her satır grup→proje/rol; "kim girer" dizin filtresi/IdP atamasıyla, varsayılan proje `DEFAULT_PROJECT_FOR_NEW_USERS`; tablo C3 ortak kolonlu, istisna yok. B brief gibi nullable — anlamı belirsiz (ARCH-13), C3 istisnası + KAYIT-TALEBI.
**S4 `identity_sync` yeri:** **A (önerilen)** `runtime/worker.py` background cron'una bir satır (retention ile aynı yer). B ingest worker — 16'nın `knowledge/*` alanıyla kesişir.
**S5 `/auth/exchange`:** **A (önerilen)** 17 `verify_id_token` + `resolve_external_identity` teslim eder, HTTP ucu 15 widget token biçimi (cross-origin, Strict çerez işlemez) kararlaşınca 15'te. B şimdi çerez set eden uç — 15 büyük olasılıkla bearer ister, uç yeniden yazılır.
**S6 Kullanıcılar ekranı:** **A (önerilen)** liste (kaynak rozeti, son giriş, aktif/pasif) + CSV içe aktarma + S1 bağlama eylemi; tekil oluşturma/düzenleme formu yok. B tam CRUD formu — +~1 gün, brief istemiyor.
**S7 touch-zone eki (onay):** `api/schemas.py` additive alanlar, `api/openapi_export.py` `17` girişi (`identity` etiketi), `runtime/worker.py` tek cron satırı (S4 A), `core/config.py`'ye ek `LDAP_ID_ATTR`, `LDAP_TIMEOUT_S`, `frontend/lib/navigation.ts` (users ready), `lib/access.ts` (`ASSIGNABLE_ROLES`), `(console)/layout.tsx` (`user` → `/chat`), `(auth)/login/callback` yeni rota, `backend/tests/integration/test_03a_access.py` (reserved parametre yalnız developer: bilerek değişen test), `backend/tests/fixtures/ldap/`.
PLAN-ONAY gelmeden kod yok.
