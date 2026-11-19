# Arşiv: inceleyici · 10c-2

Salt okunur; mesajlar ve ID'ler değişmeden taşındı (MULTI_AGENT_PROTOCOL 'Bağlam bütçesi ve arşiv'). Taşıma: 2026-11-19, koordinatör.

### R-10C2-0001 · 2026-11-17 16:02 · → koordinator · ACK
Paket: 10c-2 · Cevap: K-10C2-0005, K-05B-0009
REVIEW-ISTEK alındı; lease ffcore-inceleyici-10c2. 05b r2 delta turu geldiğinde geçici olarak oraya dönülecek. SHA 5c27543 için tam tur. `ffcore-rv10c2` yığını e2e profiliyle açılacak (`--pull never`, `--no-build`); önce YIGIN-AC yazılacak. Rapor `state/reviews/10c-2-r1.md`; sonuç bu kanalda.

### R-10C2-0002 · 2026-11-17 16:06 · → koordinator · YIGIN-AC
Paket: 10c-2 · Cevap: K-10C2-0005 · Yigin: ffcore-rv10c2
Kaynak, SHA 5c27543'ün `git archive` kopyası (scratchpad `rv10c2_src`); e2e ekran görüntüleri ve `.next` worktree'ye yazılmasın diye. Yığın: `docker compose -p ffcore-rv10c2 --env-file .env.test --profile test up -d --wait --no-build --pull never`, `FFCORE_VERSION=0.0.0-10c2` (işçinin derlediği backend imajı; dalın son backend kod commit'i be415a7 imajdan önce). Portlar `BACKEND_PORT=18520`, `FRONTEND_PORT=13520`. e2e için node_modules, `ffcore-10a-nm`'den `ffcore-rv10c2_e2e_node_modules` adlı volume'a kopyalanacak (`npm ci` yok). Sırayla koşacaklar: backend lint/test iki profil, hedefli test-int, önyüz kapısı, tam e2e. Açık yığın yalnız bu. Bitince `down -v`, volume adıyla silinip YIGIN-KAPA.

### R-10C2-0003 · 2026-11-18 15:39 · → koordinator · YIGIN-AC
Paket: 10c-2 · Cevap: K-GEN-0024 · Yigin: ffcore-rv10c2
rv10c2 temiz açılıyor; kaynak SHA 5c27543'ün `git archive` kopyası. Komut: `--profile test --profile qdrant up -d --wait --no-build --pull never`, `frontend` servisi hariç. Önceki kapı sonuçları geçerli (e2e 180/180, backend 1813×2, önyüz), yeniden koşulmuyor. Koşacaklar: `make test-int` (qdrant ile) ve backend probe'ları. Probe odakları: 185 items ucu, anahtar, kota ve retention rolleri. Açık FF yığını yalnız bu.

### R-10C2-0004 · 2026-11-18 16:04 · → koordinator · REVIEW-SONUC
Paket: 10c-2 · Cevap: K-10C2-0005 · SHA: 5c27543683bf11b94dc433b4ceb498bd9c654953 · Sonuc: ONAY · Bulgu: B0 M0 m0 N3
10c-2 r1 ONAY. Rapor `state/reviews/10c-2-r1.md`.
- Kapı: backend 1813×2; önyüz 250/250; e2e 180/180; test-int (qdrant ile) 957 passed, 13 skipped.
- 185 items ucu probe'larla doğrulandı: sıralama, filtre, sayfalama, rol (user 403, analyst+ 200), silinmiş sınav 404.
- Karar gerektirebilecek tek nokta **NOTE-2 `kismi-ozet-500`**. Eksik anahtarlı bir `summary` satırı, sınav detayını ve suite koşu listesini 500'e düşürüyor. Normal akışta bu satır oluşmaz. Ama canlı test verisinde eski biçimli (312954e öncesi) bir özet varsa liste kırılır; merge öncesi kontrol önerilir.
- NOTE-1: koşu sayfası 403'te yoklamayı sürdürüyor.
Bekleyen dosyalar (commit edilmedi): `state/reviews/10c-2-r1.md`, `state/evidence/10c-2-r1-rv-*.log` (up2, test-int, probe yeni ya da güncellendi), kanal.

### R-10C2-0005 · 2026-11-18 16:04 · → koordinator · YIGIN-KAPA
Paket: 10c-2 · Cevap: K-10C2-0005 · Yigin: ffcore-rv10c2
`down -v` tamam; rv10c2 konteyner ve volume'u kalmadı (e2e node_modules volume'u sabahki temizlikte silinmişti). Açık FF yığınım yok. Sıradaki iş: 05b r3 teyiti (P9 tekrarı ve çift kodlama, K-05B-0013); SHA bekleniyor.

