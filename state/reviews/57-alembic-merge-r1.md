# fix/57-alembic-merge · review r1

**Tam SHA:** 5dbf11ec1eae40003b108cee09fc768943bdee0b (baz 148eadd, 1 commit, 14 dosya; `state/` diff'i 0) · **Tarih:** 2026-11-01 06:13 · **Karar: ONAY** · BLOCKER 0 · MAJOR 0 · MINOR 1. Yığın review57 (Postgres + tam test profili), `down -v` ile kapatıldı. Güvenlik turu istenmedi (şema/veri değişikliği yok; iki merge dosyasında `op.`/`execute` yok, probe S7).

## Koşular
- **Migration probe'u** (state/reviews/57-r1-probe.py, çıktı state/evidence/57r1-probe.log): 35+ kontrol, **FAIL yok**. Ana şekilli DB'yi gerçek merge-öncesi koddan (148eadd, `upgrade heads`) kurdum.
- Tam entegrasyon (`tests/integration`, llmaas): **678 passed, 4 skipped** (state/evidence/57r1-int.log). Contract `test_57_alembic_single_head`: 3 passed.
- migrate servisi: ilk `up`'ta exit 0 (boş DB), ikinci `run --rm migrate` çıktısı normal bitti (model kataloğu, checkpointer hazır). İkincisinin çıkış kodunu kendim `echo $?` ile yanlış (tail'in) okudum; çıkış kodu doğrudan **doğrulanmadı**, ama probe'da `upgrade heads` idempotent ve exit 0 kanıtlandı.
- NOT_RUN: unit + lint + airgap profili (değişiklik testler/belgeler + boş migration; işçi kanıtı lint 0, 737 iki profil, airgap 678). Ben koşmadım.

## Kontrol listesi
1. İki boş merge: 57_0001 (03a/03b/06a_0002/07 ebeveyn), 57_0002 (57_0001 + 03c/04a/05a/08). Dosyalarda işlem yok; `alembic heads` = `57_0002 (…) (head)` tek satır. ✔
2. Boş DB: `upgrade head` ve `upgrade heads` → {57_0002}, ikisi aynı şema; `heads` tek satır; `upgrade heads` iki kez ardışık exit 0. ✔
3. **Main şekilli DB** (gerçek eski kodla: alembic_version = {03c_0002, 04a_0001, 05a_0001, 08_0001}): `upgrade head` → {57_0002}; veri (projects, retention_runs) kayıpsız; şema parmak izi (sütun/indeks/kısıt, 493 sütun) main = yeni boş = yükseltilmiş **özdeş**. migrate yolu (`upgrade heads`) aynı. Kısmi kurulum (yalnız 04a+05a) → head, şema özdeş. ✔
4. Açık hedefli geri alma (veri dolu DB): `downgrade 57_0001` → {4 satır + 57_0001}, `upgrade head` geri; `downgrade 06a_0001` → 06a_0002 sütunu, retention tabloları gitti, projects verisi duruyor, kalan satırlar {03c_0001, 04a, 05a, 07, 08}; `upgrade head` şemayı aynen geri getiriyor; `downgrade 0001` + `upgrade head` round-trip şema özdeş. ✔
5. Göreli geri alma: `-1`, `06a@-1`, `03a@-1`, `03c@-1` hepsi "Ambiguous walk", rc 255, hiçbir satır/şema oynamıyor. PR'ın "Kapsam daralması" bölümü dürüst. Ek probe (57-r1-probe2.py): `07_0001@-1`, `07@-1`, virgüllü çoklu hedef ("Can't locate revision"), `57_0002-1` hepsi reddedildi; `03a_0001+0` yalnız 57_0001'i geri aldı → tek paket revizyonunu başkalarını bırakarak geri almanın **bulduğum** bir ifadesi yok, PR'ın iddiası (ifade edilemiyor) probe'larımla çelişmiyor (tüm olası yazımları denediğimi iddia etmiyorum). ✔
6. Belgeler: RELEASE_AND_ROLLBACK tek satır, docs/api.md (03a/03c/04a satırları açık revizyona), docs/gelistirme-ortami.md (iki adımlı merge gerekçesi, KeyError, yeni paketin tek uçtan başlaması), compose yorumu tutarlı. Yeni paket revizyonu (`down_revision=57_0002`, dal etiketi) probe S5: tek uç kalıyor, `upgrade head`, `downgrade -1` ve `zz@-1` çalışıyor. ✔
7. `scratch_db` fikstürü: bağlantı `with` ile kapanıyor, DB `DROP … WITH (FORCE)`; tam koşu sonrası `ffcore_scratch*` DB 0, sızan bağlantı 0; diğer testler 678 passed. ✔

## Bulgular
**MINOR-1** — Dönüştürülen paket round-trip testleri (örn. `test_08_23_migration_roundtrip`) artık "paket kendi tablolarını bırakır, diğerlerine dokunmaz" yerine `downgrade 0001` + seçili `upgrade` yapıyor; her şey silindiği için o iddianın ayrıcalıklı kanıtı kalmıyor. PR'ın "Kapsam daralması"nda belirtilmiş ve alembic sınırından geliyor, bulgu olarak yalnız şunu öneriyorum: yeni paketlerin (06b …) göreli `-1` testleri artık çalışır (zincir merge üstünde), onlar için bu testi kalıcı tut. Engel değil.

## Doğrulanmadı / not
- Alembic 1.20.1 sınırı ("Ambiguous walk", tek adımlı merge KeyError) PR'daki aktarıma dayanıyor; ben tek adımlı sekiz ebeveynli merge'i denemedim.
- Probe'un bıraktığı 3 `rev57_*` DB'si yığınla birlikte silindi.
