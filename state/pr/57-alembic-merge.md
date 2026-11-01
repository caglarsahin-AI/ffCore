# PR fix/57-alembic-merge: tek migration ucu (FOLLOWUP-57/132)

**Paket:** fix/57-alembic-merge · **Sınıf:** [B] · **Branch:** fix/57-alembic-merge · **Baz:** main 148eadd · **HEAD:** 5dbf11ec1eae40003b108cee09fc768943bdee0b (1 commit, 14 dosya +370/−88) · GOREV K-57-0001 · yeni bağımlılık, imaj, compose servisi yok.

## Plan (kısa, < 1 gün)

1. **Bulunan:** `backend/alembic/versions/` 8 dal ucu (03a_0001, 03b_0001, 03c_0002, 04a_0001, 05a_0001, 06a_0002, 07_0001, 08_0001; `alembic heads`). Göreli geri alma ve uç beklentisi kullanan yerler: `tests/integration/{test_03a_schema,test_06a_schema,test_07_schema,test_08_api,test_04a_store}.py`, `docs/api.md` (`03a@-1`, `03c@-1`, `04a@-1`), compose `migrate` yorumu, `docs/gelistirme-ortami.md`. Migrate servisi ve test fikstürü `alembic upgrade heads`.
2. **Kapsam:** boş merge revizyonu (şema yok), tek uç kanıtı, geri alma kuralının belgesi; testlerin yeni grafa uyarlanması. **Kapsam dışı:** compose `migrate` komutu (`heads` → `head` değişmedi, gerek yok), eski revizyonların grafı.
3. **Felsefe:** ARCH-07 tek kez, şemasız iki dosya; ARCH-09 Alembic'in kendi merge mekanizması; ARCH-06 göreli geri alma "Ambiguous walk" ile açık hata verir (test), sessiz yanlış geri alma yok.

## Ölçümle bulunan (KARAR-GEREK A-57-0003)

