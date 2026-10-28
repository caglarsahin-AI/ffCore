"""Turkish PII test set (plan/13 item 4b, consumed by 08; C18).

Category codes map to plan/08's Turkish category names (see pii/categories.md).
All values are synthetic; numbers with a checksum (TC kimlik, VKN, IBAN, card) are
generated valid so 08's checksum recognisers can be tested, and negatives include
look-alike numbers with a wrong checksum. E-mail local parts are not names.

Person names (PERSON, DECISION-24 = A) come only from the fixed fictional pool below:
common first names combined with made-up surnames, so no combination is meant to
match a real person. Names appear only in pii/ and memory/ (test_13a_9 proves it).
"""

import json
import random
from pathlib import Path

from . import write_text

TOTAL = 100
NAME_SLOTS = 20  # sentences with a PERSON span (DECISION-24)

# Fictional name pool (DECISION-24). Surnames are invented compounds; first names
# avoid words used elsewhere in the samples (streets, passwords).
FIRST_NAMES = [
    "Elif",
    "Kerem",
    "Zeynep",
    "Burak",
    "Selin",
    "Emre",
    "Derya",
    "Oğuz",
    "Melis",
    "Tolga",
    "Ceren",
    "Arda",
    "İpek",
    "Kaan",
    "Gizem",
    "Barış",
]
LAST_NAMES = [
    "Akçamdere",
    "Yelkentaş",
    "Gökçeoba",
    "Tuzlaçay",
    "Sedirtepe",
    "Kumbayır",
    "Narlıkaya",
    "Ilgınçeşme",
    "Çınaroba",
    "Kestanelik",
    "Mavisuyu",
    "Defnedere",
]

# code -> plan/08 category name; "default_on" = enabled in 08's default policy
CATEGORIES = {
    "TR_NATIONAL_ID": ("TC kimlik", True),
    "TR_PHONE": ("TR telefon", True),
    "TR_IBAN": ("TR IBAN", True),
    "TR_TAX_ID": ("VKN", False),
    "TR_PLATE": ("plaka", False),
    "TR_PASSPORT": ("TR pasaport", False),
    "TR_ADDRESS": ("TR adres", False),
    "PERSON": ("kişi adı", False),
    "ORGANIZATION": ("kurum adı", False),
    "LOCATION": ("konum", False),
    "EMAIL_ADDRESS": ("e-posta", True),
    "CREDIT_CARD": ("kart", True),
    "CVV": ("CVV", True),
    "PIN": ("PIN", True),
    "GPS": ("GPS", False),
    "MAC_ADDRESS": ("MAC", False),
    "API_TOKEN": ("API token", False),
    "PASSWORD": ("şifre", False),
    "DATE_OF_BIRTH": ("doğum tarihi", False),
}


# --- value generators (all synthetic) and their validators -------------------


def tc_checksum(first9: str) -> str:
    d = [int(c) for c in first9]
    d10 = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    d11 = (sum(d) + d10) % 10
    return f"{d10}{d11}"


def tc_valid(s: str) -> bool:
    return len(s) == 11 and s.isdigit() and s[0] != "0" and s[9:] == tc_checksum(s[:9])


