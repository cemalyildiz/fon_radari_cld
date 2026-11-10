"""
Fon Radari - AB Funding & Tenders Portali'ndaki acik ve yakinda acilacak cagrilar.

Kaynak: Avrupa Komisyonu'nun resmi arama servisi (Funding & Tenders Portal'in kendi
kullandigi servis): https://api.tech.ec.europa.eu/search-api/prod/rest/search

Neden elle eklenmiyor: Portalda ayni anda yuzlerce acik/planlanan cagri (topic) olur.
Bu betik onlari her gun resmi servisten ceker ve data/ab_cagrilari.json'a yazar.
Yazilan her alan dogrudan servisten gelir; ceviri, tahmin veya yorum eklenmez.

Portal verisinin bilinen sorunlari ve alinan onlemler:
  * Durum etiketi guvenilir degil: 2024'te kapanmis yuzlerce cagri hala "Open"/
    "Forthcoming" etiketli. -> Durum SON BASVURU TARIHINDEN hesaplanir; son tarihi
    gecmis kayitlar alinmaz.
  * Ayni cagri birden fazla kez donebiliyor. -> identifier ile tekillestirilir.
  * Saat/saat dilimi tutarsiz (bazi kayitlarda 00:00Z, bazilarinda Bruksel saati
    UTC gibi yazilmis). -> Yalnizca TARIH kullanilir; saat icin resmi sayfa esastir.
  * Bir kismi AB'nin dogrudan cagrisi degil, AB destekli projelerin ucuncu taraflara
    actigi alt cagrilardir (kaskad fonlama, "type 8"). -> Ayrica etiketlenir.

Turkiye'den katilim uygunlugu cagri bazinda farklidir ve servis bunu vermez;
sitede her kayitta "cagri kosullarindan kontrol edin" uyarisi gosterilir.

Kullanim:
  python scripts/fetch_eu_calls.py                 # servisten cek
  python scripts/fetch_eu_calls.py --dosya ham.json  # onceden indirilmis ham yanittan (test)
"""
import json
import re
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CIKTI = ROOT / "data" / "ab_cagrilari.json"
API = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
SAYFA = 100
TSI = timezone(timedelta(hours=3))

# type: 1 = AB hibe cagrisi (topic), 2 = dis yardim (EuropeAid/INTPA) teklif cagrisi,
#       8 = AB destekli projelerin ucuncu taraflara actigi alt cagri (kaskad fonlama)
# status: 31094501 = Forthcoming, 31094502 = Open
SORGU = {"bool": {"must": [
    {"terms": {"type": ["1", "2", "8"]}},
    {"terms": {"status": ["31094501", "31094502"]}},
]}}
TUR = {"1": "ab-cagri", "2": "dis-yardim", "8": "kaskad"}

# Yalnizca kesin bilinen program adlari; bilinmeyen kodlar oldugu gibi gosterilir.
PROGRAM_ADLARI = {
    "HORIZON": "Horizon Europe", "ERC": "Horizon Europe (ERC)", "EURATOM": "Euratom",
    "LIFE": "LIFE", "DIGITAL": "Digital Europe", "EDF": "Avrupa Savunma Fonu (EDF)",
    "CEF": "Connecting Europe Facility (CEF)", "CREA": "Yaratıcı Avrupa (Creative Europe)",
    "CERV": "CERV (Vatandaşlar, Eşitlik, Haklar ve Değerler)", "ERASMUS": "Erasmus+",
    "EU4H": "EU4Health", "InnovFund": "Innovation Fund", "SMP": "Tek Pazar Programı (SMP)",
    "ESC": "Avrupa Dayanışma Programı (ESC)", "EMFAF": "EMFAF (Denizcilik, Balıkçılık ve Su Ürünleri)",
    "I3": "Bölgelerarası İnovasyon Yatırımları (I3)", "ESF": "ESF+", "JUST": "Adalet Programı (JUST)",
    "ISF": "İç Güvenlik Fonu (ISF)", "NDICI": "NDICI - Küresel Avrupa", "PPPA": "Pilot Projeler ve Hazırlık Eylemleri",
    "JTM": "Adil Geçiş Mekanizması (JTM)", "RENEWFM": "AB Yenilenebilir Enerji Finansman Mekanizması",
    "PERI": "Pericles IV", "EuropeAid": "Dış Yardım (EuropeAid / INTPA)",
}


