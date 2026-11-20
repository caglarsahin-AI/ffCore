# Review hook-egress-1 r2 · teyit turu (r1 MINOR-1 A, MINOR-2, NOTE-1/2/3)
SHA: 3da0bfb38bc37f41ef5be2fcd677f32b02c02f3c · Sonuc: ONAY · Bulgu: B0 M0 m0 N2

- **İncelenen tam SHA:** `3da0bfb38bc37f41ef5be2fcd677f32b02c02f3c` (dal `fix/hook-egress-1`).
- **Delta** `99bb7a3..3da0bfb`: 7 commit, 6 dosya, +221/−45.
  - test 9672f9e, 9c5d355, f5c4643
  - kod 2c26229, 3506f92, d5bcba3
  - docs 3da0bfb
- **İstek:** K-HKE-0007. Kararlar: K-HKE-0006 (MINOR-2 güvenlik regresyonu olarak merge öncesi; MINOR-1 A, yani yalnız mesaj; NOTE-1/2/3 aynı turda).
- **İşçinin ek bulgusu:** tırnaklı `sh -c` içindeki heredoc kapatıldı. r1 raporu `hook-egress-1-r1.md`.
- **Yöntem:**
  - Delta satır satır okundu.
  - Yığın açılmadı.
  - Hook: r1 probe partileri 1 ve 2 dalın guard'ıyla yeniden koşuldu. Yeni parti 3 ve 4: ENV mesajı, tırnaklı heredoc, tırnak izleme kenarları. Hepsi hostta `py -3.12`, block kipi, geçici kök. Karşılaştırma için main'in guard'ı ve r1'in (`99bb7a3`) guard'ı da koşuldu.
  - Egress birim testleri `tools:0.0.0-hke` konteynerinde, `--network none`, kaynak bağlı.
- **Karar: ONAY.** r1'in iki MINOR'u ve üç NOTE'u kapandı. Yeni iki NOTE eski, yani bu daldan önce de var olan konular; merge'ü bekletmez.

## Testler
`HEAD=` satırlı loglar `state/evidence/hook-egress-1-r2-rv-*.log`.

