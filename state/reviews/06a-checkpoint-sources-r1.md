# fix/06a-checkpoint-sources (FOLLOWUP-116) · review r1

**Tam SHA:** 94f3e07843d3089221f94bd1401482af7c3cae2a (baz e5074ab, 1 commit, 12 dosya; baz diff'inde state/ yok) · **Sınıf:** [B] · **Karar:** ONAY. BLOCKER 0 · MAJOR 0 · MINOR 2.

## Koşular (yığın review116, test profili, `down -v` ile kapatıldı)

| Koşu | Sonuç |
|---|---|
| Entegrasyon alt kümesi: `test_116_checkpoint_sources` (9 test), `test_06a_schema` (migration up/down), `test_06a_graph`, `test_06a_run_access`, `test_07_flow`, `test_07_service`, `test_04a_api`, `test_af_2b` + 3 probe'um | 92 passed (log: `state/evidence/116-int.log`) |
| unit + contract, `DEPLOY_PROFILE=llmaas` | 727 passed |
| unit + contract, `DEPLOY_PROFILE=airgap` | 727 passed |
| Migration gerçek DB'de: `alembic downgrade 06a_0001` sonra `upgrade heads` | kolonlar `['checkpoint_deleted_at','source_deleted_at']` → `[]` → yeniden iki kolon; head `06a_0002` |

C9: contract testleri (8 durum, 18 olay tipi, 10 SSE adı) geçti; `source_deleted` yalnız `error.code` değeri, enum'lar değişmedi.

## Kendi probe'larım (`state/reviews/116-negative-probe.py`)

1. İlgisiz belge silinince bekleyen koşu işaretlenmiyor, thread duruyor, süpürge kapatmıyor: **geçti**.
2. Biten bir koşunun canlı Redis akışında HİÇBİR olayda parça metni yok (yalnız `sources`/`tool_result` değil): **geçti**.
3. Ölçüm: koşu bittikten sonra parça metnini taşıyan saklı olay türleri = `['llm_call']` (`request_messages`). `sources` taşımıyor.

## Güvenlik turu

- **Kimlik / ACL:** yeni uç yok. Belge silme uçlarının yetki kontrolleri değişmedi; işaretleme (`mark_document_runs`) aynı transaction'da, belge kimliği ile sınırlı (kimlik UUID, projeler arası çakışma yok).
- **Secret:** `purge`/`sweep` loglarında yalnız run kimliği, istisna türü ve sayı var; metin ve DSN yok.
- **SQL:** işaretleme sorgusu SQLAlchemy ile bağlı parametreli jsonb içerme (`contains`); elle SQL birleştirme yok. Süpürge sorguları sabit.
- **Egress:** yeni dış çağrı yok; `adelete_thread` aynı Postgres'e gidiyor.
- **PII / belge metni:** (a) canlı Redis akışında metin yok (probe 2). (b) Bitmiş koşunun checkpoint'i (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`) uçta siliniyor; başarısız silme koşuyu bitmiş bırakıp damgasız kalıyor, süpürge tekrar deniyor (`test_116_7`). (c) Belgesi silinen bekleyen koşu resume'da `failed/source_deleted` oluyor, onaylı araç ve model çağrılmıyor (`test_116_3`). (d) **Artık:** `run_events.llm_call.request_messages` parça metnini koşu bittikten sonra da saklıyor (probe 3 ölçümü); bu `GET /runs/{id}/events` ile okunabilir. PR bunu kapsam dışı bırakıp FOLLOWUP-119 (03c) olarak izliyor. Silinen belgenin breadcrumb'ı maskeli ama `llm_call` içindeki metin maskesiz.
- **Log sızıntısı:** erişim logları yalnız yöntem, yol, durum, süre; metin yok.

## Bulgular

**MINOR-1, `llm_call` olayında silinen belgenin metni kalıyor.** Yukarıdaki artık (FOLLOWUP-119). Bu paketin amacı (checkpoint) karşılandı; "silinen belgenin metni saklanmaz" hedefi ancak 119 ile tamamlanıyor. Takip kaydında sahibi ve kapanış koşulu (ör. `request_messages` için okuma-anı maskesi ya da retention) yazılı olmalı.

**MINOR-2, bekleyen koşuda pencere.** Belge silindiğinde bekleyen koşunun checkpoint'inde `messages` içindeki parça metni, süpürge (dakikada bir) ya da resume koşuncaya kadar durur; en çok bir süpürge aralığı. Tasarımın sonucu; docs/agentlar.md'ye süre notu yazılabilir.

## Doğrulanmadı (NOT_RUN)

- Önceki sürüm uygulaması, downgrade sonrası şemada açılıyor mu: eski imaj bu incelemede başlatılmadı; yalnız migration round-trip'i gerçek DB'de kanıtlandı. İki kolon nullable ve eklemeli, eski kod onları kullanmıyor.
- `sweep` içinde tek bir koşunun hatası (ör. Redis) aynı turdaki sonraki koşuları atlatıyor; sonraki tur tekrar deniyor. Gözlem, test edilmedi.