- **Tek adımlı merge çalışmıyor.** 8 ebeveynli tek revizyon: `alembic upgrade heads` → `KeyError: '03a_0001'` (alembic 1.20.1 `migration.py` `merge_branch_idents` her ebeveynin `alembic_version` satırını varlığına bakmadan siler). 03a_0001, 03b_0001, 06a_0002, 07_0001 başka revizyonların `depends_on`'u olduğu için satırsızdır ("effective head"); main DB'leri yalnız 4 satır taşır: 03c_0002, 04a_0001, 05a_0001, 08_0001.
- **Çözüm: iki adım.** `57_0001` satırsız dört ucu birleştirir (ebeveynlerinin hiçbiri satır değil → Alembic yeni satır ekler); `57_0002` onu satırlı dört uçla birleştirir. Boş DB'den ve main durumundaki DB'den `upgrade head` / `upgrade heads` → tek satır `57_0002`.
- **Göreli geri alma artık yok.** Merge revizyonu tüm dal etiketlerini miras alır; merge noktasından `downgrade -1` ve `<etiket>@-1` "Ambiguous walk". Geri alma açık revizyonla: `alembic downgrade <kalacak revizyon>` (örn. `06a_0001` yalnız 06a_0002 + bağımlısı 03c_0002 + merge'leri kaldırır). Bir dalın ilk revizyonunu tek başına kaldırmak (eski `03a@-1`) ifade edilemez: kök `0001`'e inip gereken dallar yeniden çıkılır. Yeni paketler (06b) tek ucun üstüne zincirlenir, onların `-1`'i çalışır.

## Değişen dosyalar

- Yeni: `backend/alembic/versions/57_0001_join_dependency_heads.py`, `57_0002_merge_heads.py` (ikisi de `upgrade/downgrade: pass`), `backend/tests/contract/test_57_alembic_single_head.py`, `backend/tests/integration/test_57_alembic_merge.py`.
- Test altyapısı: `backend/tests/integration/conftest.py` (`scratch_db` fikstürü: tek uçta geçici DB, yıkıcı round-trip'ler paylaşılan oturum DB'sine dokunmasın).
- Uyarlanan testler (başka paketlerin dosyaları, yalnız migration round-trip'leri): `test_03a_schema.py::test_03a_6_migration_round_trip`, `test_06a_schema.py::test_06a_schema_migration_round_trip`, `test_07_schema.py::test_07_migration_roundtrip`, `test_08_api.py::test_08_23_migration_roundtrip` (göreli `@-1` → açık hedef + `scratch_db`; aynı downgrade fonksiyonlarını sınar), `test_04a_store.py::test_04a_schema_alembic_heads_include_04a` (tek satır beklentisi). `ruff --fix` bu dosyalarda kullanılmayan `os/subprocess/BACKEND` importlarını kaldırdı.
- Belgeler: `docs/gelistirme-ortami.md` (tek uç paragrafı), `docs/api.md` (üç geri alma cümlesi), `deploy/docker-compose.yml` (yalnız `migrate` yorumu), `handbook/RELEASE_AND_ROLLBACK.md` "Geri alma ilkeleri" tek cümle (K-57-0002 touch-zone eki).

## Kabul kriterleri → testler

| # | Kriter (GOREV K-57-0001) | Test | Durum |
|---|---|---|---|
| 1 | `alembic heads` tek satır; tek uç her paket dalını kapsar; merge revizyonları şemasız | `test_57_1_single_head`, `_1_head_reaches_every_package_branch`, `_1_merge_revisions_are_empty` (contract, DB'siz), `test_57_1_alembic_heads_prints_one_line` (DB) | geçti |
| 2 | Temiz DB'de `upgrade head` (tekil); merge'ü geri al ve yeniden çık; `upgrade heads` (migrate) geriye uyumlu | `test_57_2_empty_database_upgrade_head_and_back` | geçti |
| 3 | Kurulu (merge öncesi, 4 satırlı) DB `upgrade head` ve `upgrade heads` ile tek uca çıkar | `test_57_3_pre_merge_database_upgrades_to_one_head`, `_3_pre_merge_database_upgrade_heads` | geçti |
| 3b | Main şekilli DB'de veri korunur (K-57-0002 2b) | `test_57_3_pre_merge_database_upgrades_to_one_head` (proje satırı + tablo kümesi aynı) | geçti |
| 4 | Göreli geri alma açık hatayla reddedilir, hiçbir şey değişmez; açık revizyonla tek paket revizyonu geri alınır (`downgrade 57_0001`, `downgrade 06a_0001`) | `test_57_4_relative_downgrade_from_the_merge_fails_loudly`, `_4_explicit_revision_rolls_back_one_package_revision`, `test_57_2_*` | geçti |
| 4b | `downgrade 0001` (hepsi) ve geri | `test_57_5_downgrade_to_the_root_and_back` | geçti |
| 6 | `migrate` servisi (komut `upgrade heads` değişmedi) main şekilli ve temiz DB'de tek uca çıkar (K-57-0002 madde 3) | yığında elle, `0.0.0-57` imajı: bkz. "migrate servisi kanıtı" | geçti |
| 5 | Paket round-trip'leri (03a/06a/07/08) yeni kuralla yeşil | uyarlanan 4 test + 04a heads testi | geçti |

Kırmızı: merge yokken contract 3/3 failed (`state/evidence/57-red-contract-20261101.log`). Tek adımlı merge ile `upgrade heads` KeyError (A-57-0003, yığın ölçümü).

## Çalıştırılan komutlar

Hepsi `MSYS_NO_PATHCONV=1 FFCORE_VERSION=0.0.0-main docker compose -p ffcore-57 --env-file .env.test ...` (imaj `0.0.0-main`, derleme yok; worktree kodu `tools` bind mount). Loglar `state/evidence/57-*-20261101.log`.

| Komut | Ortam | Exit | Sonuç |
|---|---|---|---|
| contract test_57 (merge yok) | | 1 | 3 failed (beklenen kırmızı) |
| hedefli migration testleri (test_57 + 4 round-trip + 04a heads) | llmaas | 0 | 14 passed (`57-migration-2`) |
| `docker compose config -q` | | 0 | |
| `make lint test` | `DEPLOY_PROFILE=llmaas` | 0 | 737 passed (734 + 3) |
| `make lint test` | `DEPLOY_PROFILE=airgap` | 0 | 737 passed |
| `make test-int` (yığın `--profile test --profile qdrant`, 0.0.0-main + worktree kodu) | llmaas | 0 | 677 passed, 4 skipped (683 s) |
| `make test-int` | airgap | 0 | 678 passed, 4 skipped (609 s; koşu sırasında eklenen `test_57_5` dahil) |
| `make lint` + `pytest test_57_*` (son hâl) | llmaas | 0 | 10 passed (`57-tests-final`) |
| `docker compose build backend` (`FFCORE_VERSION=0.0.0-57`; migration dosyaları imaja gömülü) | | 0 | |
| `docker compose run --rm migrate` main şekilli DB | | 0 | aşağıda |
| `docker compose run --rm migrate` temiz DB (`down -v` sonrası) | | 0 | aşağıda |

4 skipped: main'deki opt-in bayraklı testler (DNS/model ağırlığı), 03c kapılarındakiyle aynı.

### migrate servisi kanıtı (`state/evidence/57-migrate-service-20261101.log`)

- **Main şekilli DB:** yığın `0.0.0-main` ile açıldı, migrate servisi main'in grafını kurdu: `alembic_version` = `03c_0002,04a_0001,05a_0001,08_0001`, 38 tablo; sentinel proje satırı eklendi. `0.0.0-57` imajıyla `run --rm migrate`: `-> 57_0001`, `-> 57_0002` iki adım, exit 0; sonra `alembic_version` = `57_0002`, 38 tablo, sentinel satırı aynı, katalog 2 kayıt, checkpointer hazır. İkinci koşu exit 0, değişiklik yok (idempotent).
- **Temiz DB:** `down -v`, yeni postgres, `run --rm migrate` (`0.0.0-57`): 13 upgrade adımı, exit 0, `alembic_version` = `57_0002`, 38 tablo.

## Kapsam daralması (K-57-0002 madde 2d, açıkça)

- **Kayıp:** bir paket dalının **ilk** revizyonunu tek başına geri almak (eski `03a@-1`, `07@-1`, `08@-1`; 06a'nın ikinci adımı) artık ifade edilemez. Merge revizyonu tüm dal etiketlerini miras alır ve alembic merge noktasından göreli inemez ("Ambiguous walk"); açık hedef `X` yalnız X'in üstündekileri kaldırır, dalın ilk revizyonunun altı ortak kök `0001`'dir.
- **Kalan:** bir revizyonun üstünü açık hedefle geri almak (`downgrade 06a_0001`, `downgrade 03c_0001`, `downgrade 57_0001`) ve tamamını (`downgrade 0001`). Paket round-trip testleri bu yüzden `downgrade 0001` + seçili `upgrade` ile aynı downgrade fonksiyonunu sınar; "diğer paketler dokunulmadan kalır" iddiası "diğer paketler tek başına yeniden kurulur" iddiasına daraldı.
- **Gerekçe:** alembic sınırı (1.20.1); alternatifler A-57-0003'te (B çok uç, C tarih yeniden yazımı) reddedildi.
- **Yeni paketler** (06b dahil) `57_0002` üstüne zincirlenir; onların göreli `-1`'i zincir merge noktasının üstündeyken çalışır.

## Kontrol listesi

- [x] Felsefe çelişkisi işaretlendi: GOREV'deki "dal etiketleri çalışmaya devam eder" ve "`downgrade -1`" varsayımı alembic'te tutmuyor (A-57-0003).
- [x] Donmuş sözleşme yok (migration grafiği CONTRACTS'ta değil); şema değişmedi.
- [x] İki profil.
- [x] Mutasyon ucu yok; secret yok.
- [x] Docs güncel; `.env.example` değişmedi.

## Varsayımlar

1. Revizyon kimliği `57_<n>` (FOLLOWUP numarası; paket kodu değil). Dal etiketi verilmedi (merge revizyonu zaten tüm etiketleri miras alır; ek etiket anlam katmaz).
2. Yeni paket revizyonu `down_revision = <tek uç>` ve kendi `branch_labels` ile; aynı dalgada iki paket aynı uçtan başlarsa ikinci merge eden kendi rebase'inde (ya da dalga sonunda) bir merge revizyonu ekler; contract `test_57_1_single_head` main'de tek uç kuralını bekçi olarak tutar (PLAN 5 R2.6 "CI tek head bekler").
3. `handbook/templates/PR_SABLONU.md` "`alembic upgrade head && alembic downgrade -1 && alembic upgrade head`" satırı yeni paketler (tek ucun üstüne zincirlenen) için geçerli; merge revizyonunun kendisi için değil.

## Kalan riskler

- Yığında oluşturulan `ffcore/backend:0.0.0-57` imajı (7 GB) kullanıcı temizlik listesine (KARARLAR temizlik sınırı; ben silmedim).
- Alembic sürüm yükseltmesi `merge_branch_idents` davranışını düzeltirse iki adım yine çalışır (test_57_2/3 bekçi).
- `RELEASE_AND_ROLLBACK` "`alembic downgrade <önceki>`" diyor: uyumlu; ama paketlerin eski "`<etiket>@-1`" alışkanlığı belgelerde başka yerde kalmışsa (bulamadım: `git grep "@-1"` docs/deploy/handbook temiz) DRIFT.
