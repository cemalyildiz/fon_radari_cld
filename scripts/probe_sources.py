"""Gecici kesif probu: kaynak sayfalarin HTML yapisini ogrenmek icin."""
import re, sys, urllib.request, gzip, io

HEDEFLER = {
 "tubitak_sanayi": "https://tubitak.gov.tr/tr/destekler/sanayi/ulusal-destek-programlari",
 "tubitak_duyuru": "https://tubitak.gov.tr/tr/duyurular",
 "tubitak_uluslararasi": "https://tubitak.gov.tr/tr/destekler/sanayi/uluslararasi-destek-programlari",
 "kosgeb_destekler": "https://www.kosgeb.gov.tr/site/tr/genel/destekler/3/destekler",
 "kosgeb_duyuru": "https://www.kosgeb.gov.tr/site/tr/genel/duyurular/1/duyurular",
}

UA = "Mozilla/5.0 (compatible; FonRadariBot/1.0; +https://github.com/cemalyildiz/fon_radari_cld)"

def getir(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        return r.status, raw.decode("utf-8", "replace")

for ad, url in HEDEFLER.items():
    print("=" * 70)
    print("KAYNAK:", ad, "|", url)
    try:
        st, html = getir(url)
    except Exception as e:
        print("  HATA:", type(e).__name__, e)
        continue
    print("  durum:", st, "| boyut:", len(html))
    # Cagri/duyuru gibi gorunen linkleri cikar
    linkler = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I)
    ilginc = []
    for href, metin in linkler:
        t = re.sub(r"<[^>]+>", " ", metin)
        t = re.sub(r"\s+", " ", t).strip()
        if not t or len(t) < 12:
            continue
        if re.search(r"çağrı|cagri|duyuru|destek program|başvuru|basvuru", t, re.I):
            ilginc.append((href, t[:95]))
    print("  cagri/duyuru benzeri link sayisi:", len(ilginc))
    for href, t in ilginc[:18]:
        print(f"    - {t}\n        -> {href[:110]}")
