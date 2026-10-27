# 07. Onay kuyruğu [FFCore Agents]

**Bağımlılık:** 06a, 03b. **Süre:** 1,5 gün. **Dalga:** 5. **PoC:** evet.

## Amaç

`needs_approval` işaretli araç çağrılarında duran run'ların bir insan tarafından görülüp onaylanması ya da reddedilmesi; kimin, ne zaman, neden karar verdiğinin kaydı; zaman aşımı.

## Kapsam

### Veri modeli

- `approvals(id, run_id, project_id, tool_key, action_name, arguments jsonb, reason_from_model, status: pending|approved|rejected|expired, requested_at, expires_at, resolved_at, resolved_by, resolution_note, assigned_role)`
- `assigned_role`: agent tanımındaki `approval.assign_to` (06 şemasında tanımlı, varsayılan `analyst` (A3: `developer` PoC'de atanmaz)); o rol ve üstü, yalnızca `access=edit` ise karar verebilir. Salt-okunur kullanıcı onay listesini ve detayını görür, karar düğmeleri pasiftir. (R6.1) `user` rolü (17) hiçbir zaman onay veremez; `assign_to` değeri `analyst`'ten düşük olamaz (şema doğrulaması).

### Akış

1. 06'daki `tools` düğümü interrupt'a girince `approvals` kaydı açılır, run `waiting_approval` olur, SSE'de `approval_required` event'i gider.
2. Karar: `POST /approvals/{id}/approve` ya da `/reject` (not zorunlu değil, ret için önerilir). Karar `runs.resume` ile grafı sürdürür; ret durumunda modele "araç çağrısı reddedildi: {not}" sonucu verilir.
3. Zaman aşımı: `APPROVAL_TTL_MIN` (varsayılan 60); `arq` cron işi (C9) `expired` yapar, run `failed` ile kapanır, kullanıcıya mesaj döner.
4. Liste ve sayaç: `GET /approvals?status=pending&project_id=` ve `GET /approvals/count` (önyüz rozeti için).
5. Bildirim (R6.2): PoC'de UI rozeti ve SSE `approval_required` olayı yeter; e-posta 03c'deki ortak `notification_settings` SMTP ayarından gönderilir (03c geldiğinde; ayrı `.env` yok). Bekleyen onay `APPROVAL_ALERT_AGE_MIN` (varsayılan 30) dakikayı aşınca 03c uyarı sistemine `approval_pending_age` olayı düşer. E-postadaki link onay sayfasına gider. **Onay yalnızca oturum açmış, `access=edit` ve rolü yeterli kullanıcıyla verilir (C4):** API anahtarıyla `/approvals/{id}/approve` 403; e-posta linkinden doğrudan onay yok. Tek istisna 15'teki doğrulanmış kanal kimliği (`channel_identities.verified_at` dolu ve eşlenen kullanıcı yetkiliyse düğmeli mesaj onayı; C14).
6. Onay yorgunluğu önlemi: aynı run içinde aynı aksiyon aynı argümanlarla tekrar istenirse ikinci kez sorulmaz (`approvals` üzerinde hash eşleşmesi); bu durum `run_events`'e `approval_reused` olarak yazılır (N19, sessiz değil).

## Teslimatlar

- Migration, router, servis, zamanlayıcı işi, e-posta şablonu (Türkçe).
- Testler: onay -> devam; ret -> model reddi görür; TTL -> expired ve run failed; yetkisiz rol 403.

## Kabul kriterleri

- Bekleyen onay 60 dakika sonra `expired` olur ve run kapanır.
- Analyst rolü `assigned_role=developer` olan onayı veremez.
- Her karar audit'e düşer (`approval.approved`, aktör, argümanlar).
- SSE istemcisi onay sonrası kaldığı yerden token almaya devam eder.

## Teknik notlar

- Argümanlar önyüzde okunabilir biçimde gösterilir (örn. SQL metni vurgulu); 08'in PII maskesi burada da uygulanır.
- Slack/Teams bildirimi kapsam dışı; webhook çıkışı 03c `notification_settings.default_webhook_url` üzerinden ve `core/egress.py` ile gider; ayrı env değişkeni yok (ARCH-09).

## Kapsam dışı

Onay politikası motoru (koşullu onay: "tutar > X"); ilk sürümde aksiyon bazlı evet/hayır.
