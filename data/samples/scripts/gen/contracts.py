"""Five synthetic supplier contracts (plan/13 item 1) as PDF and DOCX, plus manifest.

Facts that eval questions ask about live in FACTS, next to the clause text that
states them, so questions and documents cannot drift apart. No person names: the
parties are the (invented) hospital and companies, signing "through authorised
representatives".
"""

import json
import random
from pathlib import Path

from . import docx, pdf, write_text
from .words import CONTRACTS, DEPARTMENTS, DEVICE_TYPES, HOSPITAL_NAME

# Per contract_type: payment term (days) and the type-specific clauses.
FACTS = {
    "bakim": {
        "payment_days": 45,
        "subject": "kapsamdaki tıbbi cihazların periyodik bakımı, arıza onarımı ve kalibrasyonu",
        "obligations": [
            "Yüklenici, kapsamdaki her cihaz için yılda 2 (iki) periyodik bakım yapar ve bakım "
            "raporunu 3 iş günü içinde İdareye teslim eder.",
            "Kritik arızalarda (cihazın tamamen hizmet dışı kalması) müdahale süresi 4 saattir; "
            "diğer arızalarda müdahale süresi 24 saattir.",
            "Yedek parça temini en geç 10 iş günü içinde tamamlanır.",
            "Kalibrasyon işlemleri akredite laboratuvar sertifikasıyla belgelenir.",
        ],
        "service_level": "Cihaz başına yıllık çalışır durumda olma oranı en az %95'tir; oran her "
        "takvim yılı sonunda hesaplanır.",
        "penalty": "Müdahale süresinin aşıldığı her gün için aylık bedelin %0,5'i oranında cezai "
        "şart uygulanır.",
        "annex_title": "Ek-1 Kapsamdaki cihaz listesi",
        "annex_header": ["Envanter kodu", "Cihaz türü", "Bölüm", "Bakım sıklığı"],
    },
    "hizmet": {
        "payment_days": 30,
        "subject": "hastane binalarının genel ve klinik alan temizliği",
        "obligations": [
            "Temizlik hizmeti haftanın 7 günü 24 saat kesintisiz verilir.",
            "Her vardiyada en az 48 temizlik görevlisi çalıştırılır.",
            "Ameliyathane temizliği, her operasyon sonrasında 30 dakika içinde tamamlanır.",
            "Kullanılan tüm kimyasal ürünler Sağlık Bakanlığı ruhsatlı olmalıdır.",
        ],
        "service_level": "Hijyen denetimi ayda bir kez İdarenin enfeksiyon kontrol komitesi "
        "tarafından yapılır ve tutanağa bağlanır.",
        "penalty": "Denetimde tespit edilen her eksiklik için aylık hizmet bedelinin %1'i oranında "
        "cezai şart uygulanır.",
        "annex_title": "Ek-1 Hizmet alanları ve temizlik sıklığı",
        "annex_header": ["Alan", "Sıklık", "Ekip"],
    },
    "tedarik": {
        "payment_days": 60,
        "subject": "biyokimya ve mikrobiyoloji laboratuvarı test kitlerinin tedariki",
        "obligations": [
            "Sipariş edilen kitler siparişten itibaren en geç 5 iş günü içinde teslim edilir.",
            "Teslim edilen kitlerin raf ömrü teslim tarihinde en az 12 ay olmalıdır.",
            "Kitler 2 ile 8 °C arasında soğuk zincir korunarak taşınır ve saklanır.",
            "Birim fiyatlar sözleşme süresince sabittir.",
        ],
        "service_level": "Hatalı ya da bozuk lot tespit edildiğinde İdare, teslimden itibaren 15 "
        "gün içinde iade hakkını kullanabilir; Yüklenici yeni lotu 3 iş günü içinde gönderir.",
        "penalty": "Teslimatta gecikilen her gün için gecikilen sipariş tutarının %0,3'ü oranında "
        "cezai şart uygulanır.",
        "annex_title": "Ek-1 Kit listesi ve yıllık tahmini miktarlar",
        "annex_header": ["Kit kodu", "Test", "Yıllık miktar"],
    },
    "lisans": {
        "payment_days": 30,
        "subject": "hastane bilgi yönetim yazılımının kullanım lisansı, bakım ve teknik desteği",
        "obligations": [
            "Lisans, en fazla 850 eşzamanlı kullanıcıyı kapsar.",
            "Kritik destek taleplerine yanıt süresi 2 saattir; diğer talepler 1 iş günü içinde "
            "yanıtlanır.",
            "Yeni sürüm ve güncellemeler lisans bedeline dahildir.",
            "Uygulama verisi İdarenin sunucularında tutulur ve dışarı aktarılmaz.",
            "Yüklenici, kaynak kodun güncel kopyasını bağımsız bir kaynak kod emaneti kuruluşunda "
            "saklar; Yüklenicinin faaliyetini sona erdirmesi halinde kaynak kod İdareye teslim "
            "edilir.",
        ],
        "service_level": "Sistemin aylık erişilebilirlik taahhüdü %99,5'tir; planlı bakım "
        "çalışmaları mesai dışında yapılır.",
        "penalty": "Erişilebilirlik taahhüdünün altında kalınan her ay için aylık bedelin %2'si "
        "oranında cezai şart uygulanır.",
        "annex_title": "Ek-1 Lisans kapsamındaki modüller",
        "annex_header": ["Modül", "Kapsam"],
    },
    "danismanlik": {
        "payment_days": 30,
        "subject": "hastane yönetim süreçlerinin gözden geçirilmesi ve iyileştirme önerilerinin "
        "hazırlanması",
        "obligations": [
            "Danışmanlık çalışması altı ay sürer ve aylık ilerleme raporlarıyla yürütülür.",
            "Ödeme iki aşamada yapılır: ara raporun kabulünde bedelin %40'ı, final raporun "
            "kabulünde %60'ı.",
            "Yüklenici, edindiği bilgileri sözleşme bitiminden sonra 5 yıl süreyle gizli tutar.",
        ],
        "service_level": "Raporlar İdarenin yönetim kurulu toplantısından en az 10 gün önce teslim "
        "edilir.",
        "penalty": "Rapor tesliminde gecikilen her gün için toplam bedelin %0,2'si oranında cezai "
        "şart uygulanır.",
        "annex_title": "Ek-1 Çalışma aşamaları",
        "annex_header": ["Aşama", "Çıktı", "Süre"],
    },
}

