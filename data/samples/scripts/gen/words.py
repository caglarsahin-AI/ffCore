"""Fixed synthetic vocabularies shared by generators.

All organisation names are invented for this sample set. No person names here:
person names (if approved, decision T-13a-0003) live only in the PII and memory
generators.
"""

HOSPITAL_NAME = "Örnek Şehir Hastanesi"

DEPARTMENTS = [
    ("KARD", "Kardiyoloji"),
    ("NORO", "Nöroloji"),
    ("ORTO", "Ortopedi"),
    ("GCER", "Genel Cerrahi"),
    ("DAHI", "Dahiliye"),
    ("PEDI", "Pediatri"),
    ("KADO", "Kadın Doğum"),
    ("GOZH", "Göz Hastalıkları"),
    ("KBBH", "Kulak Burun Boğaz"),
    ("UROL", "Üroloji"),
    ("ONKO", "Onkoloji"),
    ("NEFR", "Nefroloji"),
    ("GOGU", "Göğüs Hastalıkları"),
    ("DERM", "Dermatoloji"),
    ("PSIK", "Psikiyatri"),
    ("FTRH", "Fizik Tedavi"),
    ("ACIL", "Acil Servis"),
    ("YBAK", "Yoğun Bakım"),
    ("ENFK", "Enfeksiyon Hastalıkları"),
    ("ENDO", "Endokrinoloji"),
]

BED_TYPES = ["standart", "yogun_bakim", "izolasyon"]

DEVICE_TYPES = [
    "hasta_monitoru",
    "infuzyon_pompasi",
    "ventilator",
    "ekg_cihazi",
    "ultrason",
    "defibrilator",
    "rontgen",
]
DEVICE_STATUSES = ["aktif", "bakimda", "hurda"]
FAULT_TYPES = ["elektriksel", "mekanik", "yazilim", "kalibrasyon", "sensor", "batarya"]
SEVERITIES = ["dusuk", "orta", "yuksek", "kritik"]

# The five synthetic contracts. contracts_meta rows, the contract documents and the
# eval questions are all generated from this one list so they cannot drift apart.
# acl_roles: [] = open to every project member (C15), ["admin"] = admin only.
CONTRACTS = [
    {
        "code": "SZL-2024-011",
        "title": "Tıbbi Cihaz Bakım ve Onarım Hizmet Sözleşmesi",
        "vendor": "Tavlan Medikal Teknik A.Ş.",
        "contract_type": "bakim",
        "start_date": "2024-03-01",
        "end_date": "2027-02-28",
        "annual_value_try": 4_850_000,
        "notice_days": 90,
        "file_name": "SZL-2024-011_cihaz-bakim.pdf",
        "format": "pdf",
        "pages": 10,
        "acl_roles": ["analyst"],
    },
    {
        "code": "SZL-2025-003",
        "title": "Temizlik Hizmet Alımı Sözleşmesi",
        "vendor": "Parlak Ufuk Tesis Hizmetleri Ltd. Şti.",
        "contract_type": "hizmet",
        "start_date": "2025-01-01",
        "end_date": "2026-12-31",
        "annual_value_try": 12_600_000,
        "notice_days": 30,
        "file_name": "SZL-2025-003_temizlik-hizmet.docx",
        "format": "docx",
        "pages": None,
        "acl_roles": ["analyst"],
    },
    {
        "code": "SZL-2025-007",
        "title": "Laboratuvar Kiti Tedarik Sözleşmesi",
        "vendor": "Kumsal Biyoteknoloji A.Ş.",
        "contract_type": "tedarik",
        "start_date": "2025-04-15",
        "end_date": "2026-04-14",
        "annual_value_try": 3_275_000,
        "notice_days": 60,
        "file_name": "SZL-2025-007_laboratuvar-kiti.docx",
        "format": "docx",
        "pages": None,
        "acl_roles": [],
    },
    {
        "code": "SZL-2023-019",
        "title": "Hastane Bilgi Yönetim Yazılımı Lisans ve Destek Sözleşmesi",
        "vendor": "Mavikod Bilişim A.Ş.",
        "contract_type": "lisans",
        "start_date": "2023-07-01",
        "end_date": "2026-06-30",
        "annual_value_try": 2_140_000,
        "notice_days": 45,
        "file_name": "SZL-2023-019_yazilim-lisans.pdf",
        "format": "pdf",
        "pages": 4,
        "acl_roles": ["analyst"],
    },
    {
        "code": "SZL-2025-012",
        "title": "Yönetim Danışmanlığı ve Gizlilik Sözleşmesi",
        "vendor": "Erguvan Danışmanlık A.Ş.",
        "contract_type": "danismanlik",
        "start_date": "2025-06-01",
        "end_date": "2026-05-31",
        "annual_value_try": 960_000,
        "notice_days": 15,
        "file_name": "SZL-2025-012_yonetim-danismanlik.docx",
        "format": "docx",
        "pages": None,
        "acl_roles": ["admin"],
    },
]

VENDORS = [c["vendor"] for c in CONTRACTS]
