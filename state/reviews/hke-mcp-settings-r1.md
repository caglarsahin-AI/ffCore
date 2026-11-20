# Review fix/hke-mcp-settings r1
SHA: a9cc7016ae1d0002bd90ee8bceed9a986a4642a9 · Sonuc: ONAY · Bulgu: B0 M0 m0 N1

- **İncelenen tam SHA:** `a9cc7016ae1d0002bd90ee8bceed9a986a4642a9` (dal `fix/hke-mcp-settings`).
- **Delta** `main..a9cc701`: 2 commit, 3 dosya, +104/−31.
  - test f7cd5d1
  - fix a9cc701
- **İstek:** K-HKE-0013. Sebep: K-HKE-0011 (ffmain test-int'te 05a canlı mcp-sql 500; `McpServiceSettings.egress_proxy_url` yok).
- **Yöntem:**
  - Delta satır satır okundu.
  - Main'de `SafeOutboundClient` / `policy_http_client` / `check_http_destination` / `EgressPolicy`'ye geçen her ayar tipi listelendi (hazırlık notu). Tek istisna `services/mcp_server_common.py` 135 ve 239: `McpServiceSettings`. Geri kalan 20 çağrı noktası `core.config.Settings` geçiyor. Egress'e geçen başka `BaseSettings` sınıfı yok.
  - `tools:0.0.0-hke` konteynerinde, `--network none`, `git archive` kopyası üzerinde koşuldu: ruff, birim testleri ve iki kırmızı probe (B, C).
  - 05a canlı testleri için işçi loguna dayandım (kapıda da koşacak); yığın açmadım.
- **Karar: ONAY.** Düzeltme doğru ve tek kaynaklı. Bir NOTE: yeni testin keşif yöntemi bir durumda sessiz kalıyor.

## Testler
Log: `state/evidence/hke-mcp-settings-r1-rv-unit.log` (`HEAD=` satırlı).

| Koşu | Sonuç |
|---|---|
| A: ruff + format (değişen 3 dosya) | temiz |
| A: `test_hke_208_settings_classes`, `test_hke_208_egress_proxy`, `test_03b_egress` | **82 passed** |
| B: `ffcore/` altına egress biçimli ama `egress_proxy_url`'süz bir sınıf (`RvProbeSettings`) | **1 failed**: `assert ['RvProbeSettings'] == []`. Test yeni sınıfta kırmızıya düşüyor. |
| C: aynı sınıf, import'u düşen bir modülde | **4 passed**, sessiz (NOTE-1) |
| D: bugün import'u düşen modüller (çıplak ortam) | 1 tane: `ffcore.knowledge.worker` (import anında `Settings()` kuruyor) |
| İşçi logu `hke-mcp-test-int.log` (HEAD a9cc701) | `test_05a_live_services` **5 passed**; mcp-sql `run_sql outcome=ok`. Kırmızı kanıt `hke-mcp-red.log` 4 failed; `make test` 2156 passed (`hke-mcp-gate-summary.log`) |

## Kontrol listesi (K-HKE-0013)

| # | Madde | Sonuç |
|---|---|---|
| 1 | **Ayar sınıfı testi iki sınıfı kapsıyor mu** | `test_hke_every_egress_settings_class_declares_the_proxy` `ffcore` paketini dolaşıyor, `egress_allowlist` alanı olan her `BaseSettings` sınıfını egress sınıfı sayıyor. Kümenin en az `{Settings, McpServiceSettings}` olduğunu ve hepsinde `egress_proxy_url` olduğunu kontrol ediyor. Yeni bir sınıfta kırmızıya düşüyor (probe B). İstisna: import'u düşen modül (NOTE-1). Ayrıca `McpServiceSettings` ile iki istemci de kuruluyor, ortamdan proxy okunuyor ve proxy taşıyıcısı seçiliyor (test 1-2). |
| 2 | **`EgressProxyUrl` doğrulayıcısı** | Gövde değişmeden modül düzeyi `_plain_proxy_origin` fonksiyonuna taşındı; `Annotated[str, AfterValidator(...)]`. İki sınıf da aynı tipi kullanıyor, tanım tek yerde. Boş değer kapalı (`""` döner). Geçersiz değer `ValidationError` ve `egress_proxy_url_invalid` ile başlangıcı durduruyor; `McpServiceSettings` için test 3 `https://user:pw@…/x` ile sınıyor. r1'deki yedi geçersiz biçim probe'u aynı fonksiyonu sınamıştı. `Settings` doğrulaması `test_hke_208_egress_proxy` içinde yeşil. |
| 3 | **05a canlı 5/5** | İşçi logu: 5 passed, HEAD a9cc701. Kapıda yeniden koşacak. |
| 4 | **Başka değişiklik** | Yok. `config.py`'de doğrulayıcı taşındı ve bir import eklendi; `mcp_server_common.py`'de bir alan ve bir import; bir yeni test dosyası. Davranış değişikliği yalnız `McpServiceSettings`'in alanı. Egress overlay'i mcp-search ve mcp-sql'e `EGRESS_PROXY_URL` vermiyor: boş varsayılan doğru, çünkü bu servislerin dış çağrısı yok, yalnız iç backend'e gidiyorlar. |

## NOTE-1 · Sınıf keşfi import'u düşen modülü sessizce atlıyor
- `_settings_classes()` içindeki `except Exception: continue`, import'u düşen modüldeki sınıfı hiç görmüyor (probe C: 4 passed). Yorum "listed below if any" diyor ama bir liste yok.
- Bugün çıplak ortamda düşen tek modül `ffcore.knowledge.worker`; import anında `Settings()` kuruyor, yeni bir ayar sınıfı tanımlamıyor. Yani bugün kaçan bir sınıf yok. Ama worker modülleri tam da yeni ayar sınıfının çıkabileceği yerler.
- Ayrıca test yalnız `egress_proxy_url`'yi soruyor. Egress'in okuduğu diğer alanlar (`offline`, `egress_allowlist`, `allowed_internal_hosts`) da çalışma anında `AttributeError` → 500 sınıfından.
- Öneri:
  - Düşen modüller beklenen bir listeyle karşılaştırılsın (`{"ffcore.knowledge.worker"}` ve gerekçesi); listede olmayan bir düşüş testi kırsın.
  - Alan kontrolü egress'in okuduğu kümenin tamamı olsun.
- Merge'ü bekletmez: main kırık, düzeltme doğru.

## Bekleyen dosyalar (commit edilmedi)
- `state/reviews/hke-mcp-settings-r1.md`
- `state/evidence/hke-mcp-settings-r1-rv-unit.log`
- `state/kanal/inceleyici.md`