### R-10C2-0006 · 2026-11-18 17:43 · → koordinator · YIGIN-AC
Paket: 10c-2 · Cevap: K-10C2-0008 · Yigin: ffcore-rv10c2
r2 teyidi (SHA 877cc34) başlıyor. Kaynak, 877cc34'ün `git archive` kopyası (scratchpad `rv10c2r2_src`).
- **Hafif yığın:** yalnız `postgres redis`, `--no-build --pull never`, `FFCORE_VERSION=0.0.0-10c2`.
- **Migration:** yerel backend imajı 17 Kasım'dan, yani 05b migration'ı ondan sonra main'e girdi. Bu yüzden imajdaki `migrate` servisi kullanılmıyor; `alembic upgrade head` tools içinde kaynaktan koşuyor.
- **Koşacaklar:** NOTE-2 probe'ları (S1 dolu özetin JSONB gidiş-dönüşü ve tamsayı eşik; S2 R4 verisi; S3 tuhaf biçimler), backend lint ve hedefli 10c-2/09 testleri iki profilde, önyüz `check:api`.

Açık FF yığını yalnız bu. Sonuç R-10C2-0007'de.

### R-10C2-0007 · 2026-11-19 12:40 · → koordinator · DURUM
Paket: 10c-2 · Cevap: K-10C2-0008 · Durum: ACTIVE
Dün 17:43'te başlayan r2 teyidi oturum kapanınca yarıda kaldı. Hafif rv10c2 yığını (postgres, redis) ayakta; DB `05b_0001 (head)`. Kısmi sonuçlar:
- **NOTE-2 probe'ları tamam** (`10c-2-r2-rv-probe.log`, üç koşu). İkinci ve üçüncü koşular, kendi probe hatalarımın düzeltmesi.
  - Gerçek `summarize()` çıktısı JSONB gidiş-dönüşünden sonra detayda ve listede null olmadan geliyor ve log yazılmıyor: tamsayı eşik 1 ve 0, gecikme yok, fazladan anahtar.
  - R4 verisi, `{}`, dizi, string, `false` ve tamsayı yerine float → 200, `summary: null`, `eval_summary_invalid` logu.
  - **Bir boşluk kaldı:** özet çıplak bir sayıysa (`3`) hâlâ 500. Neden `eval.py:119` `set(row.summary or {})`. Bu satır suite listesini de düşürüyor. Raporda MINOR olarak yer alacak.
- Kaldı: backend lint ve hedefli testler iki profilde (llmaas yarıda kesildi), önyüz kapısı (check:api).

Ağır test başlatmama notun alındı. Kalan koşular hafif (hedefli pytest ve node kapısı), ama ffmain'deki imaj doğrulaması bitene kadar bekliyorum. "Bitti" mesajın gelince ya da 15 dk sonra kaldığım yerden sürdüreceğim.

### R-10C2-0008 · 2026-11-19 12:52 · → koordinator · REVIEW-SONUC
Paket: 10c-2 · Cevap: K-10C2-0008 · SHA: 877cc34f7911e9981a6d83c2b02a578e3ddc66fe · Sonuc: ONAY · Bulgu: B0 M0 m1 N2
10c-2 r2 teyidi ONAY. Rapor `state/reviews/10c-2-r2.md`.
- **NOTE-2 kapandı.** R4 verisinde detay ve suite listesi 200 dönüyor, özet `null`, `eval_summary_invalid` logu yazılıyor. Katı doğrulama gerçek özeti bozmuyor: dolu `summarize()` çıktısı JSONB'den null olmadan geliyor. Tamsayı eşik 1 ve 0, gecikme yok ve fazladan anahtar varyantları denendi.
- **Rebase:** yalnız `degisiklikler.md` commit'i değişti (range-diff); r1 bulguları aynı.
- **MINOR-1 `ozet-skaler-500`:** özet çıplak bir sayıysa (ya da `true`) detay ve suite listesi hâlâ 500. Neden `eval.py:119` `set(row.summary or {})`. Olasılık düşük, düzeltme tek satır (`isinstance(dict)`).
- NOTE-1: geçersiz özet logu her okumada tekrarlanıyor.
- NOTE-2: `degisiklikler.md` null davranışını yazmıyor.
- **Koşular:** lint ve hedefli pytest 83/83 (llmaas) ve 83/83 (airgap); önyüz lint, typecheck ve check:api 0, Vitest 250/250.
Bekleyen dosyalar (commit edilmedi): `state/reviews/10c-2-r2.md`, `state/evidence/10c-2-r2-rv-*.log`, kanal.

### R-10C2-0009 · 2026-11-19 12:52 · → koordinator · YIGIN-KAPA
Paket: 10c-2 · Cevap: K-10C2-0008 · Yigin: ffcore-rv10c2
`down -v` tamam; rv10c2 konteyner ve volume'u kalmadı. Açık yığınım yok.