def gen_tc(rng: random.Random) -> str:
    first9 = str(rng.randint(1, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(8))
    return first9 + tc_checksum(first9)


def gen_tc_invalid(rng: random.Random) -> str:
    tc = gen_tc(rng)
    return tc[:10] + str((int(tc[10]) + 1 + rng.randint(0, 8)) % 10)


def vkn_check(first9: str) -> str:
    total = 0
    for i, c in enumerate(first9):
        tmp = (int(c) + (9 - i)) % 10
        v = (tmp * 2 ** (9 - i)) % 9
        if tmp != 0 and v == 0:
            v = 9
        total += v
    return str((10 - total % 10) % 10)


def gen_vkn(rng: random.Random) -> str:
    first9 = "".join(str(rng.randint(0, 9)) for _ in range(9))
    return first9 + vkn_check(first9)


def iban_valid(s: str) -> bool:
    raw = s.replace(" ", "")
    moved = raw[4:] + raw[:4]
    digits = "".join(str(int(ch, 36)) for ch in moved)
    return raw.startswith("TR") and len(raw) == 26 and int(digits) % 97 == 1


def gen_iban(rng: random.Random) -> str:
    bban = f"99{rng.randint(100, 999)}" + "0" + "".join(str(rng.randint(0, 9)) for _ in range(16))
    digits = "".join(str(int(ch, 36)) for ch in bban + "TR00")
    check = 98 - int(digits) % 97
    raw = f"TR{check:02d}{bban}"
    return " ".join(raw[i : i + 4] for i in range(0, len(raw), 4))


def luhn_valid(s: str) -> bool:
    digits = [int(c) for c in s if c.isdigit()]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def gen_card(rng: random.Random) -> str:
    prefix = rng.choice(["411111", "555555", "400000"])  # well-known test BIN ranges
    body = prefix + "".join(str(rng.randint(0, 9)) for _ in range(9))
    for last in range(10):
        if luhn_valid(body + str(last)):
            num = body + str(last)
            return " ".join(num[i : i + 4] for i in range(0, 16, 4))
    raise AssertionError("unreachable")


def gen_phone(rng: random.Random) -> str:
    op = rng.choice(["501", "505", "532", "533", "542", "545", "552", "555"])
    n = "".join(str(rng.randint(0, 9)) for _ in range(7))
    return rng.choice(
        [
            f"0{op} {n[:3]} {n[3:5]} {n[5:]}",
            f"+90 {op} {n[:3]} {n[3:]}",
            f"0{op}{n}",
            f"({op}) {n[:3]}-{n[3:]}",
        ]
    )


PLATE_LETTERS = "ABCDEFGHJKLMNPRSTUVYZ"
STREETS = ["Lale", "Menekşe", "Akasya", "Çınar", "Gül", "Papatya", "Ihlamur", "Defne"]
DISTRICTS = [
    ("Keçiören", "Ankara"),
    ("Kadıköy", "İstanbul"),
    ("Bornova", "İzmir"),
    ("Nilüfer", "Bursa"),
    ("Konyaaltı", "Antalya"),
    ("Tepebaşı", "Eskişehir"),
]
ORGS = [
    "Yıldızkent Lojistik A.Ş.",
    "Bereket Gıda Ltd. Şti.",
    "Mavikule Danışmanlık A.Ş.",
    "Kırlangıç Yapı A.Ş.",
    "Tavlan Medikal Teknik A.Ş.",
    "Ekinsoy Tarım Kooperatifi",
]


def tr_upper(s: str) -> str:
    return s.replace("i", "İ").replace("ı", "I").upper()


def tr_lower(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def gen_person(rng: random.Random) -> str:
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    form = rng.choice(["plain", "plain", "plain", "two_first", "upper", "lower", "surname_first"])
    if form == "two_first":
        return f"{first} {rng.choice([n for n in FIRST_NAMES if n != first])} {last}"
    if form == "upper":
        return tr_upper(f"{first} {last}")
    if form == "lower":
        return tr_lower(f"{first} {last}")
    if form == "surname_first":
        return f"{tr_upper(last)} {first}"
    return f"{first} {last}"


def gen_value(code: str, rng: random.Random) -> str:
    if code == "PERSON":
        return gen_person(rng)
    if code == "TR_NATIONAL_ID":
        return gen_tc(rng)
    if code == "TR_PHONE":
        return gen_phone(rng)
    if code == "TR_IBAN":
        return gen_iban(rng)
    if code == "TR_TAX_ID":
        return gen_vkn(rng)
    if code == "TR_PLATE":
        province = rng.randint(1, 81)  # draw order kept: province, letters, number
        letters = "".join(rng.choice(PLATE_LETTERS) for _ in range(rng.randint(1, 3)))
        return f"{province:02d} {letters} {rng.randint(10, 9999)}"
    if code == "TR_PASSPORT":
        return rng.choice("UZS") + "".join(str(rng.randint(0, 9)) for _ in range(8))
    if code == "TR_ADDRESS":
        district, city = rng.choice(DISTRICTS)
        return (
            f"{rng.choice(STREETS)} Mah. {rng.choice(STREETS)} Sok. No: {rng.randint(1, 120)} D: "
            f"{rng.randint(1, 30)} {district}/{city}"
        )
    if code == "ORGANIZATION":
        return rng.choice(ORGS)
    if code == "LOCATION":
        return rng.choice([d for pair in DISTRICTS for d in pair])
    if code == "EMAIL_ADDRESS":
        local = rng.choice(["destek", "bilgi", "muhasebe", "satinalma", "kullanici", "rapor"])
        number = rng.randint(10, 9999)
        return f"{local}{number}@{rng.choice(['ornek.com.tr', 'example.com', 'ornek.org'])}"
    if code == "CREDIT_CARD":
        return gen_card(rng)
    if code == "CVV":
        return f"{rng.randint(0, 999):03d}"
    if code == "PIN":
        return f"{rng.randint(0, 9999):04d}"
    if code == "GPS":
        return f"{rng.uniform(36, 42):.4f}, {rng.uniform(26, 45):.4f}"
    if code == "MAC_ADDRESS":
        return ":".join(f"{rng.randint(0, 255):02X}" for _ in range(6))
    if code == "API_TOKEN":
        return "tok_" + "".join(rng.choice("0123456789abcdef") for _ in range(32))
    if code == "PASSWORD":
        return (
            rng.choice(["Bahar", "Deniz", "Kartal", "Yonca"])
            + str(rng.randint(1000, 9999))
            + rng.choice("!?.*")
        )
    if code == "DATE_OF_BIRTH":
        return f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1950, 2005)}"
    raise ValueError(code)


