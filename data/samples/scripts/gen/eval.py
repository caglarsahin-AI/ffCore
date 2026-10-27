"""33-item evaluation set (plan/13 item 4, plan/09 "Soru seti kuralları", R8.1; total 33 per K-13a-0003, DRIFT-28).

Item shape follows plan/09's Langfuse mapping: input {message, variables},
expected_output {answer, must_contain, must_cite, sql_result}, metadata
{tags, answerable, style, expected_docs}. plan/09's style enum has no value for SQL
questions, so they are style=dogrudan with tag "sql" (K-13a-0002, FOLLOWUP-27).

absent_terms / avoided_term are generator-side checks only (not written to the
dataset): tests prove "alan içi cevapsız" terms have 0 hits in the KB and
"dolaylı" questions avoid the document's own term.
Documents asked about are all analyst-visible; the admin-only contract stays out
because eval runs with an analyst actor.
"""

import json
import random
from pathlib import Path

from . import schema, write_text
from .words import CONTRACTS

DOC = {c["contract_type"]: c["file_name"] for c in CONTRACTS}
UNKNOWN_REPLY = "Bu bilgi belgelerde yok."  # sozlesme-asistani unknown_reply

QUESTIONS = [
    # 12 direct: the question uses the document's own wording
    {"id": "q01", "style": "dogrudan", "doc": DOC["bakim"], "must": ["90 gün"],
     "q": "Tıbbi cihaz bakım sözleşmesinde fesih bildirim süresi kaç gündür?",
     "a": "Fesih bildirim süresi en az 90 gündür (Madde 10.1)."},
    {"id": "q02", "style": "dogrudan", "doc": DOC["bakim"], "must": ["4 saattir"],
     "q": "Cihaz bakım sözleşmesine göre kritik arızalarda müdahale süresi nedir?",
     "a": "Kritik arızalarda müdahale süresi 4 saattir (Madde 5.2)."},
    {"id": "q03", "style": "dogrudan", "doc": DOC["bakim"], "must": ["yılda 2"],
     "q": "Cihaz bakım sözleşmesinde her cihaz için yılda kaç periyodik bakım yapılır?",
     "a": "Her cihaz için yılda 2 periyodik bakım yapılır (Madde 5.1)."},
    {"id": "q04", "style": "dogrudan", "doc": DOC["hizmet"], "must": ["12.600.000 TL"],
     "q": "Temizlik hizmet alımı sözleşmesinin yıllık bedeli nedir?",
     "a": "Yıllık bedel KDV hariç 12.600.000 TL'dir (Madde 4.1)."},
    {"id": "q05", "style": "dogrudan", "doc": DOC["hizmet"], "must": ["30 dakika"],
     "q": "Temizlik sözleşmesine göre ameliyathane temizliği ne kadar sürede tamamlanmalıdır?",
     "a": "Her operasyon sonrasında 30 dakika içinde tamamlanır (Madde 5.3)."},
    {"id": "q06", "style": "dogrudan", "doc": DOC["hizmet"], "must": ["31.12.2026"],
     "q": "Temizlik hizmet alımı sözleşmesi hangi tarihte sona erer?",
     "a": "31.12.2026 tarihinde sona erer (Madde 3.1)."},
    {"id": "q07", "style": "dogrudan", "doc": DOC["tedarik"], "must": ["5 iş günü"],
     "q": "Laboratuvar kiti tedarik sözleşmesinde teslim süresi kaç iş günüdür?",
     "a": "Kitler siparişten itibaren en geç 5 iş günü içinde teslim edilir (Madde 5.1)."},
    {"id": "q08", "style": "dogrudan", "doc": DOC["tedarik"], "must": ["2 ile 8 °C"],
     "q": "Laboratuvar kitleri hangi sıcaklık aralığında taşınmalı ve saklanmalıdır?",
     "a": "2 ile 8 °C arasında, soğuk zincir korunarak (Madde 5.3)."},
    {"id": "q09", "style": "dogrudan", "doc": DOC["lisans"], "must": ["850"],
     "q": "Hastane bilgi yönetim yazılımı lisansı en fazla kaç eşzamanlı kullanıcıyı kapsar?",
     "a": "En fazla 850 eşzamanlı kullanıcıyı kapsar (Madde 5.1)."},
    {"id": "q10", "style": "dogrudan", "doc": DOC["lisans"], "must": ["%99,5"],
     "q": "Yazılım lisans sözleşmesinde aylık erişilebilirlik taahhüdü yüzde kaçtır?",
     "a": "Aylık erişilebilirlik taahhüdü %99,5'tir (Madde 6.1)."},
    {"id": "q11", "style": "dogrudan", "doc": DOC["lisans"], "must": ["2 saattir"],
     "q": "Yazılım lisans sözleşmesinde kritik destek taleplerine yanıt süresi nedir?",
     "a": "Kritik destek taleplerine yanıt süresi 2 saattir (Madde 5.2)."},
    {"id": "q12", "style": "dogrudan", "doc": DOC["tedarik"], "must": ["60 gün"],
     "q": "Laboratuvar kiti tedarik sözleşmesinde faturalar kaç gün içinde ödenir?",
     "a": "Faturanın tesliminden itibaren 60 gün içinde ödenir (Madde 4.2)."},
    # 8 indirect: the answer is in the document but the question avoids its term
    {"id": "q13", "style": "dolayli", "doc": DOC["bakim"], "must": ["90 gün"], "avoided_term": "fesih",
     "q": "Cihaz bakım firmasıyla çalışmayı bırakmak istersek ne kadar önceden haber vermemiz gerekir?",
     "a": "En az 90 gün önceden yazılı bildirim gerekir (Madde 10.1)."},
    {"id": "q14", "style": "dolayli", "doc": DOC["bakim"], "must": ["4 saattir"], "avoided_term": "müdahale",
     "q": "Bir ventilatör tamamen durursa bakım firmasının en geç ne kadar sürede gelmesi gerekir?",
     "a": "Cihazın tamamen hizmet dışı kaldığı kritik arızalarda 4 saat (Madde 5.2)."},
    {"id": "q15", "style": "dolayli", "doc": DOC["hizmet"], "must": ["%1"], "avoided_term": "cezai",
     "q": "Temizlik şirketi denetimde eksik çıkarsa ne kadar kesinti yapılır?",
     "a": "Her eksiklik için aylık hizmet bedelinin %1'i (Madde 7.1)."},
    {"id": "q16", "style": "dolayli", "doc": DOC["tedarik"], "must": ["12 ay"], "avoided_term": "raf ömrü",
     "q": "Gelen test kitlerinin son kullanma tarihine en az ne kadar süre kalmış olmalı?",
     "a": "Teslim tarihinde en az 12 ay (Madde 5.2)."},
    {"id": "q17", "style": "dolayli", "doc": DOC["tedarik"], "must": ["15 gün"], "avoided_term": "iade",
     "q": "Hatalı çıkan bir kit partisini kaç gün içinde geri gönderebiliriz?",
     "a": "Teslimden itibaren 15 gün içinde (Madde 6.1)."},
    {"id": "q18", "style": "dolayli", "doc": DOC["lisans"], "must": ["kaynak kod emaneti"], "avoided_term": "emanet",
     "q": "Yazılım firması kapanırsa programın kodlarına nasıl ulaşırız?",
     "a": "Kaynak kod bağımsız bir kaynak kod emaneti kuruluşunda saklanır ve İdareye teslim edilir (Madde 5.5)."},
    {"id": "q19", "style": "dolayli", "doc": DOC["hizmet"], "must": ["7 günü 24 saat"], "avoided_term": "kesintisiz",
     "q": "Temizlik firması gece ve hafta sonları da çalışıyor mu?",
     "a": "Evet, haftanın 7 günü 24 saat hizmet verilir (Madde 5.1)."},
    {"id": "q20", "style": "dolayli", "doc": DOC["bakim"], "must": ["10 iş günü"], "avoided_term": "yedek parça",
     "q": "Bakım firması bozulan cihazın parçasını en geç ne zaman getirmeli?",
     "a": "En geç 10 iş günü içinde (Madde 5.3)."},
    # 5 in-domain unanswerable: an existing contract, a field it does not have
    {"id": "q21", "style": "alan_ici_cevapsiz", "absent_terms": ["yemek"],
     "q": "Temizlik sözleşmesinde personele verilecek yemek ücreti ne kadardır?"},
    {"id": "q22", "style": "alan_ici_cevapsiz", "absent_terms": ["sigorta"],
     "q": "Cihaz bakım sözleşmesinde firmanın sigorta poliçesi tutarı nedir?"},
    {"id": "q23", "style": "alan_ici_cevapsiz", "absent_terms": ["kargo"],
     "q": "Laboratuvar kiti sözleşmesinde hangi kargo firması kullanılacak?"},
    {"id": "q24", "style": "alan_ici_cevapsiz", "absent_terms": ["eğitim"],
     "q": "Yazılım lisans sözleşmesinde kullanıcı eğitimi için kaç saat ayrılmıştır?"},
    {"id": "q25", "style": "alan_ici_cevapsiz", "absent_terms": ["marka", "deterjan"],
     "q": "Temizlik sözleşmesinde kullanılacak deterjanların markası nedir?"},
    # 3 out-of-domain unanswerable (behaviour check only, plan/09)
    {"id": "q26", "style": "alan_disi_cevapsiz", "absent_terms": ["kripto"],
     "q": "Hastanede kripto para ile ödeme yapılabilir mi?"},
    {"id": "q27", "style": "alan_disi_cevapsiz", "absent_terms": ["hava durumu"],
     "q": "Yarın Ankara'da hava durumu nasıl olacak?"},
    {"id": "q28", "style": "alan_disi_cevapsiz", "absent_terms": ["euro", "döviz"],
     "q": "Bugün bir euro kaç TL?"},
]