def ara(sayfa):
    sinir = uuid.uuid4().hex
    parca = lambda ad, icerik: (
        '--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s.json"\r\n'
        "Content-Type: application/json\r\n\r\n%s\r\n" % (sinir, ad, ad, icerik))
    govde = parca("query", json.dumps(SORGU)) + parca("languages", '["en"]') + "--%s--\r\n" % sinir
    url = "%s?apiKey=SEDIA&text=***&pageSize=%d&pageNumber=%d" % (API, SAYFA, sayfa)
    req = urllib.request.Request(url, data=govde.encode(), method="POST",
                                 headers={"Content-Type": "multipart/form-data; boundary=" + sinir,
                                          "User-Agent": "FonRadariBot/1.0 (+https://github.com/cemalyildiz/fon_radari_cld)"})
    for deneme in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception:
            if deneme == 2:
                raise
            time.sleep(15)


def hepsini_cek():
    sonuc, sayfa = [], 1
    while True:
        d = ara(sayfa)
        sonuc += d.get("results", [])
        if len(d.get("results", [])) < SAYFA or sayfa >= 60:
            return sonuc, d.get("totalResults")
        sayfa += 1
        time.sleep(1)


def ilk(m, alan, varsayilan=""):
    v = m.get(alan) or []
    return v[0] if v else varsayilan


