# 18 F2 aşama 3 · review r1 (statik)

**Tam SHA:** 7e5bf8ca35a4dd8a56a7405a9b92dca61df04d39 (e19f0e5 + 1 commit; 2 dosya: `tests/e2e/scenarios/seed.py`, `tests/e2e/scenarios/test_18_f2_approvals.py`) · **Baz:** 6deb0c1 · **state/ değişikliği:** 0 (merge-base kontrolü)
**Karar:** ONAY (statik). Koşu bağımsız yapılmadı: K-SEN-0050 yığınsız istedi. Koşu kanıtı PR'da (seed 0/0, üç temiz yığın, F2 aşama 3 geçti, f4_1c yeşil); bu kanıt bağımsız doğrulanmadı.

## Okunanlar

- `test_18_f2_8`: kuyrukta bekleme; `ticket-desk` henüz gönderim yapmamış (`/_sent` boş); okuma erişimli admin ONAY'ı göremez (`can_decide: false`) ve onaylamaya çalışınca 403. Negatif kapsam burada.
- `test_18_f2_9`: konsol onayı gönderimi tetikliyor; yeniden onay 409 (bir kez karar). Pozitif ve tekrar-koruma kapsamı.
- `test_18_f2_10`: ret, gönderimi engelliyor ve modele ret gerekçesi ulaşıyor (fake-llm isteği). Ret yolu kapsamı.
- `test_18_f2_10b`: `skip` ile NOT_RUN gerekçesi ("gerçek model gerekir") açık; geçti sayılmıyor.
- Fixture'lar (`login`, `fake_llm`, `settle`, `stream`, `run_events`) `conftest.py`'de var.
- `seed.py`: hedef projenin `default` politikasında secrets kuralı yalnız log (enforce değil). Gerekçe (kodda belgelenmiş): kodlanmış poison içeriği (base64) sır olarak algılanıyor ve tüm cevapları bloke ediyor (K-SEN-0048 A, FOLLOWUP-107). Bu, yalnız test seed'inde; üretim politikasını değiştirmiyor. Kabul: test amaçlı bilinçli gevşetme, kodda ve PR'da açık yazılı.

## Bulgular

Bloklayıcı yok. Not: seed'deki log-only secrets kuralı test stack'inde bilinçli bir zayıflatma; FOLLOWUP-107 kapanınca geri alınmalı (kayıtta görünmeli).

## Kalan riskler

- Koşu bağımsız doğrulanmadı (yığınsız istek). `test_18_f2_10b` NOT_RUN.
