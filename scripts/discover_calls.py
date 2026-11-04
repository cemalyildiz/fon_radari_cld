"""
Fon Radari - YENI CAGRI KESIF katmani.

Kurum sitelerini tarar, data/calls.json'da BULUNMAYAN cagri/program
adaylarini bulur ve data/discovered.json icine bir INCELEME KUYRUGU
olarak yazar.

TASARIM GEREKCESI (onemli):
Bulunan adaylar DOGRUDAN calls.json'a yazilmaz. Cunku bir kaydin
butce, destek orani, kimlerin basvurabilecegi, olcek gibi alanlari
sayfanin serbest metninden guvenilir sekilde cikarilamaz; bu alanlarda
yanlis bilgi, hic bilgi olmamasindan daha zararlidir. Bu yuzden:

  tarama (otomatik)  ->  inceleme kuyrugu  ->  dogrulama  ->  calls.json

Sitede bu adaylar ayri bir "Yeni tespit edilenler - dogrulanmamis"
bolumunde, acik sekilde etiketlenmis halde gosterilir.

Kuyruktaki her kaydin 'durum' alani:
  yeni       : ilk kez goruldu, incelenmedi
  incelendi  : bakildi, calls.json'a eklendi veya elendi (elle isaretlenir)
"""
import json
import re
import sys
import gzip
import io
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALLS_PATH = ROOT / "data" / "calls.json"
DISCOVERED_PATH = ROOT / "data" / "discovered.json"

UA = "Mozilla/5.0 (compatible; FonRadariBot/1.0; +https://github.com/cemalyildiz/fon_radari_cld)"
ZAMAN_ASIMI = 45

# Duyuru/liste sayfalarinda bir linkin "cagri adayi" sayilmasi icin
# baslikta aranan anahtar kelimeler (gurultu filtresi).
ILGI_DESENI = re.compile(
    r"çağrı|cagri|destek program|başvuru|basvuru|hibe|mali destek|"
    r"teklif|program[ıi]\s+aç|açıldı|acildi|duyuru",
    re.I,
)
# Acikca alakasiz olanlari ele (fuar, sergi, ihale, personel alimi vb.)
ELEME_DESENI = re.compile(
    r"sergi|fuar|ihale|personel alım|personel alim|sınav|sinav sonuc|"
    r"ziyaret|protokol imza|iş birliği protokol|basın|basin bulten",
    re.I,
)

KAYNAKLAR = [
    {
        "ad": "TÜBİTAK - Ulusal Destek Programları",
        "url": "https://tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari",
        "kok": "https://tubitak.gov.tr",
        "link_deseni": r"/tr/destekler/(?:destek/)?sanayi/ulusal-destek-programlari/[^\"#?]+",
    },
    {
        "ad": "TÜBİTAK - Duyuru Arşivi",
        "url": "https://tubitak.gov.tr/tr/duyuru",
        "kok": "https://tubitak.gov.tr",
        "link_deseni": r"/tr/(?:duyuru|destekler)/[^\"#?]+",
    },
    {
        "ad": "KOSGEB - Destekler",
        "url": "https://www.kosgeb.gov.tr/site/tr/genel/destekler/3/destekler",
        "kok": "https://www.kosgeb.gov.tr",
        "link_deseni": r"/site/tr/genel/destekdetay/\d+/[^\"#?]+",
    },
    {
        "ad": "KOSGEB - Duyurular",
        "url": "https://www.kosgeb.gov.tr/site/tr/genel/duyurular/1/duyurular",
        "kok": "https://www.kosgeb.gov.tr",
        "link_deseni": r"/site/tr/genel/(?:detay|destekdetay)/\d+/[^\"#?]+",
    },
]


def sayfa_getir(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"}
    )
    with urllib.request.urlopen(req, timeout=ZAMAN_ASIMI) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        return raw.decode("utf-8", "replace")


def metni_temizle(parca):
    t = re.sub(r"<[^>]+>", " ", parca)
    t = re.sub(r"&nbsp;?", " ", t)
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def url_normalize(href, kok):
    href = href.split("#")[0].split("?")[0].rstrip("/")
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return kok + href
    return kok + "/" + href


