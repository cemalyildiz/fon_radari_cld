# Fon Radarı — Kayıt Doğrulama Prosedürü

Sitedeki her çağrı kaydı yayına girmeden önce bu prosedürle teyit edilir. Kurallar
`scripts/dogrulama_kurallari.py` içinde koda dökülmüştür: kurala uymayan bir kayıt
eklendiğinde günlük otomasyon **kırmızıya düşer** ve doğrulama raporunda görünür.

Bu prosedür, sitede daha önce yaşanan hatalardan çıkarılmıştır:

| Hata | Kök neden | Önleyen kural |
|---|---|---|
| KOBİGEL "açık" görünüyordu | Bitiş tarihi olmayan kayıt "çerçeve program" sayıldı | Çerçeve için kanıt zorunlu; çerçeve programlar "Açık" listesinde gösterilmez |
| KOSGEB Yeşil Sanayi "sürekli açık" görünüyordu | Program sayfasındaki "Yürürlükte olan çağrılar" başlığına güvenildi; çağrı metnindeki 30.11.2024 bitişi okunmadı | `surekli_acik` için resmî kanıt zorunlu; her zaman **çağrı metni** okunur |
| Eureka çağrıları "açık" görünüyordu | Ulusal aşama tarihi yazıldı; uluslararası aşamanın kapandığı gözden kaçtı | İki aşamalı çağrı kuralı (aşağıda) |
| İstihdamı Koruma "kapalı" görünüyordu | Sonradan değişen tarih takip edilmedi | Kaynak sayfa izleme + 30 günlük teyit geçerliliği |
| 1707'de "yüksek oranlı destek" yazıyordu | Rakam yerine yorum yazıldı | Destek alanlarında rakam veya "kısmi teyit" işareti zorunlu |
| 1831'de 310.000 TL yazıyordu, resmî sayfa 280.000 TL | Kaynak ile kayıt karşılaştırılmadı | Kanıt alanına resmî metinden alıntı yazılır |

## 1. Kaynak kuralı

- **Yalnızca resmî kaynak** kullanılır: kurumun kendi sitesi (`*.gov.tr`, `tubitak.gov.tr`,
  `kosgeb.gov.tr`, `ticaret.gov.tr`, `ssb.gov.tr`), AB (`*.europa.eu`), Eureka
  (`eurekanetwork.org`) veya kalkınma ajansının sitesi (`marka.org.tr` vb.).
- Danışmanlık blogları, haber siteleri ve LinkedIn **teyit kaynağı değildir**. Resmî
  metin açılamıyorsa en fazla tarih için yardımcı olarak kullanılabilir ve kayıt
  `durum: "kismi"` olarak işaretlenir.
- Program tanıtım sayfası ile çağrı metni çelişirse **çağrı metni / genelge / yönerge** esas alınır.

## 2. Okunması gereken alanlar

Resmî kaynaktan şunlar okunur ve kayda yazılır:

1. **Başvuru başlangıç ve son başvuru tarihi** (`basvuru_baslangic`, `basvuru_bitis`, `YYYY-MM-DD`).
   Saatsiz tarih Türkiye saatiyle o günün sonu (23:59) kabul edilir.
2. **Ara tarihler** (`ara_tarihler`): kurum bazlı ön kayıt, ulusal aşama, tam proje gibi.
3. **Destek miktarı ve oranı**: rakamla. Okunamadıysa uydurulmaz; "teyit edilemedi" yazılır
   ve `durum: "kismi"` yapılır.
4. **Destek türü** (hibe / geri ödemeli / faiz desteği / ayni destek).
5. **Kimler başvurabilir**: ölçek, sektör, asgari ihracat, işbirliği kuruluşu şartı vb.
   Firmaların doğrudan başvuramadığı programlarda bu **açıkça** yazılır.

## 3. Özel durumlar

**İki aşamalı çağrılar (Eureka, Eurostars, bazı AB çağrıları):**
`basvuru_bitis` = **yeni bir başvuru sahibinin başvurabileceği son tarih**, yani ilk
aşamanın (uluslararası başvuru / proje taslağı) kapanışıdır. Sonraki aşamalar
`ara_tarihler`'e yazılır. İlk aşama kapandıysa çağrı sitede kapalı görünür; başlığa
"(uluslararası başvuru kapandı)" eklenir.