| Koşu | Sonuç |
|---|---|
| Probe 1, r1 partisi (`-hook-probe.log`) | 65 durum. Sapan 4 durum r1 MINOR-1'in ENV metin durumları; karar A gereği engel sürüyor, mesaj artık ayrı (aşağıda) |
| Probe 2, r1 partisi | 16/16 beklendiği gibi; r1'in beş sarmalayıcı biçimi artık engel |
| Probe 3, r2 | 19 durum, 18 beklendiği gibi. Tek sapma eski bir kör nokta (NOTE-1) |
| Probe 4/5 | yorum kesmesi r2, main ve r1'de aynı; `timeout 600 pytest` doğrudan komut olarak sessiz (NOTE-2) |
| Hook testleri host (`-tests.log`) | `tests/hooks tests/scripts` **432 passed** (r1'de 409) |
| ruff + egress birim (`-tests.log`) | ruff temiz; değişen dosyalarda format temiz. `test_hke_208_egress_proxy`, `test_03b_egress`, `test_hke_208_compose`: **84 passed** |

## Kontrol listesi (K-HKE-0007)

| # | Madde | Sonuç |
|---|---|---|
| 1 | **MINOR-2: beş sarmalayıcı biçimi** | `reader_command`, okuyucuyu sarmalayıcıların ardından buluyor: `env K=V`, `timeout [-s/-k değerli] N`, `docker compose run/exec … <servis>`, `docker exec [-e/-u/-w değerli] … <konteyner>`. Derinlik `MAX_NESTING` ile sınırlı. <br>Engellenenler (KAPI): `env X=1 bash`, `timeout 600 bash`, `timeout -s KILL 600 bash`, `compose run -T tools sh`, `compose run -e A=1 --rm -T tools sh`, `compose exec -T backend bash`, `docker exec -i c sh`, `docker exec -i -u root -w /w c bash`. <br>`compose run tools sh <<EOF` gövdesinde `docker build` → PROSES-175. <br>Sessiz kalanlar: `| tee`'li karşılıkları; `compose exec -T postgres psql <<EOF` (veri); `docker exec -i c python - <<EOF` gövdesinde `pytest` (kod). Kapandı. |
| 2 | **İşçi ek bulgusu: tırnak içi heredoc** | `unquoted_heredocs`, satırlar boyunca açık tırnağı izliyor. Tırnaklı `sh -c "…<<EOF…"` içindeki operatör iç kabuğa ait; iç kabuk `shell_inner` ile ayrıca denetleniyor. <br>• `sh -c "cat > f <<EOF … EOF\npytest -q"` → KAPI. <br>• Çok satırlı `sh -c '…<<EOF…EOF'` sonrasında dışarıdaki `pytest` → KAPI. <br>• `sh -c "cat >> k.md <<EOF\nmake test passed\nEOF"` → sessiz. <br>• `bash -c "bash <<EOF \| tee …"` → sessiz. <br>Kaçışlı kesme işareti (`it\'s`), çift tırnak içi kesme ve gövdesinde kesme olan kanal heredoc'u sonrası ikinci heredoc: sessiz. Main bunların üçünde yanlış pozitif veriyordu. |
| 3 | **MINOR-1 A: ENV mesajı** | Eşleşme değişmedi; probe 1'in dört metin durumu yine engel. `env_hits` artık türü döndürüyor; yol argümanı koddaki metne baskın. Kod gövdesi ya da `-c` metni için mesaj: "yorumlayıcı kodunda (heredoc gövdesi ya da -c) çıplak `.env` geçiyor; kod komut sayılır. Metin düzenlemesiyse dosyayı Write/Edit aracıyla yaz ya da betiği Write ile dosyaya koyup `py dosya.py` ile koş …". Gerçek yol (`cat .env`, `py -c "open('.env')"`, heredoc + `cat .env` birlikte) eski mesajı veriyor. Handbook satırı mesajı aktarıyor. Kapandı. |
| 4 | **NOTE-2: proxy reddi kodu** | `_ProxyOnlyBackend.connect_tcp` içinde `ConnectError`/`OSError` → `egress_proxy_unreachable`. Bağlantı zaman aşımı ayrı sınıf (`ConnectTimeout`), `egress_timeout` olarak kalıyor. <br>Yeni birim testi kapalı yerel portla http ve https için bu kodu sınıyor. Eski test `ConnectError` beklentisinden `egress_proxy_unreachable`'a gerekçeyle güncellendi; doğrudan yola düşüş yok (`dialed` yalnız proxy adresi). Kapandı. |
| 5 | **NOTE-1: docs/takim 648/654** | "ilk 240 karakteri (fix/hook-egress-1; önce 120)" ve `block` geçişinin tarihçesi yazılı; settings örneği `"block"`. Kapandı. |
| 6 | **NOTE-3: ayrık koşu örneği** | Handbook'a "Ayrık koşu" maddesi eklendi: `tee` konteynerdeki `sh -c` içinde, kanıt `docker logs -f "$cid" > state/evidence/…`. Bu turdan önce benim kullandığım desenle aynı. Kapandı. |

## Yeni notlar (merge'ü bekletmez)

### NOTE-1 · Kesme işaretli `#` yorumu sonraki satırları komut kurallarından saklıyor (eski)
- `# don't` gibi bir yorum satırından sonraki `pytest -q`, `git push` ve `docker build .` engellenmiyor. `echo hi # don't` sonrası da aynı.
- Yorumsuz biçim (`# dont`) engelleniyor. `cat .env` her durumda engelleniyor.
- Davranış main'de ve r1'de (`99bb7a3`) birebir aynı, yani bu dalın regresyonu değil (`-hook-probe.log` probe 4).
- Sebep: yorumdaki kesme işareti satır bölücüde tırnak açıyor ve kalan metin tek bir tırnaklı parça sayılıyor.
- Öneri, FOLLOWUP: `split_pipelines` / `unquoted_heredocs` tırnağın dışındaki `#`'ten satır sonuna kadar olan kısmı yorum diye atsın (kelime başındaki `#`); test: yorumdan sonra `pytest`, `git push`, `docker build` engel.

### NOTE-2 · Handbook'ta `timeout` cümlesi iki anlamlı
- Yeni cümle heredoc okuyucusunun `timeout N` ardından bulunduğunu söylüyor. Satır sonu ise hâlâ "`timeout`, `xargs`, `sudo` sarmalayıcıları … denetlenmez" diyor.
- İkisi de doğru: doğrudan `timeout 600 pytest -q` ve `timeout 600 make test` sessiz (probe 5). Ama okuyan çelişki sanabilir.
- Öneri: "doğrudan komut önündeki `timeout` denetlenmez (heredoc okuyucusu bulunur)". İsteğe bağlı olarak `unwrap`'e `timeout` eklenir; `reader_command`'daki atlama mantığı hazır.

## Bekleyen dosyalar (commit edilmedi)
- `state/reviews/hook-egress-1-r2.md`
- `state/evidence/hook-egress-1-r2-rv-{hook-probe,tests}.log`
- `state/kanal/inceleyici.md`