def _dep_id(rows, code: str) -> int:
    return next(r[0] for r in rows["departments"] if r[1] == code)


SQL_QUESTIONS = [
    {"id": "q29", "q": "Göğüs Hastalıkları bölümünde kaç yatak var?",
     "sql": "SELECT bed_capacity FROM departments WHERE code = 'GOGU'",
     "compute": lambda rows: next(r[4] for r in rows["departments"] if r[1] == "GOGU")},
    {"id": "q30", "q": "Ortopedi bölümünde 2025 yılında toplam kaç hasta taburcu edildi?",
     "sql": "SELECT SUM(a.discharged_count) FROM admissions a JOIN departments d ON d.id = a.department_id "
            "WHERE d.code = 'ORTO' AND a.day BETWEEN '2025-01-01' AND '2025-12-31'",
     "compute": lambda rows: sum(r[4] for r in rows["admissions"] if r[1] == _dep_id(rows, "ORTO"))},
    {"id": "q31", "q": "Hurda durumundaki cihaz sayısı kaçtır?",
     "sql": "SELECT COUNT(*) FROM devices WHERE status = 'hurda'",
     "compute": lambda rows: sum(1 for r in rows["devices"] if r[6] == "hurda")},
    {"id": "q32", "q": "Yazılım kaynaklı kaç arıza kaydı var?",
     "sql": "SELECT COUNT(*) FROM device_faults WHERE fault_type = 'yazilim'",
     "compute": lambda rows: sum(1 for r in rows["device_faults"] if r[3] == "yazilim")},
    {"id": "q33", "q": "Yüksek önemdeki arızalardan kaçı hâlâ çözülmedi?",
     "sql": "SELECT COUNT(*) FROM device_faults WHERE severity = 'yuksek' AND resolved_on IS NULL",
     "compute": lambda rows: sum(1 for r in rows["device_faults"] if r[4] == "yuksek" and r[5] is None)},
]

