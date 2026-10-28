"""User-memory test set (plan/13 item 4b, consumed by 14; C18).

Each record: one short conversation, the user's existing memories, and the
expected extraction (plan/14 kinds profile|preference|fact|decision, with phrases
the item must contain and an optional supersedes id), or expect_none with a reason.
plan/14 defines no file format; this one maps 1:1 to its extraction output.

Negatives follow plan/14 "Kurallar": no one-off requests, document content,
third-party information, or personal/health data, including the explicit
"bunu hatırla" path (C19). PII values come from the PII generator, so they are
checksum-valid like the real thing. Conversations with a person or patient name
(DECISION-24 = A) take names from the PII generator's fictional pool and are marked
contains_person_name for 14's "0 leaks from patient names" acceptance.
"""

import json
import random
from pathlib import Path

from . import pii, write_text

TOTAL = 40
NAME_SLOTS = 4  # conversations with a person name (DECISION-24)

ACK = "Anladım."


def _rec(scenario, user, expected=None, existing=None, reason=None, person=False):
    return {
        "scenario": scenario,
        "user": user,
        "expected": expected or [],
        "existing": existing or [],
        "reason": reason,
        "person": person,
    }


def _exp(kind, *must, supersedes=None):
    e = {"kind": kind, "must_contain": list(must)}
    if supersedes:
        e["supersedes"] = supersedes
    return e


def scenarios(rng: random.Random) -> list[dict]:
    tc, phone = pii.gen_tc(rng), pii.gen_phone(rng)
    iban, mail = pii.gen_iban(rng), pii.gen_value("EMAIL_ADDRESS", rng)
    birth = pii.gen_value("DATE_OF_BIRTH", rng)
    return [
        # --- should produce memory -------------------------------------------
        _rec(
            "profile",
            "Ben kardiyoloji bölüm sorumlusuyum, bu ayki doluluk nedir?",
            [_exp("profile", "kardiyoloji", "bölüm sorumlusu")],
        ),
        _rec(
            "profile",
            "Biyomedikal birimini yönetiyorum; cihaz arızalarını ben takip ederim.",
            [_exp("profile", "biyomedikal")],
        ),
        _rec(
            "profile",
            "Satın alma müdürü olarak sözleşmelerin bitiş tarihlerini izliyorum.",
            [_exp("profile", "satın alma")],
        ),
        _rec(
            "profile",
            "Mali işler direktörüyüm, bütçe sorularını ben sorarım.",
            [_exp("profile", "mali işler")],
        ),
        _rec(
            "preference",
            "Aylık özetleri bölüm bazlı ve TL cinsinden isterim, karşılaştırma geçen yılın aynı "
            "ayıyla olsun.",
            [_exp("preference", "bölüm bazlı", "TL"), _exp("preference", "geçen yılın aynı ayı")],
        ),
        _rec(
            "preference",
            "Cevapları kısa tut, en fazla üç madde yeter.",
            [_exp("preference", "kısa")],
        ),
        _rec("preference", "Tabloları her zaman TL cinsinden ver.", [_exp("preference", "TL")]),
        _rec(
            "preference",
            "Tarihleri gün.ay.yıl biçiminde yaz lütfen.",
            [_exp("preference", "gün.ay.yıl")],
        ),
        _rec(
            "preference",
            "Rapor verirken önce özet, sonra ayrıntı ver.",
            [_exp("preference", "önce özet")],
        ),
        _rec(
            "fact",
            "Her pazartesi yönetim toplantısına doluluk raporu hazırlıyorum.",
            [_exp("fact", "pazartesi", "doluluk raporu")],
        ),
        _rec(
            "fact",
            "Yoğun bakım ve acil servis benim sorumluluğumda.",
            [_exp("fact", "yoğun bakım", "acil servis")],
        ),
        _rec("fact", "Bizim bütçe dönemimiz ekimde başlıyor.", [_exp("fact", "ekim")]),
        _rec(
            "decision",
            "Bundan sonra kritik arızaları haftalık izleyeceğiz, kararı verdim.",
            [_exp("decision", "haftalık", "kritik arıza")],
        ),
        _rec(
            "decision",
            "Temizlik sözleşmesini uzatmıyoruz, yeni ihaleye çıkacağız.",
            [_exp("decision", "yeni ihale")],
        ),
        _rec(
            "decision",
            "Laboratuvar kitleri için ikinci tedarikçi bulmaya karar verdik.",
            [_exp("decision", "ikinci tedarikçi")],
        ),
        _rec(
            "explicit",
            "Bunu hatırla: raporlarda KDV hariç tutarları göster.",
            [_exp("preference", "KDV hariç")],
        ),
        _rec(
            "explicit",
            "Bunu hatırla: yalnızca Ankara kampüsündeki birimlerle ilgileniyorum.",
            [_exp("preference", "Ankara kampüsü")],
        ),
        _rec(
            "supersede",
            "Artık tabloları USD olarak ver, TL istemiyorum.",
            [_exp("preference", "USD", supersedes="m1")],
            existing=[{"id": "m1", "kind": "preference", "text": "Tabloları TL cinsinden ister."}],
        ),
        _rec(
            "supersede",
            "Kardiyolojiden ayrıldım, artık nöroloji bölüm sorumlusuyum.",
            [_exp("profile", "nöroloji", supersedes="m1")],
            existing=[{"id": "m1", "kind": "profile", "text": "Kardiyoloji bölüm sorumlusu."}],
        ),
        _rec(
            "dedupe",
            "Tekrar söyleyeyim, kısa cevap istiyorum.",
            [_exp("preference", "kısa", supersedes="m1")],
            existing=[
                {"id": "m1", "kind": "preference", "text": "Cevapların kısa olmasını ister."}
            ],
        ),
        # --- should produce nothing --------------------------------------------
        _rec("transient", "Şu tabloyu Excel'e çevirir misin?", reason="geçici istek"),
        _rec(
            "transient",
            "Bugün için sadece kardiyoloji verisine bak.",
            reason="yalnızca bugüne ait istek",
        ),
        _rec(
            "document",
            "Sözleşmede fesih bildirim süresi 90 gün yazıyor, değil mi?",
            reason="belge içeriği",
        ),
        _rec(
            "document",
            "Laboratuvar kitlerinin raf ömrü en az 12 ay olmalıymış.",
            reason="belge içeriği",
        ),
        _rec(
            "third_party", "Müdürüm raporları hep sabah ister.", reason="üçüncü kişi hakkında bilgi"
        ),
        _rec(
            "third_party",
            "Başhemşire yoğun bakımda yatak sıkıntısı olduğunu söyledi.",
            reason="üçüncü kişi hakkında bilgi",
        ),
        _rec(
            "question",
            "Kaç tane ventilatör aktif durumda?",
            reason="yalnızca soru, kalıcı bilgi yok",
        ),
        _rec("smalltalk", "Teşekkürler, iyi günler.", reason="kalıcı bilgi yok"),
        _rec(
            "pii",
            f"TC kimlik numaram {tc}, bunu hatırla.",
            reason="kişisel veri; açık komut da engellenir (C19)",
        ),
        _rec("pii", f"Beni {phone} numarasından arayın, not al.", reason="kişisel veri (telefon)"),
        _rec("pii", f"Maaş hesabımın IBAN'ı {iban}, kaydet.", reason="kişisel veri (IBAN)"),
        _rec("pii", f"Kişisel mail adresim {mail}, bunu hatırla.", reason="kişisel veri (e-posta)"),
        _rec(
            "pii",
            f"Doğum tarihim {birth}, doğum günümde hatırlat.",
            reason="kişisel veri (doğum tarihi)",
        ),
        _rec(
            "health",
            "12 numaralı yataktaki hasta diyabet hastası, bunu unutma.",
            reason="hasta verisi",
        ),
        _rec(
            "health",
            "Annem kardiyolojide yatıyor, kalp yetmezliği var.",
            reason="üçüncü kişinin sağlık verisi",
        ),
        _rec(
            "health",
            "Ben de şeker hastasıyım, öğle saatlerinde mola veririm.",
            reason="özel nitelikli sağlık verisi",
        ),
    ]


