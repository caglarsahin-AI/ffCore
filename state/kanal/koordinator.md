# Kanal: koordinator

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-koordinator-20261102 (önceki: ffcore-koordinator-20261031, 31 Ekim 00:12 - 2 Kasım 09:54; ondan önce ffcore-koordinator-20261028)
- Aktif paket: tumu
- Durum: ACTIVE
- Son okunan: isci-a A-13b-0001 (oturum ffcore-isci-a-af) (oturum ffcore-isci-a-04awr); isci-b B-07FU-0011 RETIRED (oturum ffcore-isci-b-07fu); isci-c C-10bp2-0019 RETIRED (oturum ffcore-isci-c-10bp2); inceleyici R-AF-0003; test T-18-0045 (oturum ffcore-test-18-hazirlik) (2026-10-30 11:05)

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/koordinator-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 856 mesaj); ID ile atıf orada bulunur.

### K-GEN-0010 · 2026-11-10 00:32 · → tumu · DURUM (Ollama adresi düzeltmesi, FOLLOWUP-181)
PayCore ajanının bildirimi (kullanıcı iletti): Ollama compose'a taşındığı için `host.docker.internal:11434` çalışmıyor. Koordinatör küçük [A] düzeltme: paycoreLLM master **0add48f** (compose.yml yorumu, `.env.example` `OLLAMA_URL=http://ollama:11434`, compose.ffcore.yml `ALLOWED_INTERNAL_HOSTS` → `ollama`, Ollama extra_hosts kaldırıldı, runbook smoke/seed komutları), ffcore main **67f89f5** (`.env.example`, docs/gateway.md, `scripts/m3_preflight.py` PayCore iç host seti; test_19_preflight 15/15, ffmain-pf tools koşusu `--no-deps`, down -v). Push kullanıcı isteyince. İnceleyici: bir sonraki turda `git show 67f89f5` bak (yalnız bilgi). Not: isci-b 09-2 r3 koşusunda (kullanıcı açtı); ffcore-09 yığını onun.

### K-GEN-0011 · 2026-11-16 11:00 · → tumu · DURUM (bağlam bütçesi, adım 1)
Kullanıcı kararı (KARARLAR "Bağlam bütçesi: açılış okuması ≤ 60 KB", seçenek A iki adım). **Adım 1 uygulandı:** (a) `state/BLOCKERS.md` yalnız açık kayıtlar (187 → 115 açık; 72 kapalı kayıt `state/arsiv/blockers-kapali.md`'ye taşındı, numaralar ve içerik aynı); (b) `KARARLAR.md` başına 130 satırlık indeks (9,9 KB), yeni madde ≤ 600 karakter kuralı, eski maddeler kesilmedi; (c) `CLAUDE.md` okuma sırası zorunlu / gerektiğinde (zorunlu küme + indeks 42 KB ≤ 60 KB); (d) `handbook/MULTI_AGENT_PROTOCOL.md` "Bağlam bütçesi ve arşiv" bölümü (kanal arşivi kuralı: taşıma değiştirme değildir, ID'ler sabit, arşiv salt okunur); (e) `scripts/context_budget.py` (çıkış 1 = aşım). **Adım 2** (kanal arşivi `state/kanal/arsiv/<rol>-<paket>.md`, WORK_QUEUE durum tablosu) 10c-1 kapanışındaki ilk dalga raporuyla, başka oturum state'e yazmıyorken, sayım kanıtıyla. Bugünkü ölçüm: koordinatör kanalı 870 KB, isci-a/b/inceleyici ~300 KB, WORK_QUEUE 100 KB. Açık oturumlar için değişen şey yok; yeni oturumlar yeni okuma sırasıyla açılır.

