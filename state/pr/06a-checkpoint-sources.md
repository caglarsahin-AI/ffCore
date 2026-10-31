# PR: fix/06a-checkpoint-sources (FOLLOWUP-116)

**Paket:** fix/06a-checkpoint-sources · **Sınıf:** [B] (K-116-0002: additive kolon + additive hata kodu) · **Branch:** fix/06a-checkpoint-sources · **Baz commit:** e5074ab · **HEAD:** 94f3e07843d3089221f94bd1401482af7c3cae2a (e5074ab üstüne 1 commit)

Başlık: `[B] fix(06a): delete finished runs' checkpoints, stop live runs whose source was deleted`

## Plan (onay K-116-0002, seçenek A şartlı)

### 1. Bulunan semboller ve dosyalar (kaynak okundu, e5074ab)
- `runtime/graph.py:63-64` `_source_payload`: `Source.public() | {"text": ...}` → `state["sources"]` (retrieve, search tool).
- Metnin ikinci yeri (GOREV'de yoktu): `state["messages"]`: `guard_in` kullanıcı mesajına `sources_block` gömer (graph.py:137), `search_documents` sonucu `role: tool` mesajında (graph.py:423, 471).
- Üçüncü yer: LangGraph Postgres saver her adımı ayrı checkpoint satırı olarak tutar (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, thread_id = run id); son durumu temizlemek eski sürümleri silmez. e5074ab'de hiçbir yol thread silmiyordu.
- Runner dışı bitişler: `api/runs.py:652` (kuyruktaki/bekleyen koşu iptali), `services/approvals.py:383` `run_closer` (onay süresi). `waiting_user`'ın süre sınırı yok.
- Silinen belge maskesi: `api/runs.py:164-200` `mask_deleted_sources` (okuma yolunda, FOLLOWUP-108).
- `AsyncPostgresSaver.adelete_thread` (checkpoint-postgres 3.1.3) üç tablodan siler (imajda kaynak okundu).

### 2. Kapsam / kapsam dışı
- Kapsam: (a) `state.sources` metinsiz (retrieve metni yalnız bir sonraki adım `guard_in`'e taşır, guard_in metinsiz bırakır; search tool hiç taşımaz); (b) koşu bitince thread silinir (runner `_complete`/`_stop`), `runs.checkpoint_deleted_at` damgası; (c) dakikalık süpürge: runner dışında biten ya da silmesi başarısız koşular, idempotent (terminal AND kolon NULL), 24 saati geçen için `checkpoint_purge_overdue` log'u; (d) belge ve KB silme, o belgeyi kaynak göstermiş canlı (running/waiting_*) koşuları `runs.source_deleted_at` ile işaretler; işaretli koşu sonraki adımda (boundary), resume'da (graf koşmadan) ya da süpürgede (bekleyenler) `failed`/`source_deleted` biter ve thread'i silinir.
- Kapsam dışı: `run_events` içindeki metin (FOLLOWUP-119, 03c); `Message.sources` (zaten metinsiz); C8/C9 alanları.

### 3. Değişen dosyalar ve neden
- `backend/alembic/versions/06a_0002_checkpoint_lifetime.py` (yeni): iki nullable kolon + kısmi indeks `ix_runs_checkpoint_pending`; downgrade'li. 06a zincirinde (`06a_0001`'e bağlı, etiket 06a).
- `backend/ffcore/models/runs.py`: iki kolon ve indeks.
- `backend/ffcore/runtime/checkpoints.py` (yeni): `delete_thread`, `purge`, `mark_document_runs`, `sweep`, `latest_state`.
- `backend/ffcore/runtime/runner.py`: boundary `source_deleted_at`'i okur; `execute` işaretli koşuyu graf koşmadan durdurur; `_complete`/`_stop` sonunda `purge`.
- `backend/ffcore/runtime/graph.py`: `_source_payload` metinsiz; retrieve metni guard_in'e taşır, guard_in metinsiz kaydeder.
- `backend/ffcore/runtime/worker.py`: `sweep_checkpoints` cron (arka plan worker'ı, saniye 30; 07 süpürgesi saniye 0).
- `backend/ffcore/api/knowledge.py`: `delete_document` ve `delete_knowledge_base` aynı transaction'da `mark_document_runs` (touch-zone genişletmesi K-116-0002).
- `backend/tests/integration/test_116_checkpoint_sources.py`, `backend/tests/unit/test_116_source_state.py` (yeni).
- `backend/tests/integration/test_06a_schema.py`: round-trip artık `06a_0002` head'i ve iki adımlı downgrade'i sınar.
- `backend/tests/unit/test_07_worker.py`: arka plan worker'ında artık iki cron var; 07 testi kendi işini adıyla seçer (davranış aynı; 07 sahibine bilgi).
- `docs/agentlar.md`: "Checkpoints and deleted documents" bölümü, `source_deleted` hata kodu satırı.

### 4. Sözleşme, yapılandırma, profil
- C8 değişmez. C9: 8 durum ve 18 olay türü değişmez; `source_deleted` yalnız `error.code` değeri (additive, K-116-0002 madde 3), docs tablosunda. SSE adları değişmez.
- Yeni yapılandırma yok. Profil farkı yok; testler iki profilde.

### 5. Kabul kriteri → test
| # | Kriter | Test | Durum |
|---|---|---|---|
| 1 | Biten koşu (always KB): `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`'ta thread satırı 0; `checkpoint_deleted_at` dolu | `test_116_1_finished_run_leaves_no_checkpoint` | geçti |
| 2 | search_documents ile biten koşu: aynı; `sources`/`tool_result` olay gövdesi (Postgres ve Redis akışı) parça metni taşımıyor | `test_116_2_tool_search_leaves_no_checkpoint_and_events_carry_no_text` | geçti |
| 3 | Belge sil (04a API) → bekleyen koşu işaretli → resume `failed`/`source_deleted`, onaylı araç ve model çağrılmaz, thread 0 satır, `GET /runs/{id}/events` sources `[deleted]`; beklerken checkpoint'teki sources metinsiz | `test_116_3_resume_after_document_delete_fails_loud` | geçti |
| 4 | waiting_user koşusunun belgesi silinir → süpürge kapatır, `error` olayı (DB + Redis), thread 0 | `test_116_4_sweep_closes_waiting_user_run_with_deleted_source` | geçti |
| 5 | Runner dışı bitiş (iptal) → süpürge thread'i siler; ikinci süpürge idempotent (damga değişmez) | `test_116_5_sweep_purges_threads_of_runs_ended_outside_the_runner` | geçti |
| 6 | Belgesi canlı bekleyen koşu resume'da tamamlanır, model metni checkpoint'teki mesajdan görür, thread silinir | `test_116_6_resume_with_live_source_completes` | geçti |
| 7 | Silme başarısız → koşu yine terminal, kolon NULL; süpürge yeniden dener ve siler | `test_116_7_failed_purge_leaves_run_finished_and_sweep_retries` | geçti |
| 8 | `_source_payload` metin döndürmez; finalize alıntısı aynı | `test_116_8_source_state_has_no_text` (unit) | geçti |
| 9 | Süpürge cron'u yalnız arka plan worker'ında, dakikada bir | `test_116_9_checkpoint_sweep_cron_on_background_worker_only` (unit) | geçti |
| 10 | KB silme o KB'nin belgesini gösteren bekleyen koşuyu işaretler, başkasını işaretlemez | `test_116_10_knowledge_base_delete_marks_waiting_runs` | geçti |
| 11 | Çalışan koşu belge silinince sonraki adımda durur, model çağrılmaz | `test_116_11_running_run_stops_at_next_step_after_delete` | geçti |
| 12 | Migration upgrade → downgrade (`06a@-1` iki kez) → upgrade, gerçek Postgres | `test_06a_schema_migration_round_trip` | geçti |

Kırmızı kanıt: `red-1.txt` (modül yok), `red-2.txt` (iskelet modülle: 1, 2, 3, 4, 5, 6, 7, 8 davranış hatasıyla düştü: thread satırları 26/40/47, sources'ta `text`, süpürge boş).

### 6. Migration
`06a_0002` (06a etiketi). Upgrade sonrası eski bitmiş koşuların `checkpoint_deleted_at`'i NULL: ilk süpürgeler (200'lük partiler) thread'lerini siler. Bu bilinçli: e5074ab öncesi checkpoint'ler de metin taşır.

### 7. Geri alma
Kod geri alınır + `alembic downgrade 06a@-1` (iki kolon ve indeks gider). Silinmiş thread'ler bitmiş koşulara aittir; geri getirilmez, okunmaz.

### 8. Durma koşulları
Görülmedi (C8/C9'a dokunulmadı; api/runs.py ve services/approvals.py değişmedi).

### 9. Felsefe kontrolü
- ARCH-07: her koşu ve her agent; kalıcı ekleme bir modül, bir cron, iki nullable kolon; yeni olay türü yok.
- ARCH-09: silme LangGraph `adelete_thread`, zamanlama `arq cron`, kaynak eşleşmesi mevcut `sources` olayından (jsonb containment); kendi checkpoint deposu ya da metni yeniden kuran katman yok (B reddedildi).
- ARCH-06/10: silinmiş kaynakla devam yok (`source_deleted`, kodlu `error` olayı); silme hatası `checkpoint_purge_failed` log'u + süpürge yeniden dener + 24 saatte `checkpoint_purge_overdue`; sessiz boş kaynak yok.

## Değişen dosyalar
- backend/alembic/versions/06a_0002_checkpoint_lifetime.py (yeni)
- backend/ffcore/models/runs.py
- backend/ffcore/runtime/{checkpoints.py (yeni), runner.py, graph.py, worker.py}
- backend/ffcore/api/knowledge.py
- backend/tests/integration/{test_116_checkpoint_sources.py (yeni), test_06a_schema.py}
- backend/tests/unit/{test_116_source_state.py (yeni), test_07_worker.py}
- docs/agentlar.md

## Çalıştırılan komutlar
Hepsi `tools` konteynerinde, `MSYS_NO_PATHCONV=1 FFCORE_VERSION=0.0.0-116`, yığın `ffcore-116` (`--env-file .env.test --profile test --profile qdrant`, 18070/13070, `up -d --wait --pull never` 74 s). İmajlar `ffcore/{tools,backend,frontend}:0.0.0-116` = `0.0.0-main` etiketi (bağımlılık değişmedi; kaynak `/work` bind mount'tan). Çıktılar `state/pr/06a-checkpoint-sources-kapilar/` (tee).

| Komut | Ortam | Exit | Süre / sonuç | Dosya |
|---|---|---|---|---|
| hedefli pytest (yeni testler, modül yok) | llmaas | 2 | collection error | `red-1.txt` |
| hedefli pytest (iskelet) | llmaas | 1 | 8 failed, 2 passed | `red-2.txt` |
| hedefli pytest (116 + 06a graph/runs_api/schema) | llmaas | 0 | 20 passed / 55 passed | `green-3.txt`, `green-4.txt` |
| `make lint` | | 0 | ruff check + format | `lint.txt` |
| `make test` | `DEPLOY_PROFILE=llmaas` | 0 | 727 passed, 117 s | `test-llmaas.txt` |
| `make test` | `DEPLOY_PROFILE=airgap` | 0 | 727 passed, 113 s | `test-airgap.txt` |
| `make test-int` | llmaas | 0 | 541 passed, 4 skipped (opt-in), 2 uyarı (arq `close` deprecation, bu PR dışı), 425 s | `test-int.txt` |

## Kontrol listesi
- [x] Felsefe ile çelişen nokta yok
- [x] Donmuş sözleşme kırılmadı (C8/C9 yalnız additive hata kodu)
- [x] İki profil testi koştu
- [x] Mutasyon uçları değişmedi (silme uçları zaten `@audited`; işaretleme aynı transaction'da)
- [x] Log, API, audit secret-free; log satırları yalnız run id ve hata türü
- [ ] Önyüz: değişiklik yok
- [x] Docs güncel (`docs/agentlar.md`); `.env.example` değişmedi
- [ ] WORK_QUEUE: koordinatörde

## Varsayımlar ve brief'teki çelişkiler
1. İşaret yeri: K-116-0002 "işaretler" diyor; ikinci additive kolon `runs.source_deleted_at` seçildi (ayrı tablo değil; tek koşu, tek damga). Koordinatöre A-116-0005'te bildirildi.
2. İşaret kapsamı running + waiting_* (yalnız waiting değil): çalışan koşu da silinmiş metinle devam etmesin; boundary'de durur. Kuyruktaki koşu henüz kaynak görmediği için işaretlenmez.
3. retrieve → guard_in arası checkpoint sürümü metni taşır (guard_in'in girdisi); thread koşu sonunda bütün sürümleriyle silindiği için kalıcı değil. Alternatif (metni checkpoint dışı RunContext'te tutmak) worker'ın iki adım arasında ölümünde ikinci bir arama yolu gerektirirdi; reddedildi.
4. Bitmiş koşunun checkpoint'ini okuyan başka yol yok (grep: runner ve bir unit test); okuma uçları `runs`/`run_events`'ten.
5. Süpürge partisi 200 koşu/dakika; migration sonrası birikmiş eski thread'ler birkaç dakikada temizlenir.
6. `source_deleted` ile kapanan bekleyen koşunun 07 onay kaydı `pending` kalır; süresi dolunca 07 süpürgesi koşuyu "waiting değil" diye loglar (`approval_expired_run_not_waiting`) ve kaydı `expired` yapar. Kuyrukta görünmeye devam etmesi 07 davranışı; FOLLOWUP önerisi PR-HAZIR mesajında.

## Kalan riskler
- FOLLOWUP-119: `run_events.llm_call.request_messages` ve `answer.text` parça metnini taşımaya devam ediyor (03c retention). Bu PR'da NOT_RUN, gerekçeli. FOLLOWUP-116 "kısmen kapandı, kalan 119".
- K-116-0002 madde 6 (yalnız bulgu): önyüz koşu ekranı `components/run-timeline.tsx:31-33` `GET /runs/{id}/events` olay gövdelerini ham JSON gösteriyor; `llm_call` olayı `request_messages` içinde parça metnini taşıdığı için silinmiş belgenin metni koşu ekranında görünür (FOLLOWUP-119'un ekran yüzü). Test paneli (`components/agent-test-panel.tsx:246-253`, `lib/run-view.ts:90`) kaynakları SSE `sources` olayından okur: metin yok. Arama paneli KB aramasından okur (canlı). isci-c'ye FOLLOWUP.
- `checkpoint_purge_overdue` yalnız log; uyarı kuralı 03c (FOLLOWUP önerisi).
- Gerçek model ve airgap yığını: NOT_RUN (değişiklik model çağrısına dokunmuyor; graf scripted port'larla gerçek LangGraph + Postgres üzerinde koşuyor).
