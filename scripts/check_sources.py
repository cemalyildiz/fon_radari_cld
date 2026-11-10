"""
Fon Radari - resmi kaynak sayfa izleme.

GitHub Actions'ta gunluk calisir. Acik gorunen (acik / yakinda kapaniyor /
cerceve) her kaydin resmi kaynak sayfasini acar ve su sorulari sorar:

  1. Sayfa, kaydin son teyit edildigi gunden beri DEGISTI mi?
     (gorunur metnin ozeti/hash'i teyit anindaki ozetle karsilastirilir)
  2. Kayittaki son basvuru tarihi sayfada HALA geciyor mu?
  3. Sayfada "uzatildi", "kapandi", "iptal", "yururlukten kaldirildi" gibi
     durum degisikligi ifadeleri var mi?

Hicbir kaydi KENDISI DEGISTIRMEZ. Bulgulari data/kaynak_izleme.json
dosyasina yazar; site bu bulgulari kartta "yeniden teyit gerekli" olarak
gosterir, gunluk rapor issue'su da listeler. Kayit, DOGRULAMA.md'deki
adimlarla yeniden teyit edilip dogrulama.tarih guncellendiginde, o gunku
sayfa ozeti yeni referans olur.

Kurum siteleri bazen otomatik istekleri engeller (TUBITAK "Erisim engellendi"
dondurebilir). Bu durum hata sayilmaz, "erisilemedi" olarak raporlanir.
Yalnizca standart kutuphane kullanir.
"""
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dogrulama_kurallari import cagri_durumu  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CALLS_PATH = ROOT / "data" / "calls.json"
IZLEME_PATH = ROOT / "data" / "kaynak_izleme.json"

UA = "FonRadariBot/1.0 (+https://github.com/cemalyildiz/fon_radari_cld)"
ZAMAN_ASIMI = 30
ISTEK_ARASI_SN = 3  # ayni siteye art arda yuklenmemek icin

AYLAR_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
AYLAR_TR_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
AYLAR_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

DURUM_IFADELERI = re.compile(
    # Yalnizca gerceklesmis durum degisiklikleri: "uzatilsa dahi" gibi kosul cumleleri yakalanmamali
    r"uzatılmıştır|uzatıldı\b|başvurular(ı)? kapan(dı|mıştır)|başvuruya kapatıl(dı|mıştır)|iptal edil(di|miştir)|"
    r"yürürlükten kaldır|askıya alın|deadline (has been )?extended|call (is )?closed|cancelled",
    re.I,
)
ENGEL_IFADELERI = re.compile(r"erişim engellendi|access denied|captcha|cloudflare", re.I)