LAB_TESTS = [
    "Glukoz",
    "Üre",
    "Kreatinin",
    "ALT",
    "AST",
    "Kolesterol",
    "Trigliserit",
    "CRP",
    "Hemoglobin A1c",
    "Ferritin",
    "TSH",
    "Vitamin B12",
    "Kan kültürü",
    "İdrar kültürü",
]
CLEANING_AREAS = [
    "Ameliyathane",
    "Yoğun bakım",
    "Acil servis",
    "Poliklinik koridorları",
    "Hasta odaları",
    "Laboratuvar",
    "Sterilizasyon ünitesi",
    "Bekleme salonları",
    "Asansörler",
    "Tuvaletler",
    "İdari ofisler",
    "Otopark girişleri",
]
MODULES = [
    "Hasta kabul",
    "Poliklinik",
    "Yatan hasta",
    "Laboratuvar",
    "Radyoloji",
    "Eczane",
    "Stok ve satın alma",
    "Faturalama",
    "Raporlama",
]
PHASES = [
    ("Mevcut durum analizi", "Durum raporu", "6 hafta"),
    ("Süreç modelleme", "Süreç haritaları", "6 hafta"),
    ("İyileştirme önerileri", "Ara rapor", "8 hafta"),
    ("Uygulama planı", "Final raporu", "6 hafta"),
]


def _date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def money(value: int) -> str:
    return f"{value:,}".replace(",", ".") + " TL"


def annex_rows(contract: dict, rng: random.Random, n: int) -> list[list[str]]:
    kind = contract["contract_type"]
    if kind == "bakim":
        return [
            [
                f"CHZ-{rng.randint(1, 600):05d}",
                rng.choice(DEVICE_TYPES),
                rng.choice(DEPARTMENTS)[1],
                "yılda 2 kez",
            ]
            for _ in range(n)
        ]
    if kind == "hizmet":
        return [
            [a, f"günde {rng.randint(2, 6)} kez", f"Ekip {rng.randint(1, 8)}"]
            for a in CLEANING_AREAS[:n]
        ]
    if kind == "tedarik":
        return [
            [f"KIT-{i + 1:03d}", t, f"{rng.randint(4, 60) * 100} test"]
            for i, t in enumerate(LAB_TESTS[:n])
        ]
    if kind == "lisans":
        return [[m, "dahil"] for m in MODULES[:n]]
    return [list(p) for p in PHASES[:n]]


