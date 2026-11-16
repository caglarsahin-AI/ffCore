# FFCore

Kurumsal yapay zekâ platformu: model dışındaki her şey (kapı, bilgi tabanı, araçlar, agent'lar, koruma, izleme) kurum içinde. Ürün varsayılanı `llmaas` profili, ikincil `airgap`. Uygulama (arayüz, API, `docs/`) İngilizce varsayılan, Türkçe yerel; kod İngilizce; proje belgeleri ve kanal Türkçe. Ayrıntı PLAN.md.

## Okuma sırası

**Zorunlu (her oturum, toplam ≤ 60 KB hedefi; bağlam bütçesi kararı 16 Kasım 2026):**

0. `FELSEFE.md` (her kuralın üstünde) ve `handbook/FELSEFE_UYGULAMA.md` (her PR planında üç felsefe sorusu)
1. Bu dosyanın kuralları; `handbook/MULTI_AGENT_PROTOCOL.md` (roller, kanal, tek yazar, arşiv); `handbook/SECURITY_AND_PERMISSIONS.md`
2. `KARARLAR.md` **İndeks** bölümü (tam maddeyi yalnız gerektiğinde, başlığıyla)
3. Çalışacağın paketin brief'i: `plan/NN-*.md`; bağımlı paketlerin yalnız "Teslimatlar" bölümü
4. `state/WORK_QUEUE.md`'de kendi satırın; `state/BLOCKERS.md` (yalnız açık kayıtlar); kendi kanalın ve koordinatör kanalının sana adresli son mesajları

**Gerektiğinde (ID ya da yolla):** `PLAN.md` (amaç, kısıtlar, profiller, mimari, ortak kurallar 5, paketler 7), `KARARLAR.md` tam maddeleri, `handbook/EXECUTION_HANDBOOK.md`, `CONTRACTS.md`, `TERMINOLOGY.md`, `ENVIRONMENT_AND_COMMANDS.md`, `CHANGE_CONTROL.md`, `state/arsiv/**` ve `state/kanal/arsiv/**` (kapalı kayıtlar ve MERGED paket mesajları; ID ile atıf burada bulunur), eski inceleme raporları.

## Bağlayıcı kısa kurallar

- Felsefe önce: bir karar FELSEFE.md ile çelişiyorsa dur ve işaret et; sessizce ihlal etme. Pozisyon al, gerekçesiyle savun. Kullanıcı kararı gereken her soruyu 2-3 birbirini dışlayan A/B/C seçeneğiyle sor; önerdiğin seçeneği önce ve açıkça işaretle, her seçeneğin etkisini yaz (META-01). Kod hakkında cümle kurmadan kaynağa bak; emin değilsen söyle; açık noktayı kendi başına kapatma.
- 80/20: çekirdek 8 özelliğe, hafızaya, kanala ya da kaynağa değer katmayan özellik eklenmez; platformun (LiteLLM, Langfuse, LangGraph, Postgres, arq) sunduğu yeniden inşa edilmez; "auto" seçim yok, açık tercih ve belirgin varsayılan.
- Kod yazmadan önce `state/WORK_QUEUE.md`'de claim; touch-zone dışına çıkma (handbook/MULTI_AGENT_PROTOCOL.md).
- Önce başarısız test, sonra en küçük dilim; her kabul kriteri bir testle kanıtlanır; kanıt PR açıklamasında (`handbook/templates/PR_SABLONU.md`).
- Donmuş sözleşmeler (handbook/CONTRACTS.md) yalnızca additive değişir; kırıcı değişiklik `BREAKING-` kaydı ve kullanıcı onayı ister.
- Değişiklik sınıfı PR başlığında `[A]`-`[D]` (handbook/CHANGE_CONTROL.md); C ve D kullanıcı onayı.
- Secret yazma, `.env` doldurma, dış sisteme bağlanma, üretim erişimi yok (handbook/SECURITY_AND_PERMISSIONS.md).
- Hasta ve kişi düzeyi kurum verisi platforma girmez; belge dışarı çıkmaz. PayCore LLM (`C:\ai_paycore\paycoreLLM`) canlı test yeri ve tüketicidir (PLAN 2d): `.env`, `data/**`, `eval/results/**` okunmaz; sunucuya bağlanılmaz; PayCore kodu kopyalanmaz, uzantıda kalır ya da C14 ile terfi eder.
- Profil farkı `if profile` dalı değil yapılandırma değeri; testler iki profille koşar.
- Fail-loud: sessiz fallback, kırpma, atlama yok; her red kayıtlı ve gerekçeli.
- UI metni yalnızca `frontend/messages/{en,tr}.json` (kaynak `en`, `tr` çeviri); kodda sabit metin yok; her ekran açık ve koyu temada.
- Terimler handbook/TERMINOLOGY.md'deki gibi; PayCore müşteridir, ürün FF ailesinindir.
- Belirsizlikte: PLAN → KARARLAR → CONTRACTS → brief sırasıyla bak; hâlâ belirsizse varsayımını PR notuna yaz, durma; kullanıcı kararı gerekiyorsa `state/BLOCKERS.md`'ye `DECISION-` kaydı.
- Paralel oturum düzeninde (handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim"): `WORK_QUEUE`, `BLOCKERS` ve `KARARLAR`'ı yalnızca koordinatör yazar; diğer roller kendi `state/kanal/<rol>.md` dosyasına mesaj yazar. `state/` her zaman `C:\ai_paycore\ffcore\state\` mutlak yolundan kullanılır, worktree kopyasından değil.
- Oturum kapanmadan handoff: paralel düzende kendi kanalına `HANDOFF` mesajı, tek oturum düzeninde `state/HANDOFF.md`.

## Komutlar

`make up`, `make smoke`, `make lint`, `make test`, `make test-int`, `alembic heads` (handbook/ENVIRONMENT_AND_COMMANDS.md). Commit: Conventional Commits, İngilizce.
