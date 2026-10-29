# 18-ticket-desk r1 bağımsız inceleme

**İncelenen tam SHA:** `134f868301c1da5aa57671ef79a8b31dbc297336`  
**Baz:** `6f2a1ec`  
**Karar:** **ONAY**  
**Bulgular:** BLOCKER 0 · MAJOR 0 · MINOR 0

Baz diff'inde `state/**` değişikliği yoktur. İnceleme yalnız exact SHA'nın detached `.worktrees/review-18-ticket-desk-r1` ağacında yapıldı.

## Kapsam sonucu

- `ticket-desk` yalnız Compose `test` profilinde, host portu olmadan çalışıyor. `send_reply` yalnız süreç içi `sent` listesine kayıt yapıyor; uygulama kodunda outbound istemci veya dış çağrı yok.
- `/_calls`, `/_sent` ve `/_reset` yalnız test servisi içinde bulunuyor. Servis kurulum profiline girmiyor ve Compose dışına port yayımlamıyor.
- 05a zincirinde kayıt `auth_type=none`; gerçek MCP çağrısında `Authorization`, `X-On-Behalf-Of` ve `Cookie` ticket-desk'e gitmiyor. Yeni eylemler varsayılan kapalı/onaylı; `send_reply` açıldığında `needs_approval=true` korunuyor.
- `.env.test` iç host listesine yalnız `ticket-desk` eklendi. `.env.example` üretim değerine eklenmedi; yalnız test/üretim ayrımını açıklayan yorum eklendi.
- İki agent tanımı 06a `AgentDefinition` ile doğrulandı. Zehirli belge agent'ının `run_sql` eylemi insan onayına bağlı; sürüm agent'ı araçsız.
- 15 SQL negatif kaydının tamamı birleşik 05a doğrulayıcısında beklenen kodla reddedildi.
- FOLLOWUP-76 değişikliği performans niteliğini gevşetmiyor: CPU bütçesi `process_time` ile korunuyor; duvar saati yalnız 10× asılı kalma koruması. Aynı testler maskeleme ve sınırlı önizleme özelliklerini de doğrulamaya devam ediyor.
- Makefile ve geliştirme belgesi eklemeleri additive; mevcut `smoke` hedefi değiştirilmedi.

## Güvenlik turu

- **Kimlik:** ticket-desk `auth_type=none`; OBO, oturum çerezi ve authorization başlığı aktarılmıyor. Test zinciri başlık adlarını değerleri kaydetmeden doğruluyor.
- **ACL:** servis yalnız test ağında ve portsuz. Ürün tarafında araç kayıt/keşif/invoke yetkileri mevcut 05a ACL yolundan geçiyor; yeni bir yetki baypası eklenmedi.
- **Secret:** servis ayarı secret gerektirmiyor; `.env.example` üretim allowlist'ine ticket-desk değeri eklenmedi. Inspection kaydı header değerlerini değil yalnız adlarını tutuyor.
- **SQL:** örnek negatif setin 15/15 kaydı gerçek 05a doğrulayıcısında beklenen kodla, DB bağlantısından önce reddediliyor.
- **Egress:** `send_reply` dış çağrı yapmıyor; exact-SHA hedefli testler `--network none` konteynerinde geçti. Compose servisi yalnız kayıt yapıyor.
- **PII:** ticket yükleyici üreticiye ait `pii` cevap anahtarını servis verisinden çıkarıyor. `list_tickets` gövde/PII döndürmüyor. Test-only `/_sent` gönderilen gövdeyi senaryo doğrulaması için bellekte tutuyor; hosta yayımlanmıyor.
- **Log:** Uvicorn access log kapalı; çağrı kaydı süreç içi ve header değerlerini içermiyor. Ticket gövdesi, cevap veya kimlik stdout loguna yazılmıyor.

## Komutlar ve sonuçlar

| Komut / kontrol | Sonuç |
|---|---|
| Exact SHA ve `6f2a1ec` baz soy kontrolü | geçti |
| `git diff 6f2a1ec..134f868 -- state` | boş |
| Dış ağsız/read-only exact worktree: `pytest test_18td_server.py test_18td_sql_write_attempts.py test_08_cost.py -q` | 33 geçti; yalnız read-only pytest cache uyarısı |
| Dış ağsız/read-only exact worktree: sample unittest keşfi | 53 geçti, 5 opt-in PostgreSQL testi atlandı |
| 06a imajında `parse_definition` ile iki agent | ikisi de geçerli |
| Hedefli Ruff check / format check | geçti; 29 dosya biçimli |
| İşçi entegrasyon kanıtındaki tek skip'in kaynak incelemesi | `test_05a_models_few_shot_similarity`; `NOT_RUN: needs RUN_MODEL_TESTS=1` |

## NOT_RUN

- Tam iki profilli 583 test ve canlı Compose entegrasyon zinciri bu kısa turda bağımsız tekrar edilmedi; işçi kanıtları çapraz kontrol edildi ancak bağımsız geçiş sayılmadı.
- Sample paketindeki 5 gerçek PostgreSQL testi bağımsız koşuda `NOT_RUN` (`RUN_PG_TESTS=1` gerekir).
- 05a model benzerlik testi `NOT_RUN` (`RUN_MODEL_TESTS=1` ve gerçek model ağırlığı gerekir). Bu skip 18-ticket-desk testlerinden değildir.
- 06a main'e girmediği için kalıcı 06a sözleşme kapısı henüz yok; iki tanım mevcut 06a imajında tek seferlik doğrulandı.
