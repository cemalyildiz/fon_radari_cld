"""
Fon Radari - otomatik veri kontrol betigi.

GitHub Actions tarafindan gunluk olarak calistirilir ve:
  1. data/calls.json dosyasinin bicimini ve zorunlu alanlarini dogrular,
  2. "last_checked" zaman damgasini gunceller,
  3. Suresi dolmus cagrilari raporlar (arayuzde zaten otomatik arsivlenirler),
  4. 14 gun icinde kapanacak cagrilar icin UYARI uretir ve bunlari
     data/alerts.json dosyasina yazar - site bu dosyayi okuyup ust kisimda
     bir uyari seridi gosterir,
  5. Bir sorun varsa (bozuk tarih, eksik alan) hata koduyla cikar; boylece
     GitHub Actions kirmizi gorunur ve fark edilir.

Kayit dogrulama kurallari scripts/dogrulama_kurallari.py icindedir (insan
icin aciklamasi: DOGRULAMA.md). Kural ihlali olan bir kayit varsa betik
hata koduyla cikar. Uyarilar (eski teyit, kismi teyit) data/dogrulama_raporu.json
dosyasina yazilir; site ve gunluk rapor issue'su bu dosyayi kullanir.
Yeni cagri kesfi: scripts/discover_calls.py. Kaynak sayfa izleme: scripts/check_sources.py.
"""
import json
import sys
from datetime import datetime, timedelta, timezone

TSI = timezone(timedelta(hours=3))  # Turkiye saati (yaz saati uygulamasi yok)
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dogrulama_kurallari import hepsini_denetle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "calls.json"
ALERTS_PATH = ROOT / "data" / "alerts.json"
RAPOR_PATH = ROOT / "data" / "dogrulama_raporu.json"

UYARI_ESIGI_GUN = 14
ZORUNLU_ALANLAR = ["id", "kategori", "baslik", "kurum", "ozet", "kaynak_url"]


def durum_hesapla(call, now):
    """Arayuzdeki (js/app.js) computeStatus mantiginin birebir karsiligi."""
    if call.get("yururlukten_kaldirildi"):
        return "kaldirildi", None
    if call.get("cerceve_program"):
        return "cerceve", None
    if call.get("surekli_acik"):
        return "surekli", None
    bitis = call.get("basvuru_bitis")
    if not bitis:
        return "acik", None
    # Saatsiz bitis tarihi o gunun sonu (23:59:59 TSI) kabul edilir; js/app.js ile ayni kural.
    end = datetime.fromisoformat(bitis)
    if len(bitis) == 10:
        end = end.replace(hour=23, minute=59, second=59)
    if end.tzinfo is None:
        end = end.replace(tzinfo=TSI)
    if now > end:
        return "kapali", None
    # Kalan TAKVIM gunu, Turkiye tarihine gore (0 = bugun son gun)
    kalan = (end.astimezone(TSI).date() - now.astimezone(TSI).date()).days
    if kalan <= UYARI_ESIGI_GUN:
        return "yakinda-kapaniyor", kalan
    return "acik", kalan


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    calls = payload.get("calls", [])
    now = datetime.now(timezone.utc)

    denetim, hatalar = hepsini_denetle(calls, now)

    if hatalar:
        print("HATA: data/calls.json dogrulama kurallarindan gecemedi (bkz. DOGRULAMA.md):")
        for h in hatalar:
            print("  -", h)
        return 1

    suresi_gecen, yaklasanlar, acik_sayisi = [], [], 0
    for call in calls:
        durum, kalan = durum_hesapla(call, now)
        if durum == "kapali":
            suresi_gecen.append(call["id"])
        elif durum == "yakinda-kapaniyor":
            acik_sayisi += 1
            yaklasanlar.append({
                "id": call["id"],
                "baslik": call["baslik"],
                "kurum": call["kurum"],
                "basvuru_bitis": call["basvuru_bitis"],
                "kalan_gun": kalan,
                "kaynak_url": call["kaynak_url"],
            })
        elif durum in ("acik", "surekli"):
            acik_sayisi += 1

    yaklasanlar.sort(key=lambda x: x["kalan_gun"])

    print("[ozet] toplam %d kayit | %d acik | %d arsivde | %d cagri %d gun icinde kapaniyor"
          % (len(calls), acik_sayisi, len(suresi_gecen), len(yaklasanlar), UYARI_ESIGI_GUN))

    if yaklasanlar:
        print("[uyari] Yaklasan son tarihler:")
        for y in yaklasanlar:
            print("  - %3d gun | %s (%s)" % (y["kalan_gun"], y["baslik"], y["kurum"]))

    payload["last_checked"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with open(ALERTS_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": payload["last_checked"],
            "esik_gun": UYARI_ESIGI_GUN,
            "yaklasan_son_tarihler": yaklasanlar,
        }, f, ensure_ascii=False, indent=2)
        f.write("\n")

    uyarilar = {cid: v["uyarilar"] for cid, v in denetim.items() if v["uyarilar"]}
    basliklar = {c["id"]: c["baslik"] for c in calls}
    with open(RAPOR_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": payload["last_checked"],
            "uyarilar": [{"id": k, "baslik": basliklar.get(k, k), "uyarilar": v} for k, v in uyarilar.items()],
        }, f, ensure_ascii=False, indent=2)
        f.write("\n")
    if uyarilar:
        print("[dogrulama] Insan dikkati gereken %d kayit:" % len(uyarilar))
        for k, v in uyarilar.items():
            for x in v:
                print("  - %s: %s" % (k, x))

    print("[bilgi] last_checked guncellendi: %s" % payload["last_checked"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
