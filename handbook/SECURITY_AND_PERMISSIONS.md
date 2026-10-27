# Güvenlik ve Agent İzinleri

## Secret politikası

- Secret yalnızca `.env` ve Postgres'te Fernet ile şifreli (anahtar `.env`'de). Kod, log, API cevabı, audit, test snapshot'ı, PR metni ve oturum mesajı secret içermez.
- `.env`'i kullanıcı doldurur; agent `.env` yazmaz, `.env.example`'a yalnızca ad ve Türkçe açıklama ekler.
- Test değerleri `tests/fixtures/` ve `data/samples/` altında; gerçek sağlayıcı anahtarı testte kullanılmaz (`FAKE_LLM=1`).
- API anahtarının ham değeri yalnızca oluşturma cevabında bir kez; DB'de `key_hash`. Araç ve kaynak kimlikleri (`tools.auth_config`, 16 bağlantıları) şifreli, API'de maskeli.
- Loglarda merkezi sanitizer: `Authorization`, `X-On-Behalf-Of`, `api_key`, `password`, `token` desenleri maskelenir; guardrail `matches` maskeli yazılır.

## Veri sınırı

- Hasta verisi ve kişi düzeyi kurum verisi platforma girmez (KARARLAR). Text-to-SQL yalnızca salt-okunur agent sunum DB'sine; kişi düzeyi veri yükleme anında maskelenmiş.
- Embedding yerel; belge dışarı çıkmaz. `llmaas`'ta egress izin listesi; `airgap`'te `OFFLINE=true` ile hiç çıkış yok.
- paycoreLLM deposunda okuma yasağı **dosya düzeyinde** (v9 P8, kararlar 4-5): `.env` (gerçek kimlik bilgileri), `data/**` (gerçek korpus), `eval/results/**` yasak; `eval/scenario*/questions.jsonl` (S1, iç dokümantasyon sorusu) ve `experts/*.yaml` (şablon) okunabilir ama FFCore deposuna kopyalanmaz. Worktree'lere gerçek `.env` kopyalanmaz; işçiler `.env.test` ile çalışır. PayCore kodu birebir kopyalanmaz, uzantı olarak kalır (C14).
- Örnek sözleşmeler ve şema (`data/samples/`) sentetiktir; gerçek kurum belgesi oraya konmaz. Kullanıcı gerçek belge verirse yalnızca kendi makinesindeki `.env` ile işaret ettiği dizinde kalır, depoya girmez.
- Geliştirmede Anthropic API'ye yalnızca sentetik veri gider.

## Agent izin matrisi

| İşlem | Durum |
|---|---|
| okuma, arama, kapsamlı edit, unit test | serbest |
| yerel compose, entegrasyon testi | serbest; hedef `localhost` ve test DB olduğu doğrulandıktan sonra |
| branch, worktree, PR açma | serbest |
| bağımlılık, imaj, compose servisi, sürüm değişikliği | kullanıcı onayı (C sınıfı) |
| migration'da kolon silme/yeniden adlandırma, public API ya da donmuş sözleşme kırma | kullanıcı onayı + KARARLAR (D sınıfı) |
| dosya silme, büyük yeniden adlandırma | kullanıcı onayı |
| dış indirme, ağdan paket kurma | geliştirmede serbest, ama `deploy/offline` manifestine eklenir; sunucu internetsizdir |
| PayCore Confluence/Jira ya da başka kurum sistemine bağlanma | yasak; 16 testleri yerel sahte sunucuyla |
| PayCore sunucusuna bağlanma, orada komut çalıştırma | yasak; komutları kullanıcı çalıştırır, çıktıyı PR'a yapıştırır (PayCore kuralı, 00i) |
| Jira'ya yazma (`JIRA_SUGGESTIONS_ENABLED`) | yasak; kapı kapalı kalır, test kanıtlar |
| yayınlama, deploy, üretim ya da müşteri erişimi | yasak; ayrı açık talep ve yetki olmadan |
| force push, history rewrite, `reset --hard` main'de | yasak |
| `.env` yazma, secret üretme | yasak |

## Uygulama güvenliği

- Facade ve tüm mutasyon uçları kimliksiz fail-closed (401/403); salt-okunur mod backend'de 403, önyüzdeki pasif düğme güvenlik değildir.
- `X-On-Behalf-Of` yalnızca `impersonate` kapsamlı anahtar ya da `SERVICE_TOKEN` ile; aksi yok sayılır ve `impersonation_denied` audit'e düşer.
- SQL: `run_sql` sqlglot doğrulayıcısından geçmeden DB'ye gitmez; salt-okunur DB kullanıcısı; `statement_timeout` DB tarafında da.
- Dış çağrılar (araç endpoint'i, webhook, kanal, kaynak): httpx ile zaman aşımı zorunlu; `llmaas`'ta izin listesi; özel IP aralıkları (SSRF) varsayılan engelli, `ALLOWED_INTERNAL_HOSTS` ile açılır.
- Dosya yükleme: içerik türü ve boyut sınırı; yol kullanıcı girdisinden türetilmez (uuid); Kapı 0 ikili dosyaları eler.
- Alt süreç: `shell=True` yok, argv listesi; Docling ve OCR işleri worker'da, zaman ve bellek sınırıyla.
- Prompt enjeksiyonu: araç sonucu ve belge parçası "veri" olarak işaretli bölümde; platform kuralları sistem mesajında; guardrail `tool.post` aşaması bunu izler.
- LiteLLM ve Langfuse dış ağa açılmaz; compose'da yalnızca backend ve frontend port yayınlar.
- Hata gövdeleri eyleme dönük ve secret-free; stack trace yalnızca logda.