**Sürekli açık programlar (`surekli_acik: true`):** Yalnızca resmî metinde başvuru
dönemi veya son tarih **tanımlanmamışsa** kullanılır ve
`dogrulama.surekli_kaniti` alanına bunu gösteren ifade yazılır. Resmî bir bitiş tarihi
varsa (ör. 1831'de 01.01.2030) `surekli_acik: false` ve tarih yazılır.

**Çerçeve programlar (`cerceve_program: true`):** Tek bir başvuru tarihi olmayan,
alt çağrılarla ya da dönemsel açılan programlar (Horizon kümeleri, kalkınma
ajanslarının genel kaydı). `dogrulama.cerceve_kaniti` zorunludur. Bunlar "Açık"
listesinde değil, "Çerçeve programlar" filtresinde gösterilir. Bir çerçevenin belirli
bir dönemi açıksa o dönem **ayrı bir kayıt** olarak eklenir.

**Kapanan dönem:** Dönemsel bir programın dönemi kapandıysa kayıt silinmez; başlığa
dönem ve "kapandı" yazılır, kayıt arşive geçer. Yeni dönem açıldığında yeni kayıt eklenir.

## 4. `dogrulama` bloğu

Her kayıtta bulunur:

```json
"dogrulama": {
  "tarih": "2026-11-04",
  "durum": "tam",
  "kaynak": "https://tubitak.gov.tr/...",
  "kanit": "Çağrı Açılış Tarihi 20 Temmuz 2026; Çağrı Kapanış Tarihi 11 Kasım 2026",
  "eksik": "(yalnızca durum=kismi ise) neyin okunamadığı",
  "surekli_kaniti": "(yalnızca surekli_acik ise)",
  "cerceve_kaniti": "(yalnızca cerceve_program ise)"
}
```

- `durum`: `tam` (tarih, destek, uygunluk resmî kaynaktan okundu) · `kismi` (bir kısmı
  okunamadı, `eksik` zorunlu) · `onceki` (yalnızca arşiv kayıtları; açık bir kayıtta kullanılamaz).
- `kanit`: resmî metinden kısa alıntı — tarihler ve rakamlar dahil. Kayıttaki rakam ile
  alıntıdaki rakam aynı olmalıdır.

## 5. Otomatik denetim (her gün 08:10)

1. **Kural denetimi** (`update_data.py`): yukarıdaki kurallara uymayan kayıt varsa iş akışı başarısız olur.
2. **Yeni çağrı taraması** (`discover_calls.py`): sitede karşılığı olmayan sayfalar "doğrulanmamış" olarak listelenir; siteye **kendiliğinden eklenmez**.
3. **Kaynak sayfa izleme** (`check_sources.py`): açık görünen her kaydın resmî sayfası açılır. Sayfa son teyitten beri değiştiyse, kayıttaki son tarih sayfada artık geçmiyorsa ya da "uzatıldı / kapandı / iptal" gibi bir ifade belirdiyse kayıt **"yeniden teyit gerekli"** olarak işaretlenir. Kayıt otomatik değiştirilmez.
4. **Teyit geçerliliği:** açık bir kaydın teyidi 30 günden eskiyse uyarı üretilir.
5. **Rapor:** bulgular GitHub'daki tek "Fon Radarı — doğrulama raporu" konusunda toplanır; yeni bir madde çıktığında o konuya yorum eklenir.

Sitede her kartta son teyit tarihi görünür. Kısmi veya eski teyitli kayıtlar ve kaynağı
değişmiş kayıtlar sarı renkle işaretlenir.

## 6. Yeni kayıt ekleme / yeniden teyit adımları

1. Resmî çağrı sayfasını **ve** çağrı metnini (PDF/genelge/yönerge) aç.
2. Bölüm 2'deki alanları oku; özel durumları (Bölüm 3) kontrol et.
3. Kaydı yaz veya güncelle; `dogrulama.tarih`'i bugünün tarihi yap, `kanit`'e alıntıyı yaz.
4. Denetimi çalıştır: `python scripts/update_data.py` → hata vermemeli.
5. Commit et. Ertesi gün kaynak izleme, bugünkü sayfayı yeni referans olarak alır.
