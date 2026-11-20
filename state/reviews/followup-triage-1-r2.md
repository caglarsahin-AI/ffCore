# Review followup-triage-1 r2 · teyit turu (r1 MINOR-1, NOTE-1, NOTE-3)
SHA: f6ec3e5f45cb1699ef13113f0a85ac72254c46ee · Sonuc: ONAY · Bulgu: B0 M0 m0 N0

- **İncelenen tam SHA:** `f6ec3e5f45cb1699ef13113f0a85ac72254c46ee`.
- **Delta** `292f290..f6ec3e5`: 2 commit, 4 dosya, +32/−5.
  - docs 8e73cc3
  - test + kod f6ec3e5
- **İstek:** K-TRJ-0007. Kararlar: K-TRJ-0006 (MINOR-1 + NOTE-3 metni, NOTE-1 `url` alanı merge öncesi; NOTE-2 FOLLOWUP-210). r1 raporu `followup-triage-1-r1.md`.
- **Yöntem:**
  - Delta satır satır okundu.
  - Yığın açılmadı. Tek bir `--network none` tools konteyneri (`ffcore-rv-trj2-unit`, `0.0.0-main`) `git archive` kopyası üzerinde koştu: `ruff check backend`, değişen iki dosyada `ruff format --check`, `test_trj_194_platform_targets` ve `test_05b_platform_targets`.
- **Karar: ONAY.** r1'in üç maddesi kapandı. Delta yalnız bu maddelere dokunuyor.

## Testler
Log: `state/evidence/followup-triage-1-r2-rv-unit.log` (`HEAD=` satırlı).

| Koşu | Sonuç |
|---|---|
| `ruff check backend` + iki dosyada format | temiz |
| `test_trj_194_platform_targets` + `test_05b_platform_targets` | 89 passed, exit 0 |

## Kontrol listesi (K-TRJ-0007)

| # | Madde | Sonuç |
|---|---|---|
| 1 | **MINOR-1: iki belge metni** | `ajanlarla-gelistirme.md` <br>• Satır 631, hook tablosu: "ayrı `compose build` hiçbir biçimde yok (`--pull=false` ile de); `up` (`--build` dahil) yalnız `--pull never`". Geçen örnekler `up -d --wait --no-build --pull never` ve `--build --pull never`; reddedilenler `compose build`, `compose build --pull=false`, `up -d` ve `--pull never`'sız `up --build`. Hook'un davranışı da tam bu (r1 probe'u, 13 biçim). <br>• Satır 507, Ders: "Kural (bugün, FOLLOWUP-207 ile değişti)" bugünkü kuralı veriyor; eski kural ve `gate09.sh` cümlesi "tarihî not" diye işaretli. <br>`ENVIRONMENT_AND_COMMANDS.md` ve 6.3 bölümü r1'de zaten doğruydu. Depoda kural olarak `build --pull=false` öneren başka metin kalmadı (`git grep`). Kapandı. |
| 2 | **NOTE-3: plan/04 satır 5-6** | Satır 5'teki "(tam göç 04b)" ifadesi şöyle değişti: "(DuckDB sonradan tamamen kaldırıldı, meta 04a'dan beri Postgres'te; 04b'nin işi `migrate-vectors` ve sürücü eşdeğerliği, D1; DRIFT-198)". Satır 6 ile tutarlı. PoC'nin tarihî anlatımı (bağdaştırıcı DuckDB'yi sarar) korunmuş; DOC-18 ile uyumlu. Kapandı. |
| 3 | **NOTE-1: qdrant `url`** | `URL_FIELDS = ("base_url", "api_base", "url")`. `refuse_platform_urls` kayıtta (`create_provider`), testte (`test_provider_config`) ve güncellemede (birleştirilmiş config ile, `update_provider`) çağrılıyor. Dolayısıyla `{"url": "http://backend:8000"}` kaydı da güncellemesi de 400 `endpoint_is_platform` alıyor, aynen `/providers/test` gibi. Testler: <br>• her üç alan × üç platform URL'si 400, mesajda URL yok <br>• qdrant `test_connection` `endpoint_is_platform` <br>• `test_trj_194_url_fields_cover_every_driver_address`: sürücü alanlarından adres olanlar tam olarak `{base_url, api_base, url}` ve hepsi listede |
| 4 | **URL_FIELDS dışında adres alanı** | `DRIVERS` alanlarını kaynaktan saydım: `base_url`, `api_key`, `api_base`, `api_version`, `aws_access_key_id`, `aws_secret_access_key`, `region`, `url`, `path`. `path` (local sürücü) konteyner içindeki bir dizin, ağ adresi değil. `region` bir bölge adı. Dışarıda adres alanı kalmadı. Yeni bir sürücü `*url*` adlı bir alanla gelirse kapsam testi kırmızıya döner. |
| 5 | **Başka değişiklik** | Delta: `services/providers.py` (2 satır + yorum), birim testi (+26), iki belge. r1 maddeleri dışında değişiklik yok. |

## Bekleyen dosyalar (commit edilmedi)
- `state/reviews/followup-triage-1-r2.md`
- `state/evidence/followup-triage-1-r2-rv-unit.log`
- `state/kanal/inceleyici.md`
