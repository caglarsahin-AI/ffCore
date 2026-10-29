"""F2 data (plan/18): 20 synthetic help-desk tickets and their expected triage class.

Setting: the IT and biomedical help desk of the sample hospital (same vocabulary as the demo
DB: departments, devices, faults, the five contracts). Classes are a closed list; every class
has at least one ticket that names its need indirectly, so triage cannot be a keyword match.
Five tickets carry synthetic PII from the PII generator (pii.fill: valid TC checksum, IBAN
mod-97), only categories 08-lite's regex recognizers cover, so F2 can check the masking. No
person names anywhere (DECISION-24): tickets are signed with a unit, never a name.

Labels are written to a separate file: the fake ticket desk serves only tickets-20.jsonl, so the
expected class never reaches the model.
"""

import json
import random
from pathlib import Path

from . import pii, write_text

CLASSES = ["access", "billing", "bug", "how_to", "other"]

# (channel, received_at, subject, body template, class, rationale)
TICKETS = [
    (
        "portal",
        "2025-11-03T08:12",
        "Yeni teknisyen için HBYS hesabı",
        "Biyomedikal birimimize bu hafta yeni bir teknisyen başladı. Hastane bilgi yönetim "
        "sistemine ve cihaz envanteri ekranına giriş yapabilmesi için hesap açılmasını rica "
        "ederiz.\nBiyomedikal Birimi",
        "access",
        "Yeni kullanıcı için hesap açılması isteniyor.",
    ),
    (
        "email",
        "2025-11-03T09:40",
        "Şifre sıfırlama bağlantısı gelmiyor",
        "Merhaba, iki gündür sisteme giremiyorum ve şifre sıfırlama bağlantısı da gelmiyor. "
        "Kimlik doğrulaması için TC kimlik numaram {TR_NATIONAL_ID}, bana {TR_PHONE} "
        "numarasından ulaşabilirsiniz.\nDahiliye Sekreterliği",
        "access",
        "Hesaba giriş ve şifre sıfırlama sorunu.",
    ),
    (
        "portal",
        "2025-11-03T11:05",
        "Arıza kaydı kaydedilemiyor",
        "Cihaz envanteri ekranında yeni arıza kaydı girip Kaydet düğmesine bastığımızda "
        '"Beklenmeyen hata" uyarısı çıkıyor ve kayıt oluşmuyor. Sorun CHZ-00412 kodlu '
        "monitörde ve diğer cihazlarda da aynı.\nKardiyoloji Servisi",
        "bug",
        "Sistem işlevi hata veriyor, kayıt oluşmuyor.",
    ),
    (
        "email",
        "2025-11-04T08:55",
        "Bakım faturası sözleşme bedelinden yüksek",
        "Cihaz bakım ve onarım sözleşmesi kapsamında gelen ekim ayı faturası, sözleşmedeki "
        "aylık bedelden yüksek görünüyor. Fark kalemlerinin kontrol edilmesini istiyoruz.\n"
        "Satın Alma Birimi",
        "billing",
        "Fatura tutarı ile sözleşme bedeli arasında fark.",
    ),
    (
        "portal",
        "2025-11-04T10:20",
        "Arıza kaydını kapatma adımları",
        "Teknik servis cihazı onardı. Arıza kaydını çözüldü olarak işaretleyip kesinti "
        "süresini nereye yazmam gerektiğini adım adım anlatabilir misiniz?\nOrtopedi Servisi",
        "how_to",
        "Bir işlemin nasıl yapılacağı soruluyor; hata yok.",
    ),
    (
        "portal",
        "2025-11-04T14:47",
        "Yeni bölümümün cihaz listesi görünmüyor",
        "Geçen hafta Nöroloji'den Yoğun Bakım'a geçtim. Sisteme girebiliyorum ama hâlâ eski "
        "bölümün cihazlarını görüyorum, Yoğun Bakım cihazlarını açamıyorum.\nYoğun Bakım "
        "Hemşireliği",
        "access",
        "Dolaylı: giriş var ama yeni bölüm için yetki tanımlanmamış.",
    ),
    (
        "email",
        "2025-11-05T09:10",
        "Ödeme hesabı değişikliği",
        "Tedarikçi firmamızın banka hesabı değişti. Bundan sonraki ödemelerin {TR_IBAN} "
        "numaralı hesaba yapılmasını rica ederiz. Yazılı teyit {EMAIL_ADDRESS} adresine "
        "gönderilebilir.\nLaboratuvar Kiti Tedarikçisi Muhasebe Birimi",
        "billing",
        "Ödeme yapılacak hesap bilgisi değişikliği.",
    ),
    (
        "portal",
        "2025-11-05T13:30",
        "Doluluk raporu boş geliyor",
        "Bölüm doluluk raporunda tarih aralığını ekim ayı seçince tablo tamamen boş geliyor; "
        "eylül seçince veriler görünüyor. Ekim ayında servis tamamen doluydu.\nGenel Cerrahi "
        "Servisi",
        "bug",
        "Rapor yanlış sonuç veriyor.",
    ),
    (
        "portal",
        "2025-11-06T08:05",
        "Envantere yeni cihaz ekleme",
        "Bölümümüze yeni bir ultrason cihazı geldi. Envantere nasıl ekleriz, cihaz kodunu "
        "biz mi veriyoruz yoksa sistem mi üretiyor?\nKadın Doğum Servisi",
        "how_to",
        "Yeni kaydın nasıl girileceği soruluyor.",
    ),
    (
        "email",
        "2025-11-06T12:15",
        "Toplantı salonu rezervasyonu",
        "Gelecek perşembe öğleden sonra konferans salonunu bölüm toplantısı için ayırmak "
        "istiyoruz. Bu talep sizin biriminize mi, idari işlere mi iletilmeli?\nPsikiyatri "
        "Servisi",
        "other",
        "Bilgi işlem ve biyomedikal kapsamı dışında genel talep.",
    ),
    (
        "portal",
        "2025-11-07T07:50",
        "Mobil uygulamada nöbet bildirimi gelmiyor",
        "Güncellemeden sonra mobil uygulamada nöbet değişikliği bildirimleri artık gelmiyor. "
        "Telefonun bildirim ayarları açık. Geri dönüş için {TR_PHONE} numaralı dahili cep "
        "hattı kullanılabilir.\nAcil Servis",
        "bug",
        "Güncelleme sonrası işlev çalışmıyor.",
    ),
    (
        "email",
        "2025-11-07T10:35",
        "Nöbette uzaktan erişim talebi",
        "Gece nöbetlerinde cihaz alarm kayıtlarına evden bakabilmemiz için uzaktan erişim "
        "(VPN) yetkisi talep ediyoruz.\nBiyomedikal Birimi",
        "access",
        "Uzaktan erişim yetkisi talebi.",
    ),
    (
        "email",
        "2025-11-07T15:20",
        "Lisans yenilemesinde iki belge",
        "Yazılım lisans yenilemesi için bu ay aynı tutarda iki ayrı belge düzenlenmiş "
        "görünüyor. Muhasebe kayıtlarımızda mükerrer borç oluştu, hangisinin geçerli olduğunu "
        "teyit eder misiniz?\nMali İşler Müdürlüğü",
        "billing",
        "Dolaylı: aynı lisans için mükerrer kesilen fatura.",
    ),
    (
        "portal",
        "2025-11-10T09:00",
        "Raporu otomatik e-postayla gönderme",
        "Haftalık arıza özet raporunun her pazartesi {EMAIL_ADDRESS} adresine kendiliğinden "
        "gönderilmesini nasıl ayarlayabilirim?\nKalite Birimi",
        "how_to",
        "Zamanlanmış rapor ayarının nasıl yapılacağı soruluyor.",
    ),
    (
        "portal",
        "2025-11-10T11:25",
        "Etiket yazıcısı yanlış barkod basıyor",
        "Son yazılım güncellemesinden beri etiket yazıcısı cihaz kodunun son iki hanesini "
        "basmıyor; okuyucu barkodu tanımıyor.\nMerkezi Sterilizasyon Ünitesi",
        "bug",
        "Güncelleme sonrası hatalı çıktı.",
    ),
    (
        "email",
        "2025-11-10T16:40",
        "Hesabım kilitlendi",
        "Birkaç kez hatalı şifre girdiğim için hesabım kilitlendi. Kurumsal e-posta adresim "
        "{EMAIL_ADDRESS}, TC kimlik numaram {TR_NATIONAL_ID}. Kilidin açılmasını rica "
        "ederim.\nÜroloji Polikliniği",
        "access",
        "Kilitlenen hesabın açılması isteniyor.",
    ),
    (
        "portal",
        "2025-11-11T08:30",
        "Bilgi güvenliği eğitimi tarihi",
        "Bu yıl zorunlu bilgi güvenliği farkındalık eğitimi ne zaman yapılacak, servis "
        "çalışanları hangi oturuma katılmalı?\nPediatri Servisi",
        "other",
        "Eğitim takvimi sorusu; destek talebi değil.",
    ),
    (
        "portal",
        "2025-11-11T13:55",
        "Sabah girilen kayıtlar kayboluyor",
        "Sabah vardiyasında girdiğimiz arıza kayıtları öğleden sonra listede yok. Yeniden "
        "girmek zorunda kalıyoruz, iki gündür aynı durum.\nNefroloji Servisi",
        "bug",
        "Dolaylı: kayıtlar sistemden düşüyor (veri kaybı hatası).",
    ),
    (
        "email",
        "2025-11-12T10:10",
        "Danışmanlık faturasında KDV farkı",
        "Yönetim danışmanlığı hizmet faturasında KDV oranı sözleşmedekinden farklı "
        "uygulanmış. Düzeltilmiş fatura talep ediyoruz.\nMali İşler Müdürlüğü",
        "billing",
        "Faturada vergi hesabı hatası.",
    ),
    (
        "portal",
        "2025-11-12T14:05",
        "Şifre değiştirme ekranına ulaşamıyorum",
        "Sistem 90 günlük şifre değişikliği uyarısı veriyor ama şifremi hangi menüden "
        "değiştireceğimi bulamadım. Yol tarifi verebilir misiniz?\nEndokrinoloji Polikliniği",
        "how_to",
        "Giriş çalışıyor; şifre değiştirme adımı soruluyor (erişim sorunu değil).",
    ),
]


def records(rng: random.Random) -> tuple[list[dict], dict]:
    if len(TICKETS) != 20:
        raise ValueError(f"{len(TICKETS)} tickets, expected 20")
    tickets, labels = [], {}
    for n, (channel, received, subject, body, cls, why) in enumerate(TICKETS, start=1):
        if cls not in CLASSES:
            raise ValueError(f"unknown class {cls}")
        text, entities = pii.fill(body, rng)
        tid = f"tkt-{n:03d}"
        tickets.append(
            {
                "id": tid,
                "channel": channel,
                "received_at": f"{received}:00+03:00",
                "subject": subject,
                "body": text,
                "pii": entities,
            }
        )
        labels[tid] = {"class": cls, "rationale": why}
    return tickets, {"classes": CLASSES, "labels": labels}


def generate(rng: random.Random, out: Path, seed: int) -> None:
    tickets, labels = records(rng)
    base = out / "tickets"
    lines = [json.dumps(t, ensure_ascii=False) for t in tickets]
    write_text(base / "tickets-20.jsonl", "\n".join(lines) + "\n")
    write_text(base / "labels.json", json.dumps(labels, ensure_ascii=False, indent=2) + "\n")