def blocks(contract: dict, rng: random.Random) -> list[tuple]:
    f = FACTS[contract["contract_type"]]
    value = contract["annual_value_try"]
    out: list[tuple] = [
        ("h1", contract["title"]),
        (
            "p",
            f"Sözleşme No: {contract['code']}. Bu belge FFCore örnek verisidir; tamamen "
            "sentetiktir.",
        ),
        ("h2", "Madde 1 - Taraflar"),
        (
            "p",
            f'1.1 İşbu sözleşme, {HOSPITAL_NAME} (bundan sonra "İdare") ile {contract["vendor"]} '
            '(bundan sonra "Yüklenici") arasında akdedilmiştir. '
            "Taraflar sözleşmeyi yetkili temsilcileri aracılığıyla imzalamıştır.",
        ),
        ("h2", "Madde 2 - Konu"),
        ("p", f"2.1 Sözleşmenin konusu, {f['subject']} işidir."),
        ("h2", "Madde 3 - Süre"),
        (
            "p",
            f"3.1 Sözleşme {_date(contract['start_date'])} tarihinde yürürlüğe girer ve "
            f"{_date(contract['end_date'])} tarihinde sona erer.",
        ),
        ("h2", "Madde 4 - Bedel ve ödeme"),
        ("p", f"4.1 Yıllık sözleşme bedeli KDV hariç {money(value)} tutarındadır."),
        (
            "p",
            "4.2 Bedel üç aylık dönemler halinde faturalanır ve faturanın İdareye tesliminden "
            f"itibaren {f['payment_days']} gün içinde ödenir.",
        ),
        (
            "table",
            [["Dönem", "Tutar (KDV hariç)"]]
            + [[f"{q}. çeyrek", money(value // 4)] for q in range(1, 5)],
        ),
        ("h2", "Madde 5 - Yüklenicinin yükümlülükleri"),
    ]
    out += [("p", f"5.{i} {text}") for i, text in enumerate(f["obligations"], start=1)]
    out += [
        ("h2", "Madde 6 - Hizmet seviyesi"),
        ("p", f"6.1 {f['service_level']}"),
        ("h2", "Madde 7 - Cezai şart"),
        ("p", f"7.1 {f['penalty']} Cezai şart tutarı ilk hakedişten mahsup edilir."),
        ("h2", "Madde 8 - Gizlilik"),
        (
            "p",
            "8.1 Taraflar, sözleşme kapsamında öğrendikleri ticari ve teknik bilgileri üçüncü "
            "kişilerle paylaşmaz.",
        ),
        ("h2", "Madde 9 - Kişisel verilerin korunması"),
        (
            "p",
            "9.1 Yüklenici, hizmet sırasında erişebileceği kişisel verileri 6698 sayılı Kişisel "
            "Verilerin Korunması Kanunu kapsamında korur ve yalnızca hizmetin gerektirdiği ölçüde "
            "işler.",
        ),
        ("h2", "Madde 10 - Fesih"),
        (
            "p",
            f"10.1 Fesih bildirim süresi: Taraflardan her biri, en az {contract['notice_days']} "
            "gün önceden yazılı bildirimde bulunmak kaydıyla sözleşmeyi sona erdirebilir.",
        ),
        (
            "p",
            "10.2 Yüklenicinin yükümlülüklerini iki kez yazılı ihtara rağmen yerine getirmemesi "
            "halinde İdare sözleşmeyi bildirim süresi beklemeksizin haklı nedenle feshedebilir.",
        ),
        ("h2", "Madde 11 - Mücbir sebep"),
        (
            "p",
            "11.1 Doğal afet, salgın ve benzeri mücbir sebep hallerinde yükümlülüklerin ifası, "
            "sebep ortadan kalkıncaya kadar ertelenir; taraf durumu 5 iş günü içinde yazılı "
            "olarak bildirir.",
        ),
        ("h2", "Madde 12 - Uyuşmazlıkların çözümü"),
        (
            "p",
            "12.1 Sözleşmeden doğan uyuşmazlıklarda İdarenin bulunduğu yer mahkemeleri ve icra "
            "daireleri yetkilidir.",
        ),
        ("h2", "Madde 13 - Yürürlük"),
        (
            "p",
            "13.1 On üç maddeden ve eklerinden oluşan işbu sözleşme, taraflarca okunarak "
            "imzalanmıştır.",
        ),
        ("h2", f["annex_title"]),
        ("table", [f["annex_header"]] + annex_rows(contract, rng, 8)),
    ]
    return out


def render_all(rng: random.Random) -> list[tuple[dict, list[tuple], bytes]]:
    """(contract, blocks, file bytes) for every contract, drawing from rng in a fixed order.
    package 18 (F13 versions) replays this to rebuild a contract's blocks exactly."""
    out = []
    for c in CONTRACTS:
        content = blocks(c, rng)
        if c["format"] == "pdf":
            header = FACTS[c["contract_type"]]["annex_header"]
            data = pdf.render(
                content,
                c["title"],
                pages_exact=c["pages"],
                filler=lambda c=c, h=header: ("table", [h] + annex_rows(c, rng, 10)),
            )
        else:
            data = docx.render(content, c["title"])
        out.append((c, content, data))
    return out


def generate(rng: random.Random, out: Path, seed: int) -> None:
    base = out / "contracts"
    base.mkdir(parents=True, exist_ok=True)
    manifest = []
    for c, _, data in render_all(rng):
        (base / c["file_name"]).write_bytes(data)
        manifest.append(
            {
                "file_name": c["file_name"],
                "code": c["code"],
                "title": c["title"],
                "format": c["format"],
                "pages": c["pages"],
                "acl_roles": c["acl_roles"],
            }
        )
    write_text(base / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
