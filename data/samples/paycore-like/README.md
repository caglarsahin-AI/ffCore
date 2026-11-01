# PayCore benzeri raw-staging ağacı (19)

Tamamen sentetik. Gerçek PayCore verisi, kişi adı ya da kurum belgesi yok. `ingest-raw`'ın
staging sözleşmesini (dosya + `<dosya>.meta.json`) ve sınırlarını yerelde göstermek için:

- `raw/confluence/DEMO/1001.md`: sentetik e-posta, telefon ve TCKN (maskeleme kanıtı; değerler 08-lite
  testlerinin sentetik örnekleri).
- `raw/confluence/DEMO/1003.md`: ekli belge (`attachments`).
- `raw/confluence/DEMO/1004.md`: yalnız bağlantılı gezinti sayfası (Kapı 2 `boilerplate`).
- `raw/jira/PRSIM/PRSIM-1.txt`: PRSIM kaynağı; `prsim_requires_ner` ile reddedilir.

```bash
python -m ffcore.cli ingest-raw --project <p> --kb <kb> --raw-dir data/samples/paycore-like/raw \
  --acl analyst --sources confluence:DEMO jira:DEMO
```
