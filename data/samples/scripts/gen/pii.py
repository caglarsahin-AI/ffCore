"""Turkish PII test set (plan/13 item 4b, consumed by 08; C18).

Category codes map to plan/08's Turkish category names (see pii/categories.md).
All values are synthetic; numbers with a checksum (TC kimlik, VKN, IBAN, card) are
generated valid so 08's checksum recognisers can be tested, and negatives include
look-alike numbers with a wrong checksum. E-mail local parts are not names.

Person names (KISI_ADI) wait for DECISION-24: NAME_SENTENCES is empty until then,
and the 100-sentence total is reported NOT_RUN by the tests, not padded.
"""

import json
import random
from pathlib import Path

from . import write_text

TOTAL = 100
NAME_SLOTS = 20  # filled only after DECISION-24
NAME_SENTENCES: list[str] = []

# code -> plan/08 category name; "default_on" = enabled in 08's default policy
CATEGORIES = {
    "TC_KIMLIK": ("TC kimlik", True), "TR_TELEFON": ("TR telefon", True),
    "TR_IBAN": ("TR IBAN", True), "VKN": ("VKN", False), "PLAKA": ("plaka", False),
    "TR_PASAPORT": ("TR pasaport", False), "TR_ADRES": ("TR adres", False),
    "KISI_ADI": ("kişi adı", False), "KURUM_ADI": ("kurum adı", False), "KONUM": ("konum", False),
    "EPOSTA": ("e-posta", True), "KART": ("kart", True), "CVV": ("CVV", True), "PIN": ("PIN", True),
    "GPS": ("GPS", False), "MAC": ("MAC", False), "API_TOKEN": ("API token", False),
    "SIFRE": ("şifre", False), "DOGUM_TARIHI": ("doğum tarihi", False),
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
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))


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
            return " ".join(num[i:i + 4] for i in range(0, 16, 4))
    raise AssertionError("unreachable")


def gen_phone(rng: random.Random) -> str:
    op = rng.choice(["501", "505", "532", "533", "542", "545", "552", "555"])
    n = "".join(str(rng.randint(0, 9)) for _ in range(7))
    return rng.choice([f"0{op} {n[:3]} {n[3:5]} {n[5:]}", f"+90 {op} {n[:3]} {n[3:]}", f"0{op}{n}",
                       f"({op}) {n[:3]}-{n[3:]}"])


PLATE_LETTERS = "ABCDEFGHJKLMNPRSTUVYZ"
STREETS = ["Lale", "Menekşe", "Akasya", "Çınar", "Gül", "Papatya", "Ihlamur", "Defne"]
DISTRICTS = [("Keçiören", "Ankara"), ("Kadıköy", "İstanbul"), ("Bornova", "İzmir"),
             ("Nilüfer", "Bursa"), ("Konyaaltı", "Antalya"), ("Tepebaşı", "Eskişehir")]
ORGS = ["Yıldızkent Lojistik A.Ş.", "Bereket Gıda Ltd. Şti.", "Mavikule Danışmanlık A.Ş.",
        "Kırlangıç Yapı A.Ş.", "Tavlan Medikal Teknik A.Ş.", "Ekinsoy Tarım Kooperatifi"]