# --- sentence templates: {CODE} placeholders become labelled spans ---------------

TEMPLATES = {
    "TR_NATIONAL_ID": [
        "Başvuru formunda TC kimlik numarası {TR_NATIONAL_ID} olarak yazılmış.",
        "Kimlik no: {TR_NATIONAL_ID}, lütfen sisteme girin.",
        "{TR_NATIONAL_ID} numaralı kayıt için randevu oluşturuldu.",
        "T.C. {TR_NATIONAL_ID} kimlik numaralı hasta yakını bilgi istedi.",
        "tc kimlik no {TR_NATIONAL_ID}",
        "Sigortalının kimlik numarasını ({TR_NATIONAL_ID}) kontrol eder misin?",
    ],
    "TR_PHONE": [
        "Bana {TR_PHONE} numarasından ulaşabilirsiniz.",
        "Geri arama için telefon: {TR_PHONE}",
        "Acil durumda {TR_PHONE} aranacak.",
        "Cep numarası {TR_PHONE}, mesaj atılabilir.",
        "tel {TR_PHONE} whatsapp da var",
        "Santral meşgulse doğrudan {TR_PHONE} numarasını deneyin.",
    ],
    "TR_IBAN": [
        "Ödemeyi {TR_IBAN} IBAN'ına yapın.",
        "Hesap bilgisi: {TR_IBAN}",
        "iban {TR_IBAN} alıcı firma hesabı",
        "İade tutarı {TR_IBAN} numaralı hesaba aktarılacak.",
        "Fatura üzerindeki IBAN {TR_IBAN} doğru mu?",
    ],
    "TR_TAX_ID": [
        "Firmanın vergi kimlik numarası {TR_TAX_ID}.",
        "VKN: {TR_TAX_ID} olan tedarikçi kaydı güncellendi.",
        "Faturada {TR_TAX_ID} vergi numarası yazıyor.",
        "vergi no {TR_TAX_ID} ile e-fatura kesildi",
    ],
    "TR_PLATE": [
        "Servis aracının plakası {TR_PLATE}.",
        "{TR_PLATE} plakalı ambulans otoparka girdi.",
        "Otopark kaydında {TR_PLATE} görünüyor.",
    ],
    "TR_PASSPORT": [
        "Pasaport numarası {TR_PASSPORT} olan ziyaretçi kayıt yaptırdı.",
        "Yurt dışı başvurusu için pasaport: {TR_PASSPORT}",
        "pasaport no {TR_PASSPORT} vize formuna eklendi",
    ],
    "TR_ADDRESS": [
        "Teslimat adresi: {TR_ADDRESS}",
        "Fatura {TR_ADDRESS} adresine gönderilsin.",
        "Ev adresim {TR_ADDRESS} olarak güncellensin.",
        "Kargo yerine elden teslim: {TR_ADDRESS}",
    ],
    "ORGANIZATION": [
        "{ORGANIZATION} ile yapılan görüşme ertelendi.",
        "Teklif {ORGANIZATION} tarafından gönderildi.",
        "Sevkiyatı {ORGANIZATION} üstlenecek.",
    ],
    "LOCATION": [
        "Toplantı {LOCATION} şubesinde yapılacak.",
        "Numune {LOCATION} deposundan alınacak.",
        "Ekip yarın {LOCATION} bölgesinde olacak.",
    ],
    "EMAIL_ADDRESS": [
        "Raporu {EMAIL_ADDRESS} adresine gönderin.",
        "İletişim: {EMAIL_ADDRESS}",
        "Şifre sıfırlama bağlantısı {EMAIL_ADDRESS} adresine gitti.",
        "Toplantı daveti {EMAIL_ADDRESS} hesabından geldi.",
        "mail adresim {EMAIL_ADDRESS}",
        "Yanıtı {EMAIL_ADDRESS} adresine CC'leyin.",
    ],
    "CREDIT_CARD": [
        "Kart numarası {CREDIT_CARD} ile ödeme denendi.",
        "Ödeme için {CREDIT_CARD} kartını kullanın.",
        "kartım {CREDIT_CARD} limit doldu mu bakar mısın",
        "Ekstrede {CREDIT_CARD} kartına ait harcama var.",
    ],
    "CVV": ["Kartın arkasındaki CVV {CVV}.", "Güvenlik kodu (CVV): {CVV}"],
    "PIN": ["Kartın PIN kodu {PIN}, kimseyle paylaşmayın.", "Kasa için PIN: {PIN}"],
    "GPS": ["Ambulansın son konumu {GPS}.", "Saha ekibinin koordinatı: {GPS}"],
    "MAC_ADDRESS": [
        "Cihazın MAC adresi {MAC_ADDRESS}.",
        "Ağa {MAC_ADDRESS} adresli bilinmeyen cihaz bağlandı.",
    ],
    "API_TOKEN": [
        "Entegrasyon anahtarı {API_TOKEN} olarak tanımlandı.",
        "Authorization başlığında {API_TOKEN} gönderiliyor.",
    ],
    "PASSWORD": ["Yeni şifrem {PASSWORD}, unutmamak için yazıyorum.", "Geçici şifre: {PASSWORD}"],
    "DATE_OF_BIRTH": [
        "Doğum tarihi {DATE_OF_BIRTH} olarak kayıtlı.",
        "Doğum tarihim {DATE_OF_BIRTH}.",
        "d.t. {DATE_OF_BIRTH}, yaş sınırı kontrol edilsin",
    ],
}
MULTI = [
    "Kimlik no {TR_NATIONAL_ID}, telefon {TR_PHONE}, e-posta {EMAIL_ADDRESS}.",
    "{ORGANIZATION} adına ödeme {TR_IBAN} hesabına, vergi no {TR_TAX_ID}.",
    "Kart {CREDIT_CARD}, CVV {CVV}, son kullanma bilgisi formda.",
    "Teslimat {TR_ADDRESS}, irtibat {TR_PHONE}.",
    "Sunucu {MAC_ADDRESS} cihazından {API_TOKEN} anahtarıyla bağlandı.",
    "{DATE_OF_BIRTH} doğumlu başvuru sahibinin kimlik no'su {TR_NATIONAL_ID}.",
    "Sevkiyat {LOCATION} deposundan {TR_PLATE} plakalı araçla çıktı.",
    "PIN {PIN} ve şifre {PASSWORD} aynı not kâğıdında yazıyordu.",
]
# PERSON sentences (DECISION-24); titles stay outside the span. No gendered honorifics
# (Bey/Hanım) or suffixes after the name: the pool does not track gender or vowel harmony.
NAME_SENTENCES = [
    "Hasta {PERSON} 12 numaralı yatağa yatırıldı.",
    "{PERSON} isimli danışanın randevusu perşembeye alındı.",
    "Dr. {PERSON} bugün nöbetçi.",
    "Raporu {PERSON} hazırladı, onay bekliyor.",
    "Teslim alan: {PERSON}",
    "{PERSON} ile görüşme saat 15.00'te.",
    "hasta adı {PERSON} dosya no 4471",
    "Başvuru sahibi {PERSON}, TC kimlik no {TR_NATIONAL_ID}.",
    "{PERSON} ve {PERSON} aynı vardiyada çalışıyor.",
    "Refakatçi {PERSON} için kart çıkarılsın.",
    "{PERSON} adlı hastanın tahlil sonuçları çıktı.",
    "İmza: {PERSON}, Satın Alma Birimi",
    "Faturadaki muhatap {PERSON} olarak düzeltilsin.",
    "{PERSON} ile {EMAIL_ADDRESS} adresinden iletişime geçildi.",
    "Taburcu listesinde {PERSON} adı da var.",
    "Ameliyat onam formunu {PERSON} imzaladı.",
    "Sayın {PERSON}, başvurunuz alınmıştır.",
    "{PERSON} telefonla aradı: {TR_PHONE}",
    "nöbet değişimi {PERSON} -> {PERSON}",
    "Ziyaretçi kaydı: {PERSON}, {DATE_OF_BIRTH} doğumlu.",
]
# Negatives: look-alikes that must NOT be labelled (no entities)
NEGATIVES = [
    "Sözleşmenin 10. maddesine göre fesih bildirim süresi 90 gündür.",
    "Sipariş numarası {TC_INVALID} olan kayıt kapatıldı.",
    "Bu ay kardiyoloji bölümünde doluluk oranı yüzde 87 oldu.",
    "Ventilatör CHZ-00412 envanter koduyla kayıtlı.",
    "Toplantı 14.30'da başlayacak, gündem üç maddeden oluşuyor.",
    "Fatura tutarı 1.212.500 TL, vadesi 45 gün.",
    "Lütfen numaramı geri yaz dediğinde sistem hiçbir şey kaydetmedi.",
    "Referans kodu {TC_INVALID} ile başvuru takip edilebilir.",
    "Kit lot numarası KIT-014, raf ömrü 12 ay.",
    "Sistem erişilebilirliği geçen ay %99,7 oldu.",
]


