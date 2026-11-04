"""
Fon Radari - gunluk dogrulama raporu (GitHub issue govdesi) uretir.

Uc kaynagi birlestirir:
  data/kaynak_izleme.json   -> resmi sayfasi degisen / tarihi bulunamayan kayitlar
  data/dogrulama_raporu.json-> eski veya kismi teyitli kayitlar
  data/discovered.json      -> otomatik taramada bulunan, sitede karsiligi olmayan sayfalar

Cikti:
  argv[1] (varsayilan rapor.md)      : issue govdesi (markdown)
  argv[2] (varsayilan anahtarlar.txt): bu rapordaki maddelerin anahtarlari;
                                       is akisi bir onceki raporla karsilastirip
                                       yalnizca YENI maddeler icin yorum atar.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def oku(ad, varsayilan):
    p = ROOT / "data" / ad
    return json.load(open(p, encoding="utf-8")) if p.exists() else varsayilan


def main():
    cikti = Path(sys.argv[1] if len(sys.argv) > 1 else "rapor.md")
    anahtar_dosyasi = Path(sys.argv[2] if len(sys.argv) > 2 else "anahtarlar.txt")

    calls = {c["id"]: c for c in oku("calls.json", {"calls": []})["calls"]}
    izleme = oku("kaynak_izleme.json", {}).get("kayitlar", {})
    dogrulama = oku("dogrulama_raporu.json", {}).get("uyarilar", [])
    kesif = oku("discovered.json", {}).get("adaylar", [])
    bilinen_url = {(c.get("kaynak_url") or "").rstrip("/") for c in calls.values()}

    satirlar, anahtarlar = [], []

    yeniden = [(cid, s) for cid, s in izleme.items() if s.get("durum") == "yeniden_teyit"]
    satirlar.append("## 1. Resmî kaynağı değişen kayıtlar — yeniden teyit gerekli (%d)" % len(yeniden))
    satirlar.append("Kaynak sayfası, kaydın son teyidinden bu yana değişmiş veya kayıttaki son tarih sayfada artık geçmiyor. Süre uzatımı, iptal ya da yeni bir dönem olabilir.\n")
    for cid, s in yeniden:
        b = calls.get(cid, {}).get("baslik", cid)
        satirlar.append("- [ ] **%s** — [kaynak](%s)" % (b, s["url"]))
        for x in s.get("bulgular", []):
            satirlar.append("  - %s" % x)
        # Anahtar bulgunun kendisidir (sayfa ozeti degil): ayni bulgu her gun yeniden bildirilmez
        anahtarlar.append("izleme:%s:%s" % (cid, "|".join(b.split("“")[0] for b in s.get("bulgular", []))))
    if not yeniden:
        satirlar.append("_Yok._")

    erisilemeyen = [(cid, s) for cid, s in izleme.items() if s.get("durum") in ("erisilemedi", "izlenemedi")]
    if erisilemeyen:
        satirlar.append("\n<details><summary>Otomatik kontrol edilemeyen kaynaklar (%d) — elle bakılmalı</summary>\n" % len(erisilemeyen))
        for cid, s in erisilemeyen:
            satirlar.append("- %s — %s — [kaynak](%s)" % (calls.get(cid, {}).get("baslik", cid), "; ".join(s.get("bulgular", [])), s["url"]))
        satirlar.append("\n</details>")

    satirlar.append("\n## 2. Teyidi eski veya kısmi olan açık kayıtlar (%d)" % len(dogrulama))
    for d in dogrulama:
        satirlar.append("- [ ] **%s**" % d["baslik"])
        for x in d["uyarilar"]:
            satirlar.append("  - %s" % x)
        anahtarlar.append("dogrulama:%s:%s" % (d["id"], "|".join(d["uyarilar"])))
    if not dogrulama:
        satirlar.append("_Yok._")

    bekleyen = [a for a in kesif if a.get("durum") == "yeni" and a.get("url", "").rstrip("/") not in bilinen_url]
    bekleyen.sort(key=lambda a: a.get("ilk_gorulme", ""), reverse=True)
    satirlar.append("\n## 3. Otomatik taramada bulunan, sitede karşılığı olmayan sayfalar (%d)" % len(bekleyen))
    satirlar.append("Bunlar **doğrulanmamıştır**. Siteye eklemek için DOGRULAMA.md adımları izlenmelidir.\n")
    for a in bekleyen[:60]:
        satirlar.append("- [ ] [%s](%s) <sub>%s · ilk görülme %s</sub>" % (a["baslik"], a["url"], a.get("kaynak", ""), a.get("ilk_gorulme", "")[:10]))
        anahtarlar.append("kesif:%s" % a["url"])
    if len(bekleyen) > 60:
        satirlar.append("- … ve %d sayfa daha (data/discovered.json)" % (len(bekleyen) - 60))

    satirlar.append("\n---\n<sub>Bu rapor her gün otomatik güncellenir. Yeni bir madde çıktığında bu konuya yorum eklenir. "
                    "Kayıt düzeltme prosedürü: [DOGRULAMA.md](https://github.com/cemalyildiz/fon_radari_cld/blob/main/DOGRULAMA.md)</sub>")
    cikti.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    anahtar_dosyasi.write_text("\n".join(anahtarlar) + "\n", encoding="utf-8")
    print("rapor: %d yeniden teyit, %d dogrulama uyarisi, %d kesif adayi" % (len(yeniden), len(dogrulama), len(bekleyen)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