class MetinCikarici(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parcalar, self._atla = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg", "header", "footer", "nav"):
            self._atla += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg", "header", "footer", "nav") and self._atla:
            self._atla -= 1

    def handle_data(self, data):
        if not self._atla and data.strip():
            self.parcalar.append(data.strip())


def gorunur_metin(html):
    p = MetinCikarici()
    p.feed(html)
    metin = " ".join(p.parcalar)
    # Her ziyarette degisebilen gurultuyu at (saat, sayac, telif yili vb.)
    metin = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b", "", metin)
    metin = re.sub(r"©\s*\d{4}", "", metin)
    return re.sub(r"\s+", " ", metin).strip()


def ozet(metin):
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()[:16]


def tarih_bicimleri(iso):
    """'2026-11-11' -> sayfada aranabilecek yazimlar."""
    y, m, g = int(iso[:4]), int(iso[5:7]), int(iso[8:10])
    return [
        "%d %s %d" % (g, AYLAR_TR[m - 1], y), "%02d %s %d" % (g, AYLAR_TR[m - 1], y),
        "%d %s %d" % (g, AYLAR_TR_KISA[m - 1], y), "%02d %s %d" % (g, AYLAR_TR_KISA[m - 1], y),
        "%02d.%02d.%d" % (g, m, y), "%d.%d.%d" % (g, m, y), "%02d/%02d/%d" % (g, m, y),
        "%d %s %d" % (g, AYLAR_EN[m - 1], y), "%s %d, %d" % (AYLAR_EN[m - 1], g, y),
        iso[:10],
    ]


def tr_katla(s):
    """Turkce harf/buyuk-kucuk farkini yok sayan karsilastirma bicimi.
    str.lower() Turkce bilmez ('ARALIK' -> 'aralik'), bu yuzden once eslenir."""
    s = s.replace("İ", "i").replace("I", "ı").lower()
    return s.translate(str.maketrans("ıişğüöç", "iisguoc"))


def tarih_sayfada_mi(iso, metin):
    m = tr_katla(metin)
    return any(tr_katla(b) in m for b in tarih_bicimleri(iso))


def getir(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=ZAMAN_ASIMI) as r:
        tur = r.headers.get("Content-Type", "")
        govde = r.read(3_000_000)
        return r.status, tur, govde


def izlenecek_url(call):
    """HTML sayfasini tercih et; dogrulama kaynagi PDF ise kaynak_url'e don."""
    dk = (call.get("dogrulama") or {}).get("kaynak", "")
    if dk and not re.search(r"\.pdf($|\?)", dk, re.I):
        return dk
    return call.get("kaynak_url", "")


def kontrol_et(call, onceki):
    url = izlenecek_url(call)
    sonuc = {"url": url, "son_kontrol": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "bulgular": []}
    teyit = (call.get("dogrulama") or {}).get("tarih")
    try:
        try:
            status, tur, govde = getir(url)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            # Gecici ag kesintisi olabilir: bir kez daha dene (HTTP 4xx ise tekrar denemenin anlami yok)
            if isinstance(e, urllib.error.HTTPError) and 400 <= e.code < 500:
                raise
            time.sleep(10)
            status, tur, govde = getir(url)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        sonuc["durum"] = "erisilemedi"
        sonuc["bulgular"].append("sayfa açılamadı: %s" % (getattr(e, "code", None) or e.__class__.__name__))
        return sonuc
    if "pdf" in tur.lower():
        sonuc["durum"] = "izlenemedi"
        sonuc["bulgular"].append("kaynak PDF; sayfa izleme yapılamıyor")
        return sonuc
    metin = gorunur_metin(govde.decode("utf-8", errors="replace"))
    if ENGEL_IFADELERI.search(metin[:2000]) or len(metin) < 200:
        sonuc["durum"] = "erisilemedi"
        sonuc["bulgular"].append("site otomatik isteği engelledi veya boş sayfa döndü")
        return sonuc

    h = ozet(metin)
    sonuc["ozet"] = h
    # Referans: kayit en son teyit edildiginde gorulen sayfa ozeti.
    if onceki and onceki.get("teyit_tarihi") == teyit and onceki.get("referans_ozet"):
        sonuc["teyit_tarihi"], sonuc["referans_ozet"] = teyit, onceki["referans_ozet"]
    else:
        # Kayit yeni teyit edilmis (veya ilk kez izleniyor): bugunku sayfa referans olur.
        sonuc["teyit_tarihi"], sonuc["referans_ozet"] = teyit, h
    degisti = h != sonuc["referans_ozet"]
    if degisti:
        sonuc["bulgular"].append("sayfa, kaydın son teyidinden (%s) bu yana değişti" % teyit)

    bitis = call.get("basvuru_bitis")
    if bitis and not call.get("surekli_acik") and not tarih_sayfada_mi(bitis, metin):
        sonuc["bulgular"].append("kayıttaki son başvuru tarihi (%s) sayfada bulunamadı" % bitis)

    # Teyit gunu okunan sayfada zaten gecen ifade (ör. teyit kaynagi bir "süre uzatildi" duyurusuysa)
    # degerlendirilmis sayilir; yalnizca sayfa teyitten sonra degistiyse bildirilir.
    m = DURUM_IFADELERI.search(metin) if degisti else None
    if m:
        bas = max(0, m.start() - 80)
        sonuc["bulgular"].append("sayfada durum ifadesi: “…%s…”" % metin[bas:m.end() + 80].strip())

    sonuc["durum"] = "yeniden_teyit" if sonuc["bulgular"] else "ok"
    return sonuc


KESIF_PATH = ROOT / "data" / "discovered.json"
# Kurum duyurusunun BASLIGINDA gecen durum degisikligi ifadeleri
DUYURU_DURUM = re.compile(
    r"süresi uzatıl|uzatıldı|uzatılmıştır|erteleme|ertelendi|takvim(i)? güncellen|tarih(i|leri)? değiş|"
    r"kapandı|kapatıldı|iptal|askıya|extended|postponed|closed|cancelled",
    re.I,
)
GENEL_KELIMELER = {"destek", "programi", "program", "programı", "cagrisi", "çağrısı", "cagri", "çağrı",
                   "yili", "yılı", "2026", "2027", "proje", "projeleri", "için", "icin", "tübitak", "tubitak",
                   "kosgeb", "ve", "the", "call", "for", "kobi", "kobİ", "ar-ge", "dönem", "donem"}


def kelime_kumesi(metin):
    """Ayirt edici kelimeler (tam kelime; genel ve sayisal kelimeler haric)."""
    genel = {tr_katla(g) for g in GENEL_KELIMELER}
    return {w for w in re.findall(r"[a-z]{4,}", tr_katla(metin))
            if w not in genel and not w.startswith("basvuru") and not w.startswith("teknoloji")}


def program_kodlari(call):
    """Basliktaki/id'deki 4 haneli program kodlari (1507, 1707, 1831...). Yillar haric."""
    metin = "%s %s" % (call.get("baslik", ""), call.get("id", ""))
    return {k for k in re.findall(r"(?<!\d)(\d{4})(?!\d)", metin) if not 2000 <= int(k) <= 2099}


def ilgili_duyurular(call, adaylar):
    """Kaydin son teyidinden SONRA gorulen ve basliginda durum degisikligi gecen kurum duyurulari.
    Eslesme: program kodu (ör. 1507) ya da basliktaki ayirt edici kelimelerden en az ikisi."""
    teyit = (call.get("dogrulama") or {}).get("tarih", "")
    kodlar = program_kodlari(call)
    kelimeler = kelime_kumesi(call.get("baslik", ""))
    sonuc = []
    for a in adaylar:
        b = a.get("baslik", "")
        if not DUYURU_DURUM.search(b) or (a.get("ilk_gorulme", "")[:10] <= teyit):
            continue
        b_kodlar = set(re.findall(r"(?<!\d)(\d{4})(?!\d)", b))
        if kodlar:
            eslesti = bool(kodlar & b_kodlar)
        else:
            eslesti = len(kelimeler & kelime_kumesi(b)) >= 2
        if eslesti:
            sonuc.append({"baslik": b, "url": a.get("url", ""), "ilk_gorulme": a.get("ilk_gorulme", "")[:10]})
    return sonuc


def main():
    calls = json.load(open(CALLS_PATH, encoding="utf-8")).get("calls", [])
    onceki = {}
    if IZLEME_PATH.exists():
        onceki = json.load(open(IZLEME_PATH, encoding="utf-8")).get("kayitlar", {})
    adaylar = json.load(open(KESIF_PATH, encoding="utf-8")).get("adaylar", []) if KESIF_PATH.exists() else []

    kayitlar = {}
    for c in calls:
        if cagri_durumu(c) not in ("acik", "yakinda-kapaniyor", "cerceve"):
            continue
        s = kontrol_et(c, onceki.get(c["id"]))
        # Kurumun yeni duyurusu (süre uzatımı, iptal vb.) kaynak sayfa erisilemese bile isaretlenir
        duyurular = ilgili_duyurular(c, adaylar)
        if duyurular:
            s["duyurular"] = duyurular
            for d in duyurular:
                s["bulgular"].insert(0, "kurum, son teyitten sonra yeni duyuru yayımladı: “%s” (%s)" % (d["baslik"], d["url"]))
            s["durum"] = "yeniden_teyit"
        kayitlar[c["id"]] = s
        print("  %-36s %-14s %s" % (c["id"][:36], s["durum"], " | ".join(s["bulgular"])[:150]))
        time.sleep(ISTEK_ARASI_SN)

    with open(IZLEME_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "aciklama": "Resmi kaynak sayfa izleme sonuclari (scripts/check_sources.py). Kayitlari degistirmez; yalnizca yeniden teyit gereken kayitlari isaretler.",
                   "kayitlar": kayitlar}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    from collections import Counter
    print("[ozet]", dict(Counter(s["durum"] for s in kayitlar.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
