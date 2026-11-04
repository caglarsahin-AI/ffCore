# PayCore 19 dış inceleme raporu, üçüncü tur (paycoreLLM master ba3056d)

- **Kaynak:** PayCore koordinatör oturumu; kullanıcı 4 Kasım 2026 ~21:20'de koordinatöre yapıştırdı (metin aynen aşağıda).
- **Kapsam:** fix/19r2-dis-inceleme merge'ü (ba3056d).
- **Karar:** yeni MAJOR yok; MINOR 1 (R12), NOTE 1 (R13). FFCore koordinatör triyajı: FOLLOWUP-169.

## Bulgular (aynen)

* R12 (MINOR, bu dalın kodunda değil): Testler deponun gerçek `.env`'ini okuyor.
   * Test konteyneri depoyu `/app`'e bağlıyor ve ayarlar `.env`'i oradan yüklüyor.
   * Ana checkout'ta `.env` var. İçeriğini okumadım, yalnızca varlığını kontrol ettim.
   * Sonuç: ana checkout'ta koşulunca 3 test daha "Langfuse yarım yapılandırılmış" hatasıyla kalıyor; aynı commit temiz kopyada geçiyor.
   * Bu, CLAUDE.md'deki "testler `.env` olmadan koşar" kuralına aykırı: `make test` gerçek secret'ları test sürecine yüklüyor.
   * Önerdiğim düzeltme: `conftest.py`'de testler için `.env` okumasını kapatmak.
* R13 (NOTE): Beş uydurma girdide `@login` maskelenmiyor; örneğin `SET @ahmet.yilmaz` ve boşluksuz `@ahmet.yilmaz(acil)`. Gerçek Jira metninde olasılıkları düşük. Düzeltme istemiyorum, runbook'taki bilinen sınırlar listesine eklenmesi yeterli.

## Triyaj (FFCore koordinatör, 4 Kasım 2026)

- R12 → FOLLOWUP-169 (küçük paycoreLLM dalı `fix/19r3-env-tests`): `tests/conftest.py` test sürecinde `.env` okumasını kapatır (örn. `Settings(_env_file=None)` ya da ortam değişkeni), test komutu/compose.test.yml temiz kopya davranışını ana checkout'ta da verir; kanıt: ana checkout'ta `make test` sonucu temiz kopyayla aynı. Secret test sürecine yüklenmez (SECURITY_AND_PERMISSIONS).
- R13 → aynı dalda runbook "bilinen sınırlar" listesine iki yazım (`SET @login` büyük harfli SQL istisnası, boşluksuz `@login(` çağrı biçimi); kod değişikliği yok (K-19R2 kararlarıyla tutarlı).
- FOLLOWUP-167 (stager `text_filter` iletimi) aynı dalda ele alınabilir; koordinatör oturum açılırken karar verir.
