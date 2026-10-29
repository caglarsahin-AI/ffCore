# PR: [A] test: belgelenen test komutları temiz ortamda, ağırlıksız yeşil

**Paket:** 04a takibi (DRIFT-85) · **Sınıf:** [A] · **Branch:** fix/main-test-gates · **Baz:** main fe0d434 · **SHA:** 7605022c46b3ad2d9fe6b82631b50592811e906b · 1 commit, push yok · **GOREV:** K-04a-0031

Yalnız testler ve belge değişti; ürün kodu (backend/ffcore) değişmedi.

## Temiz ortam

Kendi Compose projesi `fix-main-gates`, yeni volume'lar (`model_cache` boş: 0 dosya), imajlar fe0d434'ten `FFCORE_VERSION=0.0.0-fixgates` ile derlendi; belgelenen `docker compose up -d --wait` (`.env` yerine `--env-file .env.test`, ajan `.env` yazmaz). Kırmızı koşu ayrı detached worktree'den (fe0d434), aynı yığına karşı.

## Kırmızı (fe0d434, temiz yığın, yalnız belgelenen komutlar)

| Komut | llmaas | airgap |
|---|---|---|
| `make test` | 2 failed, 383 passed | aynı |
| `make test-int` | 24 failed, 160 passed, 27 errors | aynı |

- `make test`: `test_03b_2_unresolvable_host_is_request_failed` (gerçek resolver, `.invalid` Docker DNS'te 5 s bütçeyi aşıp `egress_timeout`), `test_04a_r1_5_next_file_converts_after_refusals` (Docling ağırlığı).
- `make test-int`: 01'in LiteLLM testleri 23 error (fake-llm, profil `test`, belgelenen `up` başlatmıyor; B'nin raporunda yoktu, o yığında fake-llm ayaktaydı); Qdrant testleri (profil `qdrant`) 4 error + failed; 04a ingest/API/ACL/r1 testlerinin pgvector tarafı da failed: Markdown üründe Docling'den geçiyor, `model_missing: docling-project/docling-models` (B'nin listesinden geniş: onun model_cache'inde Docling ağırlığı vardı, doğrulanmadı). Tam liste koşu çıktısında (24 FAILED kimliği).

## Düzeltme

