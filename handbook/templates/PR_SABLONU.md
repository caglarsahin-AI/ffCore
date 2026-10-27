# PR Şablonu

**Paket:** NN(a/b) · **Sınıf:** [A|B|C|D] · **Branch:** feat/NN-slug · **Baz commit:** abc1234

## Plan (ilk yorum olarak, kodlamadan önce)
1. Bulunan semboller ve dosyalar:
2. Kapsam / kapsam dışı:
3. Değişecek dosyalar ve neden:
4. Sözleşme, yapılandırma, profil etkisi:
5. Kabul kriteri → test adı:
6. Migration (branch label):
7. Geri alma:
8. Durma koşulları:
9. Felsefe kontrolü: ARCH-07 (kaç senaryo, kalıcı karmaşıklık?) / ARCH-09 (platform zaten sunuyor mu?) / ARCH-10-06 (gizli otomatik davranış, sessiz fallback?):

## Değişen dosyalar
- backend/...
- frontend/...
- docs/...

## Kabul kriterleri → testler
| # | Kriter (brief'ten) | Test | Durum |
|---|---|---|---|
| 1 | | `test_NN_1_...` | geçti / NOT_RUN (neden) |

## Çalıştırılan komutlar
| Komut | Ortam | Exit | Süre |
|---|---|---|---|
| `make lint` | | 0 | |
| `make test` | `DEPLOY_PROFILE=llmaas FAKE_LLM=1` | 0 | |
| `make test` | `DEPLOY_PROFILE=airgap FAKE_LLM=1` | 0 | |
| `make test-int` | | | |
| `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` | | | |
| `make smoke` | | | |

## Çıktı özeti ve post-state
(secret-free, kurum verisi yok; tablo sayıları, oluşan dosyalar)

## Kontrol listesi
- [ ] Felsefe ile çelişen bir nokta varsa işaretlendi, sessizce geçilmedi
- [ ] Donmuş sözleşme kırılmadı (CONTRACTS.md) ya da D sınıfı onayı var
- [ ] İki profil testi koştu
- [ ] Her mutasyon ucu audit üretiyor; salt-okunur mod 403
- [ ] Log, API, audit, hata gövdesi secret-free
- [ ] Türkçe metinler `tr.json`'da; iki tema test edildi (önyüz)
- [ ] Docs ve `.env.example` güncel
- [ ] `state/WORK_QUEUE.md` durumu güncellendi

## Varsayımlar ve brief'teki çelişkiler

## Kalan riskler
