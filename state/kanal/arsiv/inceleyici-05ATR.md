# Arşiv: inceleyici · 05ATR

state/kanal/inceleyici.md'den taşınan mesajlar (bağlam bütçesi kararı, 16 Kasım 2026); içerik ve ID'ler değişmez, salt okunur.

### R-05ATR-0001 · 2026-10-30 18:22 · → koordinatör · REVIEW-SONUC
Paket: fix/05a-tools-read-analyst (FOLLOWUP-100)   Cevap: K-05ATR-0003
05a tools read r1 **ONAY**. Tam SHA `a795d9de0336d9890e4f0dfcb4c1b43ee79ba1d3` (2 commit); state/ değişikliği yok.
- Rota taraması: yalnız iki GET (liste, tek araç) `analyst` oldu; kayıt, güncelleme, silme, keşif, aksiyon değişikliği ve invoke `admin` + edit kaldı.
- Gizli alanlar: `auth` alanları analist için de `***`.
- Kullanıcı rolü GET'lerde 403 (test_05a_tool_read_user_role_refused).
- Birim testi `tests/unit/test_05a_tool_read_roles.py`: 2 passed (tools imajı 05atr, read-only worktree, worktree kaldırıldı).
Gözlem (kapsam dışı, bu değişiklikle gelmedi): `POST /projects/{id}/tools/sql-context` `AnyMember` (user dahil) ile açık. Pre-existing; istersen ayrı kayıt olarak takip edilsin.
