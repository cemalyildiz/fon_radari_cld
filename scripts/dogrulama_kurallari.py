"""
Fon Radari - kayit dogrulama kurallari.

Her kayit (data/calls.json icindeki bir cagri) yayinlanmadan once bu
kurallardan gecmek zorundadir. Kurallar hem gunluk otomasyonda
(scripts/update_data.py) hem de yeni kayit eklerken elle
(python scripts/dogrula.py) calistirilir. Prosedurun insan icin
aciklamasi: DOGRULAMA.md

Neden bu kadar kati?
Bu sitede daha once yasanan hatalarin hepsi ayni turdendi: resmi kaynaktan
teyit edilmemis bir bilgi "acik" gibi gosterildi (KOBIGEL, Teknoloji Hamlesi,
KOSGEB Yesil Sanayi, SoGreen, Eureka uluslararasi asamasi kapanmis cagrilar,
Istihdami Koruma'nin yanlis bitis tarihi). Kurallar bu hatalarin tekrarini
yapisal olarak engellemek icin yazildi.

Kayit uzerindeki "dogrulama" blogu:
  tarih            : YYYY-MM-DD, resmi kaynagin en son okundugu gun
  kaynak           : bilginin okundugu RESMI sayfa/belge adresi
  kanit            : kaynaktan tarih/limit/oran iceren kisa alinti
  durum            : "tam" | "kismi" | "onceki"
                     tam    = tarih, destek ve uygunluk resmi kaynaktan okundu
                     kismi  = bazi alanlar okunamadi (eksik alaninda yazilir)
                     onceki = yalnizca arsiv kayitlarinda; eski teyit korunuyor
  eksik            : (kismi ise zorunlu) neyin teyit edilemedigi
  surekli_kaniti   : (surekli_acik ise zorunlu) neden suresiz acik oldugu
  cerceve_kaniti   : (cerceve_program ise zorunlu) neden tek tarihli cagri olmadigi
  kaynak_turu      : "ikincil" ise resmi olmayan kaynak (yalnizca arsivde kabul)
"""
import re
from datetime import date, datetime, timedelta, timezone

TSI = timezone(timedelta(hours=3))

# Aktif kayitlar icin teyit en fazla bu kadar eski olabilir; asilirsa
# "yeniden teyit gerekli" uyarisi uretilir.
TEYIT_GECERLILIK_GUN = 30

# Resmi kaynak alan adlari. Yeni bir kurum eklenirken buraya eklenmeli.
RESMI_ALANLAR = [
    r"\.gov\.tr$", r"^tubitak\.gov\.tr$", r"\.europa\.eu$", r"^europa\.eu$",
    r"eurekanetwork\.org$", r"eurostars-eureka\.eu$",
    # Kalkinma ajanslari (gov.tr disindaki resmi alan adlari); yeni ajans eklendikce buraya yazin
    r"^marka\.org\.tr$", r"^istka\.org\.tr$", r"^bebka\.org\.tr$", r"^izka\.org\.tr$",
    r"^hamle\.gov\.tr$",
]

# Bu ifadeler bir alanin aslinda teyit edilmedigini gosterir.
BELIRSIZ_IFADELER = re.compile(r"teyit edil(meli|emedi)|kontrol edilmeli|dokümanından teyit|güncel kılavuza bakınız", re.I)

GECERLI_DURUMLAR = {"tam", "kismi", "onceki"}


def alan_adi(url):
    m = re.match(r"^https?://([^/:?#]+)", url or "", re.I)
    return (m.group(1).lower() if m else "").removeprefix("www.")


def resmi_mi(url):
    a = alan_adi(url)
    return bool(a) and any(re.search(d, a) for d in RESMI_ALANLAR)


def _tarih(s):
    return date.fromisoformat(s[:10])


def cagri_durumu(call, now=None):
    """js/app.js computeStatus ile ayni sonuc: acik | yakinda-kapaniyor | cerceve | kapali | kaldirildi"""
    now = now or datetime.now(timezone.utc)
    if call.get("yururlukten_kaldirildi"):
        return "kaldirildi"
    if call.get("cerceve_program"):
        return "cerceve"
    if call.get("surekli_acik") or not call.get("basvuru_bitis"):
        return "acik"
    bitis = call["basvuru_bitis"]
    end = datetime.fromisoformat(bitis)
    if len(bitis) == 10:
        end = end.replace(hour=23, minute=59, second=59)
    if end.tzinfo is None:
        end = end.replace(tzinfo=TSI)
    if now > end:
        return "kapali"
    kalan = (end.astimezone(TSI).date() - now.astimezone(TSI).date()).days
    return "yakinda-kapaniyor" if kalan <= 14 else "acik"