def tarih(s):
    """'2027-10-07T00:00:00.000+0000' veya '2027-10-07' -> '2027-10-07' (saat bilinçli olarak atilir)."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s or "")
    return m.group(1) if m else None


def butce(m, kimlik):
    """budgetOverview icinden bu cagriya (topic) ait satirlar: toplam butce, proje basina katki, beklenen hibe sayisi."""
    try:
        bo = json.loads(ilk(m, "budgetOverview", "{}"))
    except ValueError:
        return None
    satirlar = [x for liste in (bo.get("budgetTopicActionMap") or {}).values() for x in liste
                if str(x.get("action", "")).split(" ")[0] == kimlik]
    if not satirlar:
        return None
    toplam = 0.0
    for x in satirlar:
        for v in (x.get("budgetYearMap") or {}).values():
            try:
                toplam += float(v)
            except (TypeError, ValueError):
                pass
    mins = [x["minContribution"] for x in satirlar if isinstance(x.get("minContribution"), (int, float))]
    maxs = [x["maxContribution"] for x in satirlar if isinstance(x.get("maxContribution"), (int, float))]
    hibe = [x["expectedGrants"] for x in satirlar if isinstance(x.get("expectedGrants"), (int, float))]
    return {
        "toplam_eur": round(toplam) if toplam else None,
        "proje_min_eur": min(mins) if mins else None,
        "proje_max_eur": max(maxs) if maxs else None,
        "beklenen_proje": sum(hibe) if hibe else None,
    }


def resmi_url(u):
    return bool(re.match(r"^https://([a-z0-9-]+\.)*europa\.eu/", u or ""))


def donustur(r, bugun):
    m = r.get("metadata", {})
    tur = TUR.get(ilk(m, "type"))
    kimlik = ilk(m, "identifier").strip()
    url = ilk(m, "url") or r.get("url", "")
    baslik = (ilk(m, "title") if tur == "ab-cagri" else (ilk(m, "callTitle") or ilk(m, "title"))).strip()
    if not (tur and kimlik and baslik and resmi_url(url)):
        return None, "eksik alan veya resmi olmayan baglanti"

    # Son tarihler: deadlineDate + actions[].deadlineDates (cok asamali / cok kesimli cagrilar)
    sonlar = {tarih(x) for x in m.get("deadlineDate", [])}
    planlanan_acilis = None
    try:
        for a in json.loads(ilk(m, "actions", "[]")):
            sonlar |= {tarih(x) for x in a.get("deadlineDates", [])}
            planlanan_acilis = planlanan_acilis or tarih(a.get("plannedOpeningDate"))
    except ValueError:
        pass
    sonlar = sorted(x for x in sonlar if x)
    if not sonlar:
        return None, "son basvuru tarihi yok"
    model = ilk(m, "deadlineModel")
    # Yeni bir basvuru sahibinin basvurabilecegi tarihler (Eureka hatasindan ders: ikinci asama sayilmaz)
    if model == "two-stage":
        basvuru, sonraki_asama = sonlar[:1], sonlar[1:]
    elif model == "multiple cut-off":
        basvuru, sonraki_asama = [d for d in sonlar if d >= bugun], []
    else:
        basvuru, sonraki_asama = sonlar[-1:], []
    if not basvuru or basvuru[-1] < bugun:
        return None, "yeni basvuru tarihi gecmis (portal etiketi guncel degil)"

    onek = "EuropeAid" if kimlik.startswith("EuropeAid") else kimlik.split("-")[0]
    kayit = {
        "id": kimlik,
        "baslik": baslik,
        "url": url,
        "tur": tur,
        "program_kodu": onek,
        "program": PROGRAM_ADLARI.get(onek, onek),
        "cagri": " - ".join(x for x in (ilk(m, "callIdentifier"), ilk(m, "callTitle")) if x) if tur == "ab-cagri" else "",
        "eylem_turu": ", ".join(m.get("typesOfAction", [])),
        "baslangic": tarih(ilk(m, "startDate")) or planlanan_acilis,
        "basvuru_tarihleri": basvuru,
        "ikinci_asama_tarihleri": sonraki_asama,
        "asama": model,
        "portal_durum": {"31094501": "Forthcoming", "31094502": "Open"}.get(ilk(m, "status"), ""),
    }
    if tur == "ab-cagri":
        kayit["butce"] = butce(m, kimlik)
    else:
        b = ilk(m, "budget")
        try:
            kayit["butce"] = {"toplam_eur": round(float(b))} if b else None
        except ValueError:
            kayit["butce"] = None
    if tur == "kaskad":
        kayit["duzenleyen"] = " - ".join(x for x in (ilk(m, "projectAcronym"), ilk(m, "projectName")) if x)
        kayit["ust_cagri"] = kimlik
        kayit["id"] = "%s#%s" % (kimlik, ilk(m, "ccm2Id"))  # ayni ust cagri altinda birden cok alt cagri olabilir
        if len(basvuru) > 1:
            # Alt cagrilarda "multiple cut-off" etiketi her zaman ayri kesim anlamina gelmiyor
            # (ön başvuru + tam başvuru olabilir); kullaniciya acikca soylenir.
            kayit["tarih_notu"] = "Birden fazla tarih var; her birinin yeni başvuruya açık bir kesim mi, yoksa sonraki aşama mı olduğu çağrı sayfasında yazar."
    if tur == "dis-yardim":
        kayit["hedef_ulke"] = kimlik.split("/")[-1]
    return kayit, None


def main():
    bugun = datetime.now(TSI).strftime("%Y-%m-%d")
    if "--dosya" in sys.argv:
        ham, toplam = json.load(open(sys.argv[sys.argv.index("--dosya") + 1], encoding="utf-8")), None
    else:
        try:
            ham, toplam = hepsini_cek()
        except Exception as e:
            print("[ab] servis okunamadi (%s); mevcut dosya korunuyor" % e.__class__.__name__)
            return 1

    kayitlar, elenen = {}, {}
    for r in ham:
        k, neden = donustur(r, bugun)
        if neden:
            elenen[neden] = elenen.get(neden, 0) + 1
            continue
        kayitlar.setdefault(k["id"], k)  # tekillestirme
    liste = sorted(kayitlar.values(), key=lambda k: (next(d for d in k["basvuru_tarihleri"] if d >= bugun), k["id"]))

    # Guvenlik: servis gecici olarak eksik donerse iyi veriyi ezme
    if CIKTI.exists() and "--dosya" not in sys.argv:
        onceki = len(json.load(open(CIKTI, encoding="utf-8")).get("cagrilar", []))
        if onceki and len(liste) < onceki * 0.5:
            print("[ab] %d kayit geldi, onceki %d; beklenmedik dusus - dosya guncellenmedi" % (len(liste), onceki))
            return 1

    with open(CIKTI, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kaynak": "Avrupa Komisyonu Funding & Tenders Portalı resmî arama servisi (api.tech.ec.europa.eu)",
            "aciklama": "Son başvuru tarihi bugün veya sonrasında olan açık/planlanan çağrılar. Alanlar servisten olduğu gibi alınır; "
                        "saat ve Türkiye'nin katılım uygunluğu için resmî çağrı sayfası esastır.",
            "servis_toplam": toplam,
            "elenen": elenen,
            "cagrilar": liste,
        }, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    from collections import Counter
    print("[ab] %d cagri yazildi | turler: %s | elenen: %s" % (
        len(liste), dict(Counter(k["tur"] for k in liste)), elenen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
