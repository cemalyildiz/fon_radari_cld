"""
Fon Radarı - otomatik veri kontrol betiği.

Bu betik GitHub Actions tarafından saatlik olarak çalıştırılır ve:
  1. data/calls.json dosyasının biçimini doğrular,
  2. "last_checked" zaman damgasını günceller (kart durumları zaten
     tarayıcıda anlık tarihe göre client-side hesaplandığı için
     "Açık / Yakında Kapanıyor / Kapalı" etiketleri her zaman güncel kalır),
  3. basvuru_bitis tarihi geçmiş ve surekli_acik=false olan çağrıları
     konsol çıktısında raporlar (ileride otomatik arşivleme/taşıma
     eklenebilir).

NOT (şeffaflık için): Bu betik şu an TÜBİTAK / KOSGEB / Horizon Europe /
LIFE sitelerini otomatik olarak TARAMIYOR (scraping yapmıyor) - her kurumun
sitesi farklı yapıda olduğundan güvenilir bir tarayıcı ayrı ayrı yazılmalı
ve bakımı sürdürülmelidir. Yeni çağrıların data/calls.json içine eklenmesi
şimdilik elle / AI destekli olarak yapılmaktadır. Bu dosya, kaynak bazlı
tarayıcılar eklendikçe genişletilmek üzere tasarlanmıştır.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "calls.json"


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        payload = json.load(f)

    calls = payload.get("calls", [])
    now = datetime.now(timezone.utc)

    expired = []
    for call in calls:
        if call.get("surekli_acik"):
            continue
        bitis = call.get("basvuru_bitis")
        if not bitis:
            continue
        end_date = datetime.fromisoformat(bitis).replace(tzinfo=timezone.utc)
        if end_date < now:
            expired.append(call["id"])

    if expired:
        print(f"[bilgi] Süresi geçmiş {len(expired)} çağrı tespit edildi: {', '.join(expired)}")
        print("[bilgi] Bunlar arayüzde otomatik olarak 'Kapalı / Arşiv' etiketiyle gösterilecek.")

    payload["last_checked"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[bilgi] last_checked güncellendi: {payload['last_checked']}")


if __name__ == "__main__":
    sys.exit(main())
