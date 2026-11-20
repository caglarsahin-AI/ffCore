# Kanal: isci-a

Yalnızca bu rol yazar; mesajlar sona eklenir, eskisi değiştirilmez. Biçim ve türler: handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim".

- Oturum kimliği: ffcore-isci-a-12 (Opus 5.5; önceki lease ffcore-isci-a-hook RETIRED 2026-11-19, K-HOOK-0017)
- Aktif paket: 12 (K-12-0001), dal feat/12-kurulum, worktree .worktrees/feat/12-kurulum
- Durum: ACTIVE
- Son okunan: K-GEN-0031

## Mesajlar
- Arşiv: MERGED/kapalı paketlerin mesajları `state/kanal/arsiv/isci-a-<paket>.md` dosyalarında (16 Kasım 2026 taşıması: 342 mesaj); ID ile atıf orada bulunur.

### A-12-0001 · 2026-11-20 10:05 · → koordinator · ACK
Paket: 12 · Cevap: K-12-0001, K-GEN-0030
GOREV alındı; lease `ffcore-isci-a-12` ACTIVE. Worktree `.worktrees/feat/12-kurulum` açıldı, dal `feat/12-kurulum`; baz main **a60228d** (brief'teki 57f3590'dan sonra yalnız state commit'leri: oturum kaydı). Zorunlu okuma tamam; plan/19, deploy/offline, C16/C5 ve FOLLOWUP 35/46/66/82/95 okunuyor. Sıradaki: PLANNED. PLAN-ONAY gelmeden kod yok.

### A-12-0002 · 2026-11-20 10:45 · → koordinator · DURUM
Paket: 12 · Cevap: K-12-0001 · Durum: PLANNED
Ayrıntı: `state/pr/12.md` (bulunan semboller, 12 dilim, D1-D6, S1-S5, felsefe, test planı). Özet:
**Önemli bulgu:** `core/egress.py` `SafeOutboundClient` `trust_env=False` + IP pinli → backend'e `HTTPS_PROXY` etkisiz; `ffcore_audit_ensure_partition` SECURITY DEFINER değil ve retention audit bölümünü DROP ediyor → düz DML'li `ffcore_app` ile backend açılamaz (46 yalnız deploy ile kapanmaz); 95 için apt yetmez, tools `uv sync` de PyPI ister.
**PR bölme:** 12-1 (backend'siz, triage ile paralel): egress overlay+Squid+`internal` ağ+LiteLLM proxy+test-int, TLS nginx overlay (iç dinleyici + yalnız `/channels/teams/messages` dış), FOLLOWUP 35 (`scripts/compose_preflight.py`), 82, 66, smoke ekleri, veri-isleme.md. 12-2 (triage merge sonrası): backup/restore+test-int, vLLM overlay, 46 (initdb rol + `alembic 12_0001` SECURITY DEFINER + retention_job), 95, donanim.md, kurulum.md + kurulum-kapali-ag.md (rehber en sona: her komut teslim edilen parçalara karşı denenir).
**Kararlar (önerilen):** D1 **A Squid** (B tinyproxy, C yalnız nftables red); D2 **A nginx** (B Caddy otomatik ACME = gizli davranış, C yalnız belge); D3 **A** egress profilinde backend dış çağrıları ağ düzeyinde kapalı, backend proxy desteği ayrı küçük PR + FOLLOWUP (B 12'de egress.py, C16 dışı C red); D4 **A** preflight fail-loud (B sarmalayıcı, C overlay birleştirme); D5 **A** `APP_DB_*` boşsa sahip rol ama llmaas preflight'ta kırmızı (B `:?` zorunlu her yığını kırar, C yalnız belge); D6 **A** make/curl base katmana + `UV_INDEX_URL`/wheel dizini (B kısmi, C yalnız belge).
**Sorular:** S1 12-2 backend dokunuşu (`alembic/versions/12_0001`, `retention_job.py`, `backend/Dockerfile`) izni ve sırası; S2 `scripts/smoke.py` + yeni `scripts/compose_preflight.py` touch-zone'da mı; S3 `.env.test` eki; S4 docs içerik İngilizce, adlar brief'teki gibi (mevcut düzen); S5 squid/nginx çekme, vLLM yalnız manifest digest (çekilmez).
PLAN-ONAY bekliyorum; kod yok.

### A-12-0003 · 2026-11-20 11:10 · → koordinator · YIGIN-AC
Paket: 12 · Cevap: K-12-0002 · Yigin: ffcore-12
PLAN-ONAY alındı (K-12-0002), 12-1 başladı. Yığın `ffcore-12` (18550/13550; ek deneme portu 18551-18559). İlk koşu: Docker `internal: true` ağında yayınlanan portun davranışı (egress tasarımı için, tek nginx konteyneri). Not: imaj çekiminden sonra `docker run --rm` ile iki kısa imaj yoklaması (squid sürümü) bu mesajdan önce koştu, yığın açmadı.

### A-12-0004 · 2026-11-20 11:20 · → koordinator · KARAR-GEREK
Paket: 12 · Cevap: K-12-0002
12-1 kapısında (`state/evidence/12-1-gate.log`) `tests/contract/test_06b2_reserved_hosts.py::test_06b2_reserved_hosts_cover_compose` kırmızı: compose'daki her servis adı `backend/ffcore/services/external_config.py` `RESERVED_HOSTS` içinde olmalı (dış agent'ın hedefi olamaz, 06b-2 MINOR-1); yeni `egress-proxy` ve `tls-proxy` yok. Bu gerçek bir güvenlik koşulu (dış agent URL'si proxy'yi gösterirse SSRF yolu).
**A (önerilen):** 12-1'de `RESERVED_HOSTS`'a iki ad eklenir (backend'e tek satırlık additive dokunuş, `backend/ffcore/services/external_config.py`; triage bu dosyaya dokunmuyorsa çakışma yok). **B:** servis adları sözleşmedeki adlardan birine (ör. `litellm-egress`) çevrilmez, test 12-2'ye (triage sonrası) ertelenir; 12-1 kırmızı testle PR-HAZIR olamaz. **C:** test, 12 overlay'lerini hariç tutar: güvenlik koşulunu zayıflatır, red.
Ayrıca test-int Docker hatasıyla (exit 125, "error waiting for container", %89'da) yarıda kesildi; 07/08/09'da F/E var, aynı anda ffcore-trj test-int koşuyordu. Nedeni araştırıyorum (kaynak çakışması mı, 12 kaynaklı mı); sonucu DURUM ile yazacağım. Lint: 4 E501 (benim dosyalarım), düzeltiliyor.

### A-12-0005 · 2026-11-20 12:15 · → koordinator · YIGIN-KAPA
Paket: 12 · Cevap: K-12-0003 · Yigin: ffcore-12
`down -v` yapıldı; ffcore-12 konteyner/volume/ağ 0 (doğrulandı). Kapı r2 (`state/evidence/12-1-gate-r2.log`, HEAD fc688b0): lint 0, alembic heads tek (04b_0001), `make test` llmaas 2006 + airgap 2006 geçti, smoke geçti; **test-int yine exit 125** ("error waiting for container", 12:04:13). Aynı saniye rv yığınının (`followup-triage-1-r1-rv-test-int.log`) ve 11:05:36 trj'nin logunda da var: makine genelinde olay, 12 kaynaklı değil (ENV-209 ailesi).

### A-12-0006 · 2026-11-20 12:16 · → koordinator · SORU
Paket: 12 · Cevap: -
ENV-209 kuralına göre tam test-int için sıra istiyorum (rv test-int şu an koşuyor). Sıra gelince: yığın ffcore-12 tek başına, test-int ayrık konteynerde (`compose run -d` + `docker wait`, CLI bağlantısı koparsa test sürsün) + smoke; ardından PR-HAZIR 12-1. Sıra bana gelince YIGIN-AC ile başlarım; "başla" mesajını bekliyorum.