def gen_value(code: str, rng: random.Random) -> str:
    if code == "TC_KIMLIK":
        return gen_tc(rng)
    if code == "TR_TELEFON":
        return gen_phone(rng)
    if code == "TR_IBAN":
        return gen_iban(rng)
    if code == "VKN":
        return gen_vkn(rng)
    if code == "PLAKA":
        return f"{rng.randint(1, 81):02d} {''.join(rng.choice(PLATE_LETTERS) for _ in range(rng.randint(1, 3)))} {rng.randint(10, 9999)}"
    if code == "TR_PASAPORT":
        return rng.choice("UZS") + "".join(str(rng.randint(0, 9)) for _ in range(8))
    if code == "TR_ADRES":
        district, city = rng.choice(DISTRICTS)
        return (f"{rng.choice(STREETS)} Mah. {rng.choice(STREETS)} Sok. No: {rng.randint(1, 120)} "
                f"D: {rng.randint(1, 30)} {district}/{city}")
    if code == "KURUM_ADI":
        return rng.choice(ORGS)
    if code == "KONUM":
        return rng.choice([d for pair in DISTRICTS for d in pair])
    if code == "EPOSTA":
        local = rng.choice(["destek", "bilgi", "muhasebe", "satinalma", "kullanici", "rapor"])
        return f"{local}{rng.randint(10, 9999)}@{rng.choice(['ornek.com.tr', 'example.com', 'ornek.org'])}"
    if code == "KART":
        return gen_card(rng)
    if code == "CVV":
        return f"{rng.randint(0, 999):03d}"
    if code == "PIN":
        return f"{rng.randint(0, 9999):04d}"
    if code == "GPS":
        return f"{rng.uniform(36, 42):.4f}, {rng.uniform(26, 45):.4f}"
    if code == "MAC":
        return ":".join(f"{rng.randint(0, 255):02X}" for _ in range(6))
    if code == "API_TOKEN":
        return "tok_" + "".join(rng.choice("0123456789abcdef") for _ in range(32))
    if code == "SIFRE":
        return rng.choice(["Bahar", "Deniz", "Kartal", "Yonca"]) + str(rng.randint(1000, 9999)) + rng.choice("!?.*")
    if code == "DOGUM_TARIHI":
        return f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1950, 2005)}"
    raise ValueError(code)


# --- sentence templates: {CODE} placeholders become labelled spans ---------------

