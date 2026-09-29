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

ONEMLI SINIRLAMA (seffaflik icin):
Bu betik kurum sitelerini TARAMAZ (scraping yapmaz). TUBITAK, KOSGEB,
Ticaret Bakanligi, SSB, Kalkinma Ajanslari ve AB portallarinin her biri
farkli yapida oldugundan, guvenilir otomatik kesif icin her kaynaga ayri
bir tarayici yazilmali ve bakimi surdurulmelidir. Dolayisiyla:
  - Mevcut cagrilarin DURUMU (acik/kapali/kac gun kaldi) otomatik guncellenir.
  - YENI cagrilarin kesfi ve eklenmesi hala elle/AI destekli yapilir.
Bu dosya, ileride kaynak bazli tarayicilar eklenmek uzere tasarlanmistir.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "calls.json"
ALERTS_PATH = ROOT / "data" / "alerts.json"

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
    end = datetime.fromisoformat(bitis).replace(tzinfo=timezone.utc)
    kalan = (end - now).days
    if kalan < 0:
        return "kapali", kalan
    if kalan <= UYARI_ESIGI_GUN:
        return "yakinda-kapaniyor", kalan
    return "acik", kalan


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    calls = payload.get("calls", [])
    now = datetime.now(timezone.utc)

    hatalar = []
    gorulen_idler = set()
    for i, call in enumerate(calls):
        for alan in ZORUNLU_ALANLAR:
            if not call.get(alan):
                hatalar.append("[%d] '%s' alani eksik veya bos" % (i, alan))
        cid = call.get("id")
        if cid in gorulen_idler:
            hatalar.append("[%d] tekrar eden id: %s" % (i, cid))
        gorulen_idler.add(cid)
        if call.get("kategori") not in ("ulusal", "uluslararasi"):
            hatalar.append("[%d] gecersiz kategori: %s" % (i, call.get("kategori")))
        for tarih_alani in ("basvuru_baslangic", "basvuru_bitis"):
            deger = call.get(tarih_alani)
            if deger:
                try:
                    datetime.fromisoformat(deger)
                except ValueError:
                    hatalar.append("[%d] bozuk tarih %s: %s" % (i, tarih_alani, deger))

    if hatalar:
        print("HATA: data/calls.json dogrulamadan gecemedi:")
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

    print("[bilgi] last_checked guncellendi: %s" % payload["last_checked"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
