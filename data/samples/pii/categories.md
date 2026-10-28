# PII kategori kodları

`pii-100.jsonl` içindeki `category` kodlarının plan/08 kategori adlarıyla eşlemesi.
`default_on`: 08'in varsayılan politikasında açık. Kişi adı (`PERSON`) yalnızca bu sette ve
hafıza setinde geçer; adlar betikteki sabit uydurma havuzdandır (DECISION-24). plan/08'e göre kişi adı
varsayılan politikada `egress`'te `tokenize` edilir; buradaki `hayır` yalnızca genel açık listeyi gösterir.

| Kod | plan/08 adı | default_on |
|---|---|---|
| `TC_KIMLIK` | TC kimlik | evet |
| `TR_TELEFON` | TR telefon | evet |
| `TR_IBAN` | TR IBAN | evet |
| `VKN` | VKN | hayır |
| `PLAKA` | plaka | hayır |
| `TR_PASAPORT` | TR pasaport | hayır |
| `TR_ADRES` | TR adres | hayır |
| `PERSON` | kişi adı | hayır |
| `KURUM_ADI` | kurum adı | hayır |
| `KONUM` | konum | hayır |
| `EPOSTA` | e-posta | evet |
| `KART` | kart | evet |
| `CVV` | CVV | evet |
| `PIN` | PIN | evet |
| `GPS` | GPS | hayır |
| `MAC` | MAC | hayır |
| `API_TOKEN` | API token | hayır |
| `SIFRE` | şifre | hayır |
| `DOGUM_TARIHI` | doğum tarihi | hayır |
