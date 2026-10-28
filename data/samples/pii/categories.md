# PII kategori kodları

`pii-100.jsonl` içindeki `category` kodlarının plan/08 kategori adlarıyla eşlemesi.
Kodlar kanonik listedir (İngilizce, Presidio uyumlu; FOLLOWUP-33, KARARLAR "08-lite kararları");
tek kaynak `backend/ffcore/guardrails/categories.py`, 08 testi iki listenin eşitliğini kanıtlar.
`default_on`: 08'in varsayılan politikasında açık. Kişi adı (`PERSON`) yalnızca bu sette ve
hafıza setinde geçer; adlar betikteki sabit uydurma havuzdandır (DECISION-24). plan/08'e göre kişi adı
varsayılan politikada `egress`'te `tokenize` edilir; buradaki `hayır` yalnızca genel açık listeyi gösterir.

| Kod | plan/08 adı | default_on |
|---|---|---|
| `TR_NATIONAL_ID` | TC kimlik | evet |
| `TR_PHONE` | TR telefon | evet |
| `TR_IBAN` | TR IBAN | evet |
| `TR_TAX_ID` | VKN | hayır |
| `TR_PLATE` | plaka | hayır |
| `TR_PASSPORT` | TR pasaport | hayır |
| `TR_ADDRESS` | TR adres | hayır |
| `PERSON` | kişi adı | hayır |
| `ORGANIZATION` | kurum adı | hayır |
| `LOCATION` | konum | hayır |
| `EMAIL_ADDRESS` | e-posta | evet |
| `CREDIT_CARD` | kart | evet |
| `CVV` | CVV | evet |
| `PIN` | PIN | evet |
| `GPS` | GPS | hayır |
| `MAC_ADDRESS` | MAC | hayır |
| `API_TOKEN` | API token | hayır |
| `PASSWORD` | şifre | hayır |
| `DATE_OF_BIRTH` | doğum tarihi | hayır |
