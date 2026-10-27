# FFCore

Kurumsal LLM platformu: model dışındaki her şey (kapı, bilgi tabanı, araçlar, agent'lar, koruma, izleme) kurum içinde. Ürün varsayılanı `llmaas` profili, ikincil `airgap`. Arayüz Türkçe, kod İngilizce. Ayrıntı PLAN.md.

## Okuma sırası

0. `FELSEFE.md` (geliştirme felsefesi, her kuralın üstünde) ve `handbook/FELSEFE_UYGULAMA.md` (FFCore'daki karşılığı; her PR planında üç felsefe sorusu)
1. `PLAN.md` (amaç, kısıtlar, profiller, mimari, ortak kurallar bölüm 5, paketler bölüm 7)
2. `KARARLAR.md` (brief'lerde yazmayan kararlar)
3. `handbook/INDEX.md` → en az `EXECUTION_HANDBOOK.md`, `CONTRACTS.md`, `SECURITY_AND_PERMISSIONS.md`, `TERMINOLOGY.md`
4. Çalışacağın paketin brief'i: `plan/NN-*.md` ve bağımlı paketlerin "Teslimatlar" bölümü
5. `state/WORK_QUEUE.md` (claim), `state/BLOCKERS.md`

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
- Türkçe metin yalnızca `frontend/messages/tr.json`; her ekran açık ve koyu temada.
- Terimler handbook/TERMINOLOGY.md'deki gibi; PayCore müşteridir, ürün FF ailesinindir.
- Belirsizlikte: PLAN → KARARLAR → CONTRACTS → brief sırasıyla bak; hâlâ belirsizse varsayımını PR notuna yaz, durma; kullanıcı kararı gerekiyorsa `state/BLOCKERS.md`'ye `DECISION-` kaydı.
- Paralel oturum düzeninde (handbook/MULTI_AGENT_PROTOCOL.md "Oturumlar arası iletişim"): `WORK_QUEUE`, `BLOCKERS` ve `KARARLAR`'ı yalnızca koordinatör yazar; diğer roller kendi `state/kanal/<rol>.md` dosyasına mesaj yazar. `state/` her zaman `C:\ai_paycore\ffcore\state\` mutlak yolundan kullanılır, worktree kopyasından değil.
- Oturum kapanmadan handoff: paralel düzende kendi kanalına `HANDOFF` mesajı, tek oturum düzeninde `state/HANDOFF.md`.

## Komutlar

`make up`, `make smoke`, `make lint`, `make test`, `make test-int`, `alembic heads` (handbook/ENVIRONMENT_AND_COMMANDS.md). Commit: Conventional Commits, İngilizce.
