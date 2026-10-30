# 10b-poc-2 · review r1

**Tam SHA:** 2459133138523b039e687ac3be535aebca175613 (10 commit, frontend + docs)
**Karar:** EKSİK KANIT, ONAY VERİLMEDİ (K-INC-0008: bağımsız e2e ve kendi negatif testi olmadan ONAY yok).

## Yığın

Proje `review10bp2`, portlar 18040/13040, `FFCORE_VERSION=0.0.0-review-10bp2`. Belgelenen adımlar (`docs/onyuz.md` 256-286) uygulandı: `up -d --wait --build` çıkış 0; `seed-prompts` çıkış 0 (platform_rules oluşturuldu); superadmin oluşturuldu. Yığın kapatıldı (`down -v`, kalan konteyner yok).

## Kanıt

| Aşama | Komut | Sonuç |
|---|---|---|
| 1 | `npx playwright test --grep @model-missing` | 1 passed (`test_10bp1_10_readiness`); çıkış 0 |
| 2 | `FAKE_EMBED=1`, backend ve worker yeniden başlatıldı, `--grep-invert @model-missing` | **NOT_RUN**: 590 s zaman aşımında kesildi (çıkış 124), sonuç alınamadı |

Aşama 2 yeniden koşulmadı: host disk %99 (8,4 GB boş), koordinatörün "yeni imaj yok, hemen kapat" talimatı.

## Eksik

- Aşama 2 sonucu yok; bilinen kırmızı test `test_10bp2_3` (FOLLOWUP-105) bu koşuda görülemedi.
- Negatif e2e testi yazılmadı (K-INC-0008 zorunlu kılıyor).
- Frontend diff'inin kod okuması (erişim kontrolü, rol görünürlüğü, hata metinleri) bu turda yapılmadı.

## Güvenlik turu

Bu PR'da güvenlik turu istenmedi; API ve akış tarafında yeni kod değil, yalnız önyüz ve belge. Kod okuması yapılmadığı için bu kısım da NOT_RUN.

## Önyüz kod okuması (yığınsız, R-10BP2-0005)

Değişen 102 dosyanın önyüz kısmı (`git show :...`, ana tabanına göre): dangerouslySetInnerHTML, localStorage, innerHTML, eval, window.open taraması temiz; sabit renk sınıfı (bg-white, text-gray-*, #fff/#000) yok.
Yazma kontrolü: onay düğmeleri `can_decide` ile devre dışı (`approvals/[approvalId]/page.tsx` 72, 120), `WriteGate` ile sarılmış (test paneli onayı dahil); çalıştırma ve geri bildirim formu `fieldset disabled={!canWrite}`. Bu yalnız önyüz; sunucu tarafı 403 kontrolü 07 r2'de yığın testleriyle doğrulandı.
Bulgu (önyüz): yok.

## Negatif e2e (yazıldı, koşulmadı)

`state/reviews/10b-poc-2-r1-negative.spec.ts`: anonim ziyarette onay ayrıntısı ve düğmeleri yok, `/login`'e yönlenir; anonim `approve` isteği 2xx dönmez. NOT RUN (yığın kapalı).

## Güncel karar

Hâlâ **EKSİK KANIT, ONAY yok**: aşama 2 sonucu yok (1147 s koşu, tekrarında en az 1800 s zaman aşımı gerekli), negatif test koşulmadı, test_10bp2_3 (FOLLOWUP-105) doğrulanmadı.

## Yığın koşusu (K-INIT-0024, 2026-10-30 16:44)

Tam SHA 2459133138523b039e687ac3be535aebca175613; yığın `review10bp2` (18040/13040), aynı worktree, `--pull=never`; MinIO ve Qdrant pinli imajları kullanıcı tarafından çekildi.

| Koşu | Sonuç |
|---|---|
| seed-prompts, superadmin | çıkış 0 |
| Aşama 1: `--grep @model-missing` | 1 passed |
| Aşama 2: `FAKE_EMBED=1`, `--grep-invert @model-missing`, 1800 s zaman aşımı | 136 passed, **1 failed** (10.2 dk, çıkış 1); log: `state/evidence/10bp2-r1-stage2.log` |
| Negatif e2e: `rev_10bp2_neg_1` (`state/reviews/10b-poc-2-r1-negative.spec.ts`) | **1 passed** (anonim onay ayrıntısı ve düğmeleri yok, /login'e yönlenir, anonim approve 2xx değil) |

**Kırmızı test:** `test_10bp2_3_agent_wizard_lifecycle` (FOLLOWUP-105). Beklenen: kaydetme hatası `variable_undefined` kodunu göstersin. Gerçek: `Some fields are not valid. Check the form and try again. (code: validation_error)`. Yani sihirbaz API'nin ayrıntılı kodunu göstermiyor; bu bir ürün açığı, test gevşetilmedi.

**Karar:** DUZELT (tek kırmızı kabul testi). Öneri: sihirbazın kaydetme hatasında API kodunu (`variable_undefined`) göstermesi. Alternatif (koordinatör kararı): FOLLOWUP-105 olarak kabul edilip paket ONAY alır; bu durumda test'in kırmızı kalması ve kayıtta açık olması şart.

**Güvenlik turu:** istenmedi; önyüz kod okumasında bulgu yok; negatif test geçti.
**Worktree:** yalnız `docs/images` (42 PNG, e2e yeniden üretti). Başka değişiklik yok.