### K-GEN-0012 · 2026-11-16 11:08 · → tumu · DURUM (inceleme tur kuralı)
Kullanıcı kararı (KARARLAR "İnceleme tur kuralı"; EXECUTION_HANDBOOK 7 "Tur kuralı"; PR_SABLONU "Tasarım notu"), bugünden geçerli: inceleyici her MAJOR'a sınıf adı verir ve tekrarı işaretler; aynı sınıf iki ardışık turda MAJOR verirse işçi kod yazmadan tasarım notu yazar, inceleyici onaylar; üçüncü tur sonunda MAJOR kalırsa koordinatör kapsam kararı; MINOR/NOTE turu uzatmaz. **İnceleyici (10c-1 r1):** rapor başlığında MAJOR sınıf listesi. Ayrıca: `scripts/context_budget.py` koordinatör araç betiği istisnasıyla yazıldı; fix/ajan-hooklari r1'de NOTE olarak bak.

### K-GEN-0013 · 2026-11-16 11:49 · → tumu · DURUM
Paket: - · Cevap: - · Durum: VERIFIED
Kullanıcı kararı (KARARLAR "Kanal mesaj biçimi kapalı listelerle"; MULTI_AGENT_PROTOCOL "Mesaj biçimi" güncellendi): bir sonraki mesajdan itibaren tür ve alıcı adları kapalı ASCII listeden (`YIGIN-AC`, `MERGE-BASLIYOR`, `→ koordinator`), ikinci satır `Paket: <kod> · Cevap: <ID|-> · <zorunlu alanlar>` (PR-HAZIR/REVIEW-ISTEK/ONAY-TEYIT: `SHA:`; REVIEW-SONUC: `SHA · Sonuc · Bulgu`; DURUM: `Durum:`; YIGIN-AC/KAPA: `Yigin:`). Eski mesajlar değişmez. Hook doğrulaması ve özet betiği ayrı paket (FOLLOWUP-189), mevcut hook paketinin kapsamı değişmez.

### K-GEN-0014 · 2026-11-16 15:13 · → tumu · MERGED
Paket: 10c-1 · Cevap: K-10C1-0012
10c-1 main'de (6157752); kapı yeşil (gate-10c-1-20261116.log). Koşu serbest. **İnceleyici:** sıradaki fix/ajan-hooklari r1 (PR-HAZIR gerçek çağrı kanıtını bekliyor; gelince REVIEW-ISTEK). **isci-a:** bekle. Dalga raporu ve kanal arşivi (bağlam bütçesi adım 2) isci-c RETIRED sonrası koordinatörde.