def fill(template: str, rng: random.Random) -> tuple[str, list[dict]]:
    text, entities, i = "", [], 0
    while i < len(template):
        if template[i] == "{":
            j = template.index("}", i)
            code = template[i + 1 : j]
            value = gen_tc_invalid(rng) if code == "TC_INVALID" else gen_value(code, rng)
            if code != "TC_INVALID":
                entities.append(
                    {"start": len(text), "end": len(text) + len(value), "category": code}
                )
            text += value
            i = j + 1
        else:
            text += template[i]
            i += 1
    return text, entities


def records(rng: random.Random) -> list[dict]:
    templates = [t for code in TEMPLATES for t in TEMPLATES[code]] + MULTI + NEGATIVES
    rows = []
    for t in templates:
        text, entities = fill(t, rng)
        rows.append({"text": text, "entities": entities})
    if len(rows) != TOTAL - NAME_SLOTS:
        raise ValueError(f"{len(rows)} name-free sentences, expected {TOTAL - NAME_SLOTS}")
    if len(NAME_SENTENCES) != NAME_SLOTS:
        raise ValueError(f"{len(NAME_SENTENCES)} PERSON sentences, expected {NAME_SLOTS}")
    for t in NAME_SENTENCES:  # appended last so the name-free rows keep their values
        text, entities = fill(t, rng)
        rows.append({"text": text, "entities": entities})
    return [{"id": f"pii-{n:03d}", **r} for n, r in enumerate(rows, start=1)]


