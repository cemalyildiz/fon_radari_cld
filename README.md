# Fon Radarı

Ulusal ve uluslararası yeşil dönüşüm proje çağrılarını (TÜBİTAK, KOSGEB, Horizon Europe, LIFE Programme vb.) tek bir arayüzde listeleyen statik web sitesi.

## Nasıl çalışır

- Tüm çağrı verisi `data/calls.json` içinde tutulur.
- Site, GitHub Pages üzerinden statik olarak yayınlanır (sunucu gerektirmez).
- "Açık / Yakında Kapanıyor / Kapalı" durumları **tarayıcıda anlık tarihe göre hesaplanır** — yani ziyaretçi siteye ne zaman girerse girsin, durum etiketleri güncel tarihe göre doğru gösterilir.
- `.github/workflows/update-data.yml` her saat başı çalışarak `scripts/update_data.py` betiğini tetikler; bu betik `last_checked` zaman damgasını günceller ve süresi geçmiş çağrıları konsolda raporlar.

## Önemli sınırlama (şeffaflık için)

Bu sistem şu an **her kurumun web sitesini otomatik taramıyor (scraping yapmıyor)**. TÜBİTAK, KOSGEB, Horizon Europe ve LIFE Programme'ın her biri farklı yapıda sitelere sahip olduğundan, güvenilir bir otomatik tarayıcı her kaynak için ayrı yazılmalı ve düzenli bakım gerektirir. Şu an için:

- Yeni çağrıların `data/calls.json`'a eklenmesi elle / AI destekli yapılmaktadır.
- Saatlik otomasyon, mevcut verinin **durumunu** (açık/kapalı) güncel tutar, ama **yeni çağrı keşfi** otomatik değildir.
- `scripts/update_data.py` dosyası, ileride kaynak bazlı tarayıcılar eklenerek genişletilebilecek şekilde tasarlanmıştır.

Başvuru kararı vermeden önce her zaman ilgili kurumun resmi ve güncel kılavuzunu kontrol edin (her kart üzerinde "Resmi kaynağa git" bağlantısı bulunur).

## Yerel geliştirme

Herhangi bir statik dosya sunucusu ile çalıştırılabilir, örn.:

```bash
python3 -m http.server 8000
```

Sonra `http://localhost:8000` adresini açın.

## Yayın (GitHub Pages)

Repo ayarlarından **Settings → Pages → Source: Deploy from a branch → main / (root)** seçilerek yayınlanır.