1. **03b DNS** (`tests/unit/test_03b_egress.py`): birim testi `socket.gaierror(EAI_NONAME)` atan sahte resolver kullanır; davranış aynı (`egress_dns_failed`, host var, yol yok, `__cause__` yok). Gerçek resolver senaryosu `tests/integration/test_03b_egress_dns.py`'ye: 30 s arama bütçesi; `egress_dns_failed` beklenir, zaman aşımı geçti sayılmaz, açık nedenle NOT_RUN (skip "NOT_RUN: the system resolver did not answer within 30 s"). Not: Docker'ın DNS'i bilinmeyen adı host resolver'ına iletir; `.invalid` sorgusu kurum DNS'ine gidebilir (bu test öncesinde birim testindeydi, şimdi yalnız entegrasyonda).
2. **Ağırlık isteyen testler**: `tests/converters.py::convert_without_weights` — Markdown'ı olduğu gibi okur; stdlib dönüştürücüleri (düz metin, e-posta, MHTML, diyagram) ve açık skip'ler gerçek dönüştürücüyle; ağırlık isteyen biçim testi yüksek sesle düşürür ("mark the test `models`"). Dönüştürme sonrası hattı test eden entegrasyon testleri bunu kullanır (`test_04a_api`, `test_04a_ingest`, `test_04a_review_r1_acl`, `test_04a_review_r1_ingest`). Kapsam kaybı yok: Markdown uçtan uca testinin gerçek Docling varyantı `models` işaretli parametre (`[docling]`), 13a docx (`convert_bounded`) `models` işaretli. Worker testi gerçek job yolunu (kalıcı dönüştürücü süreci) korur, yüklemeyi `.eml` yapar (stdlib, ağırlıksız). Birim `next_file_converts_after_refusals` sonraki dosyayı düz metin yapar.
3. **Profiller**: seçim **ikisi birlikte**: (a) belgelenen tek komut gereken profilleri başlatır: `docker compose --profile test --profile qdrant up -d --wait && docker compose run --rm tools make test-int` (`docs/gelistirme-ortami.md`); (b) biri yine de erişilemezse `tests/integration/conftest.py` toplama sonrası tek mesajla durur: "integration services not reachable: qdrant (profile qdrant) at …, fake-llm (profile test) at …. Start them: …", exit 1 (sessiz atlama yok). Gerekçe: GOREV "belgelenen tek komutla yeşil olan"ı istiyor, bu (a); (b) 27 ayrı hata yerine nedeni ve çözümü tek satırda verir. Yalnız seçilen testler gerektirdiğinde kontrol eder (Qdrant: `vectorstore` işaretli test + `RUN_QDRANT_TESTS=1`; fake-llm: LiteLLM fixture'ı kullanan test).

## Yeşil (7605022, aynı temiz yığın, model_cache 0 dosya)

| Komut | llmaas | airgap |
|---|---|---|
| `make lint` | 0, 197 dosya | |
| `make test` | 385 passed | 385 passed |
| profil olmadan `make test-int` | tek mesajla durdu, make exit 1, test koşmadı | |
| belgelenen komut: `--profile test --profile qdrant up -d --wait` + `make test-int` | 207 passed, 2 skipped | 207 passed, 2 skipped |

2 skipped = `models` işaretli: Markdown uçtan uca `[docling]` ve 13a docx ("NOT_RUN: needs RUN_MODEL_TESTS=1"). Gerçek resolver DNS testi koştu ve geçti (`egress_dns_failed`, skip değil).

## Felsefe

80/20: ürün kodu değişmedi; tek test dönüştürücüsü, tek ön kontrol. Fail-loud: ağırlık isteyen biçim sahte dönüştürücüde düşer; eksik servis tek mesajla durur; DNS zaman aşımı geçti sayılmaz. Kapsam: Docling yolu `models` altında korundu (make models sonrası `make test-models`).

## Review r1 → düzeltme → kanıt (DUZELT K-04a-0036)

**Yeni SHA:** 4418a3f94a7e228ea9ffc0353221b82ce3db64bb (7605022 + 1 commit) · Baz main fe0d434 · Tur r2.

| Bulgu | Düzeltme | Kırmızı (7605022) | Yeşil (4418a3f) |
|---|---|---|---|
| MAJOR-1: gerçek resolver testi varsayılan `make test-int`'te `.invalid` sorgusunu host/kurum DNS'ine iletebilir | Karar B: `dns` işareti + `RUN_DNS_TESTS` bayrağı (kök conftest `FLAGS`, `pyproject` markers); test modülü `pytestmark = pytest.mark.dns`; bayraksız kök conftest testi toplama sırasında `NOT_RUN: needs RUN_DNS_TESTS=1` diye atlar, fixture ve arama koşmaz; `docs/gelistirme-ortami.md` bayrağın yığın dışına (host/kurum resolver'ına) DNS sorgusu gönderdiğini ve bayraklı komutu yazar | `tests/unit/test_03b_dns_opt_in.py` 2/2 failed (`KeyError: 'dns'`; belgede `RUN_DNS_TESTS=1` yok) | 2/2 passed |

Kanıt (yeni temiz yığın `fix-main-gates`, model_cache 0 dosya, belgelenen komut, bayrak verilmedi):

| Komut | llmaas | airgap |
|---|---|---|
| `make lint` | 0, 198 dosya | 0 |
| `make test` | 387 passed | 387 passed |
| `--profile test --profile qdrant up -d --wait` + `make test-int` | 206 passed, 3 skipped | 206 passed, 3 skipped |
| `docker run --network none … pytest -rs tests/integration/test_03b_egress_dns.py` | 1 skipped, "NOT_RUN: needs RUN_DNS_TESTS=1", 0,21 s | |

3 skipped: `test_03b_egress_dns.py` (RUN_DNS_TESTS), Markdown uçtan uca `[docling]` ve 13a docx (RUN_MODEL_TESTS). Ağsız koşuda test, hiçbir ağ olmadan atlandı: atlama arama yapılmadan önce. Bayraklı koşu yapılmadı (DUZELT: dış DNS; kararı kullanıcıda). Birim testindeki sahte resolver kanıtı değişmedi.