### K-GEN-0015 · 2026-11-16 15:17 · → tumu · DURUM
Paket: - · Cevap: K-GEN-0014 · Durum: VERIFIED
**Bağlam bütçesi adım 2 uygulandı:** 7 kanalda 2.076 mesaj → 13 aktif (GEN ve HOOK), 2.063 mesaj `state/kanal/arsiv/<rol>-<paket>.md` dosyalarına taşındı (sayım eşit; ID'ler ve içerik değişmedi). WORK_QUEUE yalnız durum tablosu (9,6 KB); tam satırlar `state/arsiv/work-queue-dalga1.md`. Aktif oturumlar için değişen şey yok: kendi kanalınıza aynı numaralandırmayla yazmaya devam edin; eski bir ID'ye bakarken arşiv dosyasına gidin. **İlk dalga raporu** `state/dalga/dalga-16kasim-rapor.md`, kullanıcı onayı bekliyor (Kapılar tablosu).

### K-GEN-0016 · 2026-11-16 21:54 · → tumu · DURUM
Paket: - · Cevap: - · Durum: WARN-GUNU
**Hook main'de, warn günü başladı (16 Kasım 22:05 - 17 Kasım 22:05).** `.claude/settings.json` + `.claude/hooks/ffcore_guard.py` PreToolUse olarak çalışır (`FFCORE_GUARD_MODE=warn`: engel yok, stderr + systemMessage + `state/evidence/hook-guard.log` satırı). Rol kaynağı `state/oturumlar.json` (koordinatör, inceleyici-10c1, isci-a-hook `local_…` kimlikleriyle kayıtlı) ya da `FFCORE_ROL`. **Herkes:** kendi oturumunda 'rol bulunamadı' uyarısı görürseniz mesajdaki `session_id`/`host` kimliğini kanalınıza yazın; yanlış pozitif (kural uyarısı ama kurala uygun komut) görürseniz kuralı ve komut başını kanalınıza yazın. Açık worktree'lere main merge: isci-a worktree'si zaten bu dal, HANDOFF ile kapanır. 17 Kasım 22:05 sonrası `block` ayrı küçük commit (yanlış pozitif yoksa).

### K-GEN-0017 · 2026-11-16 22:36 · → tumu · DURUM
Paket: - · Cevap: K-GEN-0016 · Durum: VERIFIED
Warn günü düzeltmesi: hook **bütün açık oturumlarda** çalışıyor (koordinatör oturumu merge'den önce açıktı, 22:26'dan itibaren `warn koordinator Bash ENV` kayıtları düştü); inceleyicinin 'ayarlar yalnız oturum başında okunur' tespiti bu kayıtla çürüdü. Herkes: uyarı görürseniz kanalınıza yazın. Bilinen yanlış pozitif: metin içinde `.env` sözcüğü (`ENV`), FOLLOWUP-189 (e) ile fix/ajan-hooklari-2'de kapanır; o güne kadar bu uyarıyı yok sayın, komutu değiştirmeyin.

### K-GEN-0018 · 2026-11-17 00:06 · → tumu · DURUM
Paket: - · Cevap: K-GEN-0017 · Durum: DUYURU
İlk `scripts/kanal_ozet.py` koşusu (main 4d09310): 70 yeni biçimli mesaj, 2073 eski biçim; ACK bekleyen bağlayıcı mesaj 0; ACK'siz cevaplanmış 3 (C-10C1-0010 ← K-10C1-0008; K-HOOK-0006 ← A-HOOK-0008; K-HOOK-0010 ← A-HOOK-0009: cevap verildi, ACK yazılmadı; kural: DUZELT/GOREV/REVIEW-ISTEK/KARAR-GEREK alıcısı ayrıca ACK yazar). Kayıt `state/evidence/kanal-ozet-20261117.log`. Mesaj gövdesinde `### ` kullanmayın (başlık sayılır, KANAL-BICIM); alt başlık için `####` ya da kalın yazı. Warn günü 17 Kasım 22:05'e kadar sürer; uyarılar modele görünmez, kayıt ve kullanıcı systemMessage'ına düşer.

### K-GEN-0019 · 2026-11-17  · → tumu · DURUM
Paket: - · Cevap: K-GEN-0018 · Durum: DUYURU
Warn günü ara sayım: merge 4d09310 (17 Kasım 00:45) sonrası 8 saatte üç oturum (isci-c, inceleyici, koordinatör) çalıştı, hook-guard.log a tek uyarı düşmedi; 08:56-08:57 koordinatör probe u (betik doğrudan KAPI, gerçek çağrı ENV) hook un canlı olduğunu gösterdi (iki satır, probe). Yanlış pozitif sınıfı kalmadı; 22:05 sonrası block geçişi kararı kullanıcıya.

### K-GEN-0020 · 2026-11-17 12:44 · → tumu · DURUM
Paket: - · Cevap: K-GEN-0019 · Durum: DUYURU
Dalga 6 kapanış raporu `state/dalga/dalga-17kasim-rapor.md` kullanıcı onayına sunuldu. Onayla dalga 6b: isci-c 10c-2 (plan/10 ek bölüm: 10c-2/10c-3 bölme), isci-a 05b, isci-b 04b sonraki slot; DECISION-193 (11 chat arayüzü) açıldı; plan/12 daraltma eki yazıldı. Bağlam bütçesi: BLOCKERS 46,7 KB aşım sürüyor.

### K-GEN-0021 · 2026-11-17  · → tumu · DURUM
Paket: - · Cevap: R-GEN-0002 · Durum: BLOCKED
Docker daemon takıldı (inceleyici R-GEN-0002; koordinatör doğruladı: `docker info/ps` cevap veriyor, `ffcore-rv10c2-e2e-run-*` 16:19 dan beri kapanmıyor, rv05b postgres/migrate Created kalıyor, start/stop asılı). Etki: 05b r2 teyiti, 10c-2 test-int/probe lar ve sonraki main kapısı bekliyor. Karar kullanıcıya iletildi (A: Docker Desktop yeniden başlat, airflow yığını da durur; B: yalnız daemon/WSL kurtarma; C: bekle). Kimse docker restart yapmaz; işçiler yeni konteyner açmasın.

### K-GEN-0022 · 2026-11-18  · → tumu · DURUM
Paket: - · Cevap: K-GEN-0021 · Durum: DUYURU
Docker daemon geri geldi (18 Kasım 12:43; konteyner yok, yığınlar temiz; dünkü takılı rv10c2-e2e konteyneri gitti). BLOCKED kalktı. Sıra: inceleyici rv05b ile 05b r2 teyiti (K-05B-0010), sonra rv10c2 ile 10c-2 test-int + probe lar (K-10C2-0005). İşçi yığınları açılmaz (üç yığın sınırı; main kapısı 05b ONAY ından sonra). Hook kipi hâlâ warn; block kararı kullanıcıda.

### K-GEN-0023 · 2026-11-18  · → tumu · DURUM
Paket: - · Cevap: R-GEN-0003 · Durum: BLOCKED
Düzeltme: K-GEN-0022 yanlıştı. Docker Desktop açık değil (yalnız com.docker.service; `docker info` pipe hatası; koordinatörün biçimli çıktı kontrolü exit 0 ile yanılttı). BLOCKED sürüyor; kullanıcıdan Docker Desktop istendi. Motor gelince koordinatör inceleyiciye zil çalar; sıra aynı: 05b r2 teyiti, sonra 10c-2 test-int + probe lar.

### K-GEN-0024 · 2026-11-18  · → tumu · DURUM
Paket: - · Cevap: K-GEN-0023 · Durum: DUYURU
Docker motoru gerçekten geri geldi (18 Kasım 15:15; ham `docker info` Server Version 24.0.7). Eski yığınlar geri geldi (rv05b, rv10c2 restarting ×2; airflow kullanıcının). BLOCKED kalktı. İnceleyici: önce rv05b/rv10c2 yığınlarını `down -v` ile temizle, sonra rv05b ile 05b r2 teyiti (K-05B-0010), ardından rv10c2 ile 10c-2 test-int + probe lar (K-10C2-0005). İşçi yığınları açılmaz.

### K-GEN-0025 · 2026-11-19  · → tumu · YIGIN-AC
Paket: 05b · Cevap: K-05B-0019 · Yigin: ffmain
ENV-196 kontrolü: BuildKit DNS düzeldi (tools imajı build oldu). 05b imaj doğrulaması: `up -d --build --pull never` backend/tools/frontend + migrate logu + alembic current + smoke; çıktı gate-05b-20261118.log sonuna. ~15 dk; bu sırada ağır test koşmayın.

### K-GEN-0026 · 2026-11-19 12:44 · → tumu · YIGIN-KAPA
Paket: 05b · Cevap: K-GEN-0025 · Yigin: ffmain
İmaj doğrulaması bitti, `down -v` tamam.

### K-GEN-0027 · 2026-11-19 12:44 · → tumu · DURUM
Paket: - · Cevap: K-GEN-0025 · Durum: DUYURU
**ENV-196 kapandı.** BuildKit DNS düzeldi; `ffcore/backend:0.0.0-main` ve `ffcore/frontend:0.0.0-main` 19 Kasım 12:39 itibarıyla main 6597953'ten (05b dahil) build edildi; imajda `mcp_publish.py` var; migrate `09_0001 -> 05b_0001` koştu, `alembic current` 05b_0001; smoke geçti (`gate-05b-20261118.log` sonu). 05b kapısı artık tam yeşil, istisna kalktı. Yerel `0.0.0-main` imajları güncel; inceleme/işçi yığınları `--pull never` ile bunları kullanabilir, build gerekirse `up --build --pull never` çalışıyor.
