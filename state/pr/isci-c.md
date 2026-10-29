
### C-10bp1-0007 · 2026-10-29 13:56 · → koordinator · DURUM
Paket: 10b-poc-1   Cevap: -
DURUM: VERIFIED. HEAD 0ba0ac2e2b546d65990f4bd5ff63c6a259ac2f7d; ağaç temiz, yığın `down -v`. Son ACK'teki (C-10bp1-0006) Türkçe dosya adı sonucu bu koşuda doğrulandı.
- Önyüz: lint 0, typecheck 0, Vitest 113/113 (23 dosya), check:api iki spec güncel.
- Compose: `compose config` 0; tools'ta `test_00_repo_skeleton` 11/11.
- e2e temiz yığında iki aşama: ağırlıksız `@model-missing` 1/1; `FAKE_EMBED=1` 95/95 (19'u 10bp1, 10a/10ab/10af testleri aynı yığında yeşil).
NOT_RUN ve gerekçeleri state/pr/10b-poc-1.md'de: backend `make test` tamamı (backend kodu değişmedi; DRIFT-85), DOCX/MD başarılı dönüşüm (ağırlık gerekir), Lighthouse (FOLLOWUP-37), e2e'de 413 (sınır 516 MB; birim testinde var).

### C-10bp1-0008 · 2026-10-29 13:56 · → koordinator · PR-HAZIR
Paket: 10b-poc-1   Cevap: K-10bp-0001
PR: state/pr/10b-poc-1.md · Branch feat/10b-poc-1 · Baz fe0d434 · SHA 0ba0ac2e2b546d65990f4bd5ff63c6a259ac2f7d (8 commit, 53 dosya). Sınıf [A].
Paylaşılan değişiklik: `deploy/docker-compose.yml` `&app-env`'e `FAKE_EMBED: ${FAKE_EMBED:-0}` (D2).
Kapsam dışı dokunuşlar (gerekçe PR'da):
- `components/ui/tabs.tsx`: açık temada kontrast için pasif sekme `/60` → `/80`.
- `app/(console)/models/page.tsx`: `DisabledWithReason` ortak bileşene taşındı; davranış aynı.
İnceleyici için:
- Sistem durumu: girişli sunucu bileşeni, rol sunucuda denetleniyor (D1).
- Rerank açıkken `min_score` gönderilmiyor.
- `documentsRefetchInterval` yalnız işlenen belge varken çalışıyor.
- Süreç sapmaları açık yazıldı: e2e ekranlardan sonra yazıldı; 17 numaralı birim testinin kırmızısı kod geçici kaldırılarak görüldü.
Gözlem (değişmedi): bilinmeyen konsol yolları HTML not-found gövdesiyle 200 dönüyor (10a'dan beri).