CATEGORIES_MD_HEADER = "\n".join(
    [
        "# PII kategori kodları",
        "",
        "`pii-100.jsonl` içindeki `category` kodlarının plan/08 kategori adlarıyla eşlemesi.",
        "Kodlar kanonik listedir (İngilizce, Presidio uyumlu; FOLLOWUP-33, KARARLAR "
        '"08-lite kararları");',
        "tek kaynak `backend/ffcore/guardrails/categories.py`, 08 testi iki listenin eşitliğini "
        "kanıtlar.",
        "`default_on`: 08'in varsayılan politikasında açık. "
        "Kişi adı (`PERSON`) yalnızca bu sette ve",
        "hafıza setinde geçer; adlar betikteki sabit uydurma havuzdandır "
        "(DECISION-24). plan/08'e göre kişi adı",
        "varsayılan politikada `egress`'te `tokenize` edilir; "
        "buradaki `hayır` yalnızca genel açık listeyi gösterir.",
        "",
        "| Kod | plan/08 adı | default_on |",
        "|---|---|---|",
        "",
    ]
)


def generate(rng: random.Random, out: Path, seed: int) -> None:
    base = out / "pii"
    lines = [json.dumps(r, ensure_ascii=False) for r in records(rng)]
    write_text(base / "pii-100.jsonl", "\n".join(lines) + "\n")
    table = "".join(
        f"| `{code}` | {name} | {'evet' if on else 'hayır'} |\n"
        for code, (name, on) in CATEGORIES.items()
    )
    write_text(base / "categories.md", CATEGORIES_MD_HEADER + table)