TEMPLATES = {
    "TC_KIMLIK": ["Başvuru formunda TC kimlik numarası {TC_KIMLIK} olarak yazılmış.",
                  "Kimlik no: {TC_KIMLIK}, lütfen sisteme girin.",
                  "{TC_KIMLIK} numaralı kayıt için randevu oluşturuldu.",
                  "T.C. {TC_KIMLIK} kimlik numaralı hasta yakını bilgi istedi.",
                  "tc kimlik no {TC_KIMLIK}",
                  "Sigortalının kimlik numarasını ({TC_KIMLIK}) kontrol eder misin?"],
    "TR_TELEFON": ["Bana {TR_TELEFON} numarasından ulaşabilirsiniz.",
                   "Geri arama için telefon: {TR_TELEFON}",
                   "Acil durumda {TR_TELEFON} aranacak.",
                   "Cep numarası {TR_TELEFON}, mesaj atılabilir.",
                   "tel {TR_TELEFON} whatsapp da var",
                   "Santral meşgulse doğrudan {TR_TELEFON} numarasını deneyin."],
    "TR_IBAN": ["Ödemeyi {TR_IBAN} IBAN'ına yapın.", "Hesap bilgisi: {TR_IBAN}",
                "iban {TR_IBAN} alıcı firma hesabı",
                "İade tutarı {TR_IBAN} numaralı hesaba aktarılacak.",
                "Fatura üzerindeki IBAN {TR_IBAN} doğru mu?"],
    "VKN": ["Firmanın vergi kimlik numarası {VKN}.", "VKN: {VKN} olan tedarikçi kaydı güncellendi.",
            "Faturada {VKN} vergi numarası yazıyor.",
            "vergi no {VKN} ile e-fatura kesildi"],
    "PLAKA": ["Servis aracının plakası {PLAKA}.", "{PLAKA} plakalı ambulans otoparka girdi.",
              "Otopark kaydında {PLAKA} görünüyor."],
    "TR_PASAPORT": ["Pasaport numarası {TR_PASAPORT} olan ziyaretçi kayıt yaptırdı.",
                    "Yurt dışı başvurusu için pasaport: {TR_PASAPORT}",
                    "pasaport no {TR_PASAPORT} vize formuna eklendi"],
    "TR_ADRES": ["Teslimat adresi: {TR_ADRES}", "Fatura {TR_ADRES} adresine gönderilsin.",
                 "Ev adresim {TR_ADRES} olarak güncellensin.",
                 "Kargo yerine elden teslim: {TR_ADRES}"],
    "KURUM_ADI": ["{KURUM_ADI} ile yapılan görüşme ertelendi.",
                  "Teklif {KURUM_ADI} tarafından gönderildi.",
                  "Sevkiyatı {KURUM_ADI} üstlenecek."],
    "KONUM": ["Toplantı {KONUM} şubesinde yapılacak.", "Numune {KONUM} deposundan alınacak.",
              "Ekip yarın {KONUM} bölgesinde olacak."],
    "EPOSTA": ["Raporu {EPOSTA} adresine gönderin.", "İletişim: {EPOSTA}",
               "Şifre sıfırlama bağlantısı {EPOSTA} adresine gitti.",
               "Toplantı daveti {EPOSTA} hesabından geldi.",
               "mail adresim {EPOSTA}",
               "Yanıtı {EPOSTA} adresine CC'leyin."],
    "KART": ["Kart numarası {KART} ile ödeme denendi.", "Ödeme için {KART} kartını kullanın.",
             "kartım {KART} limit doldu mu bakar mısın",
             "Ekstrede {KART} kartına ait harcama var."],
    "CVV": ["Kartın arkasındaki CVV {CVV}.", "Güvenlik kodu (CVV): {CVV}"],
    "PIN": ["Kartın PIN kodu {PIN}, kimseyle paylaşmayın.", "Kasa için PIN: {PIN}"],
    "GPS": ["Ambulansın son konumu {GPS}.", "Saha ekibinin koordinatı: {GPS}"],
    "MAC": ["Cihazın MAC adresi {MAC}.", "Ağa {MAC} adresli bilinmeyen cihaz bağlandı."],
    "API_TOKEN": ["Entegrasyon anahtarı {API_TOKEN} olarak tanımlandı.",
                  "Authorization başlığında {API_TOKEN} gönderiliyor."],
    "SIFRE": ["Yeni şifrem {SIFRE}, unutmamak için yazıyorum.", "Geçici şifre: {SIFRE}"],
    "DOGUM_TARIHI": ["Doğum tarihi {DOGUM_TARIHI} olarak kayıtlı.", "Doğum tarihim {DOGUM_TARIHI}.",
                     "d.t. {DOGUM_TARIHI}, yaş sınırı kontrol edilsin"],
}
MULTI = [
    "Kimlik no {TC_KIMLIK}, telefon {TR_TELEFON}, e-posta {EPOSTA}.",
    "{KURUM_ADI} adına ödeme {TR_IBAN} hesabına, vergi no {VKN}.",
    "Kart {KART}, CVV {CVV}, son kullanma bilgisi formda.",
    "Teslimat {TR_ADRES}, irtibat {TR_TELEFON}.",
    "Sunucu {MAC} cihazından {API_TOKEN} anahtarıyla bağlandı.",
    "{DOGUM_TARIHI} doğumlu başvuru sahibinin kimlik no'su {TC_KIMLIK}.",
    "Sevkiyat {KONUM} deposundan {PLAKA} plakalı araçla çıktı.",
    "PIN {PIN} ve şifre {SIFRE} aynı not kâğıdında yazıyordu.",
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
            code = template[i + 1:j]
            value = gen_tc_invalid(rng) if code == "TC_INVALID" else gen_value(code, rng)
            if code != "TC_INVALID":
                entities.append({"start": len(text), "end": len(text) + len(value), "category": code})
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
    for t in NAME_SENTENCES:  # DECISION-24
        text, entities = fill(t, rng)
        rows.append({"text": text, "entities": entities})
    return [{"id": f"pii-{n:03d}", **r} for n, r in enumerate(rows, start=1)]


CATEGORIES_MD_HEADER = """# PII kategori kodları

`pii-100.jsonl` içindeki `category` kodlarının plan/08 kategori adlarıyla eşlemesi.
`default_on`: 08'in varsayılan politikasında açık. Kişi adı (KISI_ADI) cümleleri DECISION-24 kararını bekliyor.

| Kod | plan/08 adı | default_on |
|---|---|---|
"""


def generate(rng: random.Random, out: Path, seed: int) -> None:
    base = out / "pii"
    lines = [json.dumps(r, ensure_ascii=False) for r in records(rng)]
    write_text(base / "pii-100.jsonl", "\n".join(lines) + "\n")
    table = "".join(f"| `{code}` | {name} | {'evet' if on else 'hayır'} |\n"
                    for code, (name, on) in CATEGORIES.items())
    write_text(base / "categories.md", CATEGORIES_MD_HEADER + table)
