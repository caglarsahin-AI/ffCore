# Arşiv: test · FL

state/kanal/test.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### T-FL-0001 · 2026-10-30 11:55 · → koordinator · DURUM + sapma
Paket: fake-llm-tool-mode   Cevap: K-SEN-0025
- Kırmızı: 3 failed / 2 passed. Düşenler: tool_call üretimi, akış içinde tool_call, araç sonucundan sonra metin. Geçenler: tools'suz metin, chat değişmedi.
- Yeşil: 5/5 (host py3.12).
- tool-* modu hem tek cevapta hem akışta çalışıyor; runtime akış kullanıyor (adapters.py chat_stream). Sırasıyla: finish_reason tool_calls; araç sonucu gelince "hello " + ilk 50 karakter; tools yoksa "hello".
- Zorunlu argümanlar örnek değerle: ticket_id=tkt-001, body, sql (SELECT code FROM departments LIMIT 1), reason, query; diğerleri tipe göre.
- docs/gelistirme-ortami.md'ye tek paragraf.

SAPMA (gerekçeli): "LiteLLM yapılandırmasına tool-default sanal modeli" yapılmadı.
deploy/litellm/config.yaml'da model listesi yok ("Modeller LiteLLM veritabanında", store_model_in_db, C1). LiteLLM modelleri yalnız proje model kayıtlarından uzlaştırıcıyla yazılır. Statik bir kayıt C1'e aykırı olur, ayrıca gereksiz: upstream model_id tool-default olan bir proje modeli yeterli. LiteLLM openai/tool-default gönderir, fake tool-* moduna girer.
18 e2e seed'ine chat-tools → tool-default modeli eklenecek (e2e dalında). 10b-poc-2 de aynı yolu kullanır.
Lint ve make test iki profil koşuyor (yalnız tools konteyneri, servis yok).

### T-FL-0002 · 2026-10-30 12:04 · → koordinator · PR-HAZIR
Paket: fake-llm-tool-mode   Cevap: K-SEN-0025
fix/fake-llm-tool-mode @ cab06f1299e08750b5e739814c04d867b37b4749 (main 8622714 üstünde, tek commit, 3 dosya). Sınıf [A].
Kapılar:
- lint 0.
- airgap 644 passed.
- llmaas: ilk koşu 1 failed (test_04a_9d, FOLLOWUP-97, bu dalın dışında); tekrar 644 passed.
- 01 entegrasyonu NOT_RUN (yığın gerekir).
Sapma notu PR dosyasında: state/pr/fake-llm-tool-mode.md.
Sonraki iş: e2e dalında seed'e chat-tools (tool-default) ekleyip F3/F4/F11 araçlı testleri; bu dal merge olunca rebase.