CONTRACT_TYPE = {c["file_name"]: c["contract_type"] for c in CONTRACTS}


def items(seed: int) -> list[dict]:
    rows = schema.build(random.Random(f"{seed}:schema"))
    out = []
    for q in QUESTIONS:
        unanswerable = q["style"].endswith("cevapsiz")
        if unanswerable:
            expected = {"answer": UNKNOWN_REPLY}
            md = {"tags": ["cevapsiz"], "answerable": False, "style": q["style"], "expected_docs": []}
        else:
            expected = {"answer": q["a"], "must_contain": q["must"], "must_cite": [q["doc"]]}
            md = {"tags": ["belge", CONTRACT_TYPE[q["doc"]]], "answerable": True, "style": q["style"],
                  "expected_docs": [q["doc"]]}
        out.append({"id": q["id"], "input": {"message": q["q"], "variables": {}},
                    "expected_output": expected, "metadata": md})
    for q in SQL_QUESTIONS:
        value = q["compute"](rows)
        out.append({"id": q["id"], "input": {"message": q["q"], "variables": {}},
                    "expected_output": {"answer": str(value), "must_contain": [str(value)],
                                        "sql_result": [[value]]},
                    "metadata": {"tags": ["sql"], "answerable": True, "style": "dogrudan", "expected_docs": []}})
    return out


SUITE = {
    "key": "sozlesme-33",
    "name": "Sözleşme ve veri sınavı (33 soru)",
    "langfuse_dataset_name": "sozlesme-33",
    "scorers": ["contains", "cites_source", "sql_result", "llm_judge"],
    "pass_threshold": 0.8,
    "repeat": 1,
}


def generate(rng: random.Random, out: Path, seed: int) -> None:
    base = out / "eval"
    write_text(base / "sozlesme-33.json", json.dumps(items(seed), ensure_ascii=False, indent=2) + "\n")
    write_text(base / "suite.json", json.dumps(SUITE, ensure_ascii=False, indent=2) + "\n")
