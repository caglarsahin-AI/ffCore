# PR hook-egress-1 [B]: hook block geçişi + FOLLOWUP-208/210/212/213

Durum: PLANNED (B-HKE-0002), PLAN-ONAY bekleniyor. Dal `fix/hook-egress-1`, baz main 1c0abcd.

## Plan

### Felsefe kontrolü
1. ARCH-07: hook düzeltmeleri bütün oturumlara (block'ta her Bash çağrısı); 208 backend'in dört dış çağrı ailesini (uzak MCP, OpenAPI araçları, webhook, dış agent) egress profilinde çalışır kılar. Çekirdeğe eklenen: tek ayar + proxy taşıyıcısı (egress.py içinde, tek yer).
2. ARCH-09: proxy işini Squid yapar (izin listesi, adres reddi, log); backend yeniden inşa etmez. httpcore'un kendi proxy taşıyıcısı (CONNECT tüneli) kullanılır, el yazımı CONNECT yok.
3. ARCH-10/06: `EGRESS_PROXY_URL` açık ayar (boş = bugünkü doğrudan pinli yol); proxy'de hata açık `EgressRequestFailed`/`EgressDenied`, doğrudan yola sessiz düşüş yok.

### Bulunan semboller
- `.claude/hooks/ffcore_guard.py`: `check_bash` (KAPI ve PROSES-175 heredoc gövdesini de komut sanıyor), `strip_heredocs` (yalnız ENV yolunda kullanılıyor), `check_compose` (yalnız compose), `check_write` (`pr` eşleşmesi tam ad), `resolve_mode`.
- `tests/hooks/test_guard.py::test_settings_command_runs_guard` (settings komutunu olduğu gibi koşuyor).
- `backend/ffcore/core/egress.py`: `_PinnedBackend.connect_tcp`, `_PinnedTransport`, `SafeOutboundClient`, `policy_http_client`, `check_http_destination`, `check_destination` (SMTP).
- `deploy/postgres/initdb/20-app-role.sh` (kaynaklanabilir, `exit` yok → `false`), `scripts/compose_preflight.py` (`db_role_incomplete`, `db_role_owner`), `.env.example` APP_DB yorumu.
- `deploy/docker-compose.egress.yml`, `deploy/egress/squid.conf`, `backend/tests/integration/test_12_egress.py` (uygulama ağında dış ad çözülmüyor: `test_12_e1_outside_names_do_not_resolve_on_the_app_network`).

### hook-guard.log incelemesi (98 satır, 16-20 Kasım, warn)
| Kural | Sayı | Sınıf |
|---|---|---|
| KAPI | 65 | ≥20 heredoc gövdesi (`cat >> state/kanal/… <<EOF`, `python - <<EOF` belge düzenleme; gövdede `make test`/`pytest` satırı) = **yanlış pozitif, kök neden**: `check_bash` gövde satırlarını komut olarak bölüyor (yeniden üretildi). ~7 görünür gerçek `pytest … \| tail` (tee'siz) = kurala göre doğru pozitif (S7). Kalan 38 satır 120 karaktere kesik; sınıflanamıyor (çoğu inceleyici/işçi `S=…; cd …` zinciri). |
| ENV | 23 | 16 Kasım'dakiler 189(e) öncesi; 19-20 Kasım 3 satır `python - <<EOF` kod gövdesinde metin `.env` = kararla kabul edilmiş YP (MINOR-2, FN yönü). |
| PROSES-175 | 5 | 4'ü heredoc gövdesi (kanal YIGIN-AC metni, belge düzenleme) = YP, KAPI ile aynı kök neden; 1'i gerçek. |
| TEK-YAZAR | 3 | `state/pr/04b-2.md`, `state/pr/followup-triage-1.md`: kayıttaki paket/pr adı ile alt PR dosya adı uyuşmuyor = YP (block'ta işçi kendi PR notunu yazamaz). |
| YIGIN, PAYCORE | 1+1 | gerçek / inceleme probu. |

### Dilim sırası (her dilim önce kırmızı test; test/kod/docs ayrı commit)
1. **212**: `test_settings_command_runs_guard` `shutil.which("py")` yoksa `pytest.skip("py launcher yok (Linux konteyner); kapı hook adımı host py -3.12, FOLLOWUP-212")`; handbook ENVIRONMENT_AND_COMMANDS hook satırı "kapı hook adımı host".
2. **210**: `check_compose` yanında `docker build` / `docker buildx build` / `docker image build` (+ `docker builder build`) → PROSES-175; `docker buildx ls`, `docker build --help` vb. serbest.
3. **Block öncesi daraltma** (öneri A, aşağıda) + TEK-YAZAR alt PR adı.
4. **Block**: `.claude/settings.json` `FFCORE_GUARD_MODE=block` ayrı commit; testler block kipinde: gerçek ihlal çıkış 2, bilinen YP fikstürleri sessiz (çıkış 0, kayıt satırı yok).
5. **213**: initdb yalnız-parola → stderr + `false`; `.env.example` yorumu ve `db_role_owner` mesajı (kullanıcı da boş olabilir: "set APP_DB_USER=ffcore_app and APP_DB_PASSWORD"); preflight testi + initdb için kabuk testi (host'ta `sh` yoksa tools konteynerinde).
6. **208** (öneri A, aşağıda): birim testleri (sahte proxy, httpcore2 sahte backend) + test-int Squid.

### Karar 1: KAPI daraltması
- **A (Önerilen):** KAPI ve PROSES-175 (bütün komut kuralları) `strip_heredocs` sonrası metne bakar: veri heredoc'u (`cat > f <<EOF`) ve yorumlayıcı kodu (`python - <<EOF`) komut sayılmaz; `sh`/`bash` gövdesi komut kalır. ENV bugünkü gibi kod gövdesini tarar (karar MINOR-2). Gerçek `make test` / `pytest` (tee'siz, `\| tail` dahil) block'ta engellenir: S7 kararı korunur. Etki: kök neden kapanır, kural gevşemez; YP sınıfı ≥20+4 susar.
- B: A + `state/kanal/` ya da `state/pr/` hedefli komutların tamamı muaf. Bedel: aynı zincirdeki gerçek kapı da geçer (muafiyet hedefe değil komuta bağlı olmalı) → fail-loud ihlali.
- C: KAPI yalnız `make <hedef>`; çıplak `pytest` serbest. Bedel: 16 Kasım S7 kararını tersine çevirir; hedefli koşu çıktıları kaybolur (K-05a-0011 dersi).
- Ek (A ile): TEK-YAZAR `state/pr/<ad>.md` için `<pr>` ya da `<pr>-<n>` / `<paket>-<n>` (alt PR) kabul; kayıt satırı 120 karakter kalır (değiştirmiyorum).
- Bilinen etki: block'ta herkes hedefli `pytest … | tail` yerine `… 2>&1 | tee state/evidence/<x>.log | tail` yazmalı; geçişten önce `tumu`'ya duyuru önerisi (koordinatör).

### Karar 2: 208 tasarımı
Gerçek: egress profilinde uygulama ağı `internal`, dış adlar backend'de **çözülmüyor** (test_12 e1). Backend tarafında çözümleme + IP pinleme proxy ile birlikte yapılamaz.
- **A (Önerilen):** `EGRESS_PROXY_URL` doluyken **iç olmayan** hedefler httpcore2 proxy taşıyıcısıyla çıkar (https → `CONNECT host:port`, http → mutlak biçim); backend proxy'den önce bütün **ad düzeyi** kuralları uygular (şema, port, OFFLINE, EGRESS_ALLOWLIST, platform hedefi, yönlendirme başına tekrar, kimlik başlığı düşürme), **adres düzeyi** denetimi (özel IP / DNS rebinding) çözümleyen ve bağlanan bileşene, Squid'e geçer (`to_private`, 12-1 r1 NOTE-3 ile `is_global` hizalı; fark: belge aralıkları, squid.conf'ta yazılı). TLS uçtan uca (SNI/sertifika backend'de). Proxy bağlantısının kendisi yalnız `EGRESS_PROXY_URL` köküne pinli (başka iç host'a değil). `ALLOWED_INTERNAL_HOSTS` hedefleri bugünkü doğrudan pinli yoldan. `policy_http_client` (MCP SDK) aynı seçimi kullanır. SMTP (`check_destination`) proxy'lenemez → egress profilinde bağlantı hatası, docs'ta açık. Etki: kanal/kaynak/uzak MCP/webhook egress profilinde çalışır; pinleme sınırı belgelenir.
- B: backend ad çözer + denetler, sonra `CONNECT host` (ad) gönderir. Bedel: internal ağda ad çözülmüyor (çalışmaz); çözülse bile Squid ikinci kez çözer → denetim/bağlantı ayrışır (rebinding açığı), sahte güvence.
- C: backend çözer, `CONNECT <ip>:port` (IP) + SNI ad. Bedel: aynı DNS engeli; Squid `dstdomain` izin listesi IP görür ve işlevsiz kalır (ikinci savunma hattı kaybolur).
- Not: A'da ayar boşken davranış bire bir bugünkü (regresyon testi). `EGRESS_PROXY_URL` yalnız `http://host:port` (kimlik, yol, https proxy yok → açılışta açık hata).

### Test-int (208)
`backend/tests/integration/test_12_egress.py` ek testler (RUN_EGRESS_TESTS=1, aynı yığın tarifi + backend'e `EGRESS_PROXY_URL=http://egress-proxy:3128`): SafeOutboundClient ile izinli alan 200 (proxy erişim logunda satır), izin listesi dışı backend'de `egress_not_allowlisted` (proxy'ye gitmeden), Squid reddi (rebind/bench) `EgressDenied`/403 açık hata, `EGRESS_PROXY_URL` boş istemciyle doğrudan çıkış bağlantı hatası. Yığın `ffcore-hke` (18880/13880), hedefli (ENV-209: tam test-int için sıra istenecek).