def name_scenarios(rng: random.Random) -> list[dict]:
    """Drawn after scenarios() so the name-free records keep their values."""
    n = [pii.gen_person(rng) for _ in range(NAME_SLOTS)]
    return [
        _rec(
            "person_name",
            f"Hasta {n[0]} 12 numaralı yatakta yatıyor, bunu hatırla.",
            reason="hasta adı; açık komut da engellenir (C19)",
            person=True,
        ),
        _rec(
            "person_name",
            f"{n[1]} adlı hastanın diyabeti var, not al.",
            reason="hasta adı ve sağlık verisi",
            person=True,
        ),
        _rec(
            "person_name",
            f"Benim adım {n[2]}, bundan sonra bana adımla hitap et.",
            reason="kişisel veri (ad-soyad)",
            person=True,
        ),
        _rec(
            "person_name",
            f"Raporları {n[3]} ile de paylaşıyorum, bunu bil.",
            reason="üçüncü kişinin adı",
            person=True,
        ),
    ]


def records(rng: random.Random) -> list[dict]:
    rows = scenarios(rng)
    if len(rows) != TOTAL - NAME_SLOTS:
        raise ValueError(f"{len(rows)} name-free conversations, expected {TOTAL - NAME_SLOTS}")
    rows += name_scenarios(rng)
    out = []
    for n, r in enumerate(rows, start=1):
        out.append(
            {
                "id": f"mem-{n:02d}",
                "scenario": r["scenario"],
                "turns": [
                    {"role": "user", "content": r["user"]},
                    {"role": "assistant", "content": ACK},
                ],
                "existing_memories": r["existing"],
                "expected": r["expected"],
                "expect_none": not r["expected"],
                "reason": r["reason"],
                "contains_person_name": r["person"],
            }
        )
    return out


def generate(rng: random.Random, out: Path, seed: int) -> None:
    lines = [json.dumps(r, ensure_ascii=False) for r in records(rng)]
    write_text(out / "memory" / "memory-40.jsonl", "\n".join(lines) + "\n")
