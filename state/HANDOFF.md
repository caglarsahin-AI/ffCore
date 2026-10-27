# Handoff Defteri

Paralel oturum düzeninde işçi bu şablonu kendi `state/kanal/<rol>.md` dosyasına `HANDOFF` mesajı olarak yazar; bu dosyaya yalnızca koordinatör dalga kapanışında özet arşivler. Tek oturum düzeninde işçi buraya yazar (en yeni üstte). "Devam edilecek" tek başına geçerli handoff değildir.

## Şablon

```
### <paket> · <işçi> · <tarih saat>
- Durum: (WORK_QUEUE'daki durum)
- Tam sonraki adım: (hangi dosyada hangi fonksiyon, hangi test)
- Değişen dosyalar: 
- Koşan testler / kalan testler:
- Kararlar ve varsayımlar:
- Blocker'lar: (BLOCKERS.md kayıt no)
- Commit edilmemiş durum: (var/yok; varsa ne)
- Branch ve son commit:
```

## Kayıtlar

(henüz yok)