def kayit_denetle(call, now=None):
    """(hatalar, uyarilar) dondurur. Hata = yayina engel; uyari = insan dikkati gerekir."""
    now = now or datetime.now(timezone.utc)
    bugun = now.astimezone(TSI).date()
    h, u = [], []
    durum = cagri_durumu(call, now)
    aktif = durum in ("acik", "yakinda-kapaniyor", "cerceve")
    dg = call.get("dogrulama")

    # --- tarih tutarliligi ---
    bas, bit = call.get("basvuru_baslangic"), call.get("basvuru_bitis")
    for ad, deger in (("basvuru_baslangic", bas), ("basvuru_bitis", bit)):
        if deger:
            try:
                _tarih(deger)
            except ValueError:
                h.append("bozuk tarih %s=%s" % (ad, deger))
    try:
        if bas and bit and _tarih(bas) > _tarih(bit):
            h.append("basvuru_baslangic (%s) basvuru_bitis'ten (%s) sonra" % (bas, bit))
    except ValueError:
        pass
    if call.get("surekli_acik") and bit:
        h.append("surekli_acik=true iken basvuru_bitis dolu olamaz; resmi bir bitis tarihi varsa surekli_acik=false yapin")
    for at in call.get("ara_tarihler") or []:
        if not at.get("ad") or not at.get("tarih"):
            h.append("ara_tarihler ogesinde 'ad' ve 'tarih' zorunlu")
            continue
        try:
            _tarih(at["tarih"])
        except ValueError:
            h.append("ara_tarihler bozuk tarih: %s" % at["tarih"])

    # --- baslik / durum celiskisi ---
    if aktif and re.search(r"kapand[ıi]|kaldırıld[ıi]", call.get("baslik", ""), re.I) and "uluslararası başvuru kapandı" not in call.get("baslik", ""):
        h.append("baslik 'kapandi/kaldirildi' diyor ama hesaplanan durum '%s'" % durum)

    # --- dogrulama blogu ---
    if not dg:
        h.append("dogrulama blogu yok (tarih, kaynak, kanit zorunlu)")
        dg = {}
    else:
        for alan in ("tarih", "kaynak", "kanit"):
            if not dg.get(alan):
                h.append("dogrulama.%s bos" % alan)
    dd = dg.get("durum", "tam")
    if dd not in GECERLI_DURUMLAR:
        h.append("dogrulama.durum gecersiz: %s" % dd)
    teyit = None
    if dg.get("tarih"):
        try:
            teyit = _tarih(dg["tarih"])
            if teyit > bugun:
                h.append("dogrulama.tarih gelecekte: %s" % dg["tarih"])
        except ValueError:
            h.append("dogrulama.tarih bozuk: %s" % dg["tarih"])

    if aktif:
        if dd == "onceki":
            h.append("acik gorunen kayit 'onceki' teyitle yayinlanamaz; resmi kaynaktan yeniden teyit edin")
        if dg.get("kaynak_turu") == "ikincil" or not resmi_mi(dg.get("kaynak", "")):
            h.append("acik gorunen kaydin dogrulama.kaynak'i resmi alan adinda degil: %s" % alan_adi(dg.get("kaynak", "")))
        if not resmi_mi(call.get("kaynak_url", "")):
            h.append("acik gorunen kaydin kaynak_url'i resmi alan adinda degil: %s" % alan_adi(call.get("kaynak_url", "")))
        if teyit and (bugun - teyit).days > TEYIT_GECERLILIK_GUN:
            u.append("teyit %d gun once yapilmis (sinir %d): yeniden teyit gerekli" % ((bugun - teyit).days, TEYIT_GECERLILIK_GUN))

    if call.get("surekli_acik") and not dg.get("surekli_kaniti"):
        h.append("surekli_acik=true icin dogrulama.surekli_kaniti zorunlu (resmi kaynakta suresiz/donemsiz oldugunu gosteren ifade)")
    if call.get("cerceve_program") and not dg.get("cerceve_kaniti"):
        h.append("cerceve_program=true icin dogrulama.cerceve_kaniti zorunlu")

    belirsiz = [a for a in ("destek_miktari", "destek_orani", "kimler_basvurabilir") if BELIRSIZ_IFADELER.search(call.get(a) or "")]
    if belirsiz and dd == "tam":
        h.append("%s alani 'teyit edilmeli' benzeri ifade iceriyor ama dogrulama.durum='tam'; durum='kismi' ve dogrulama.eksik yazin" % ", ".join(belirsiz))
    if dd == "kismi":
        if not dg.get("eksik"):
            h.append("dogrulama.durum='kismi' icin dogrulama.eksik zorunlu")
        elif aktif:
            u.append("kismi teyit: %s" % dg["eksik"])

    return h, u


def hepsini_denetle(calls, now=None):
    """{id: {"hatalar": [...], "uyarilar": [...]}} + toplu hata listesi."""
    sonuc, tum_hatalar, idler = {}, [], set()
    for i, c in enumerate(calls):
        cid = c.get("id") or "#%d" % i
        h, u = [], []
        for alan in ("id", "kategori", "baslik", "kurum", "ozet", "kaynak_url"):
            if not c.get(alan):
                h.append("'%s' alani eksik" % alan)
        if c.get("kategori") not in ("ulusal", "uluslararasi"):
            h.append("gecersiz kategori: %s" % c.get("kategori"))
        if cid in idler:
            h.append("tekrar eden id")
        idler.add(cid)
        hh, uu = kayit_denetle(c, now)
        h += hh
        u += uu
        sonuc[cid] = {"hatalar": h, "uyarilar": u}
        tum_hatalar += ["%s: %s" % (cid, x) for x in h]
    return sonuc, tum_hatalar