def kaynak_tara(kaynak):
    """Bir kaynak sayfasindan aday cagri linklerini cikarir."""
    try:
        html = sayfa_getir(kaynak["url"])
    except Exception as e:
        print("  ! %s okunamadi: %s: %s" % (kaynak["ad"], type(e).__name__, e))
        return [], False

    desen = re.compile(kaynak["link_deseni"])
    adaylar = {}
    for href, ic in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        yol = href.split("#")[0].split("?")[0]
        if not desen.search(yol):
            continue
        baslik = metni_temizle(ic)
        if len(baslik) < 12 or len(baslik) > 220:
            continue
        if ELEME_DESENI.search(baslik):
            continue
        if not ILGI_DESENI.search(baslik) and not desen.search(yol):
            continue
        tam = url_normalize(href, kaynak["kok"])
        # Ayni URL birden fazla kez gecerse en uzun basligi tut
        if tam not in adaylar or len(baslik) > len(adaylar[tam]):
            adaylar[tam] = baslik

    return [{"url": u, "baslik": b} for u, b in adaylar.items()], True


def bilinen_urlleri_topla(calls):
    """calls.json'daki kaynak_url'lerden karsilastirma kumesi uretir."""
    bilinen = set()
    for c in calls:
        u = (c.get("kaynak_url") or "").split("#")[0].split("?")[0].rstrip("/")
        if u:
            bilinen.add(u)
    return bilinen


def baslik_anahtari(baslik):
    """Basliklari kabaca eslestirmek icin normalize eder (ayni cagrinin
    farkli URL'lerle tekrar tekrar 'yeni' gorunmesini onler)."""
    t = baslik.lower()
    t = t.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    t = t.replace("ü", "u").replace("ö", "o").replace("ç", "c")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def main():
    if not CALLS_PATH.exists():
        print("HATA: data/calls.json bulunamadi")
        return 1

    with open(CALLS_PATH, encoding="utf-8") as f:
        calls = json.load(f).get("calls", [])

    if DISCOVERED_PATH.exists():
        with open(DISCOVERED_PATH, encoding="utf-8") as f:
            kuyruk_dosya = json.load(f)
    else:
        kuyruk_dosya = {"generated_at": None, "adaylar": []}

    mevcut_kuyruk = kuyruk_dosya.get("adaylar", [])
    bilinen_url = bilinen_urlleri_topla(calls)
    bilinen_url |= {a["url"].rstrip("/") for a in mevcut_kuyruk}

    # calls.json basliklarini da anahtar olarak kullan
    bilinen_anahtar = {baslik_anahtari(c.get("baslik", "")) for c in calls}
    bilinen_anahtar |= {baslik_anahtari(a.get("baslik", "")) for a in mevcut_kuyruk}
    bilinen_anahtar.discard("")

    simdi = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    yeniler = []
    basarili_kaynak = 0

    for kaynak in KAYNAKLAR:
        adaylar, ok = kaynak_tara(kaynak)
        if ok:
            basarili_kaynak += 1
        print("  %-42s %3d aday" % (kaynak["ad"], len(adaylar)))
        for a in adaylar:
            u = a["url"].rstrip("/")
            if u in bilinen_url:
                continue
            ank = baslik_anahtari(a["baslik"])
            if ank in bilinen_anahtar:
                continue
            bilinen_url.add(u)
            bilinen_anahtar.add(ank)
            yeniler.append({
                "baslik": a["baslik"],
                "url": a["url"],
                "kaynak": kaynak["ad"],
                "ilk_gorulme": simdi,
                "durum": "yeni",
            })

    # Hicbir kaynak okunamadiysa kuyrugu EZME - sessiz veri kaybini onle
    if basarili_kaynak == 0:
        print("HATA: hicbir kaynak okunamadi, kuyruk degistirilmedi")
        return 1

    kuyruk_dosya["adaylar"] = mevcut_kuyruk + yeniler
    kuyruk_dosya["generated_at"] = simdi
    kuyruk_dosya["aciklama"] = (
        "Otomatik tarama ile bulunan, HENUZ DOGRULANMAMIS cagri adaylari. "
        "Butce/oran/uygunluk bilgileri icermez; calls.json'a eklenmeden once "
        "kurumun resmi sayfasindan teyit edilmelidir."
    )

    with open(DISCOVERED_PATH, "w", encoding="utf-8") as f:
        json.dump(kuyruk_dosya, f, ensure_ascii=False, indent=2)
        f.write("\n")

    bekleyen = [a for a in kuyruk_dosya["adaylar"] if a.get("durum") == "yeni"]
    print()
    print("[ozet] %d kaynak tarandi | %d YENI aday | kuyrukta %d inceleme bekliyor"
          % (basarili_kaynak, len(yeniler), len(bekleyen)))
    if yeniler:
        print("[yeni] Bu taramada ilk kez gorulenler:")
        for y in yeniler:
            print("  - %s" % y["baslik"][:88])
            print("      %s" % y["url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
