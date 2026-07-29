# TEFAS Otomatik Veri Çekme — Kurulum Rehberi

Hiç Python bilmiyorsan bile adım adım takip edebilirsin. Toplam ~15 dakika.

---

## Bölüm 1 — Neyi nasıl çekiyoruz?

TEFAS 2026'da sitesini yeniledi. Yeni site (Next.js tabanlı) arka planda
iki adet **açık JSON API** kullanıyor:

| Endpoint | Ne verir |
|---|---|
| `www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir` | Fiyat, pay sayısı, yatırımcı sayısı, fon büyüklüğü |
| `www.tefas.gov.tr/api/funds/dagilimSiraliGetirT` | Portföy dağılımı (50+ varlık kalemi, %) |

Bu API'ler **üyelik, API anahtarı, login istemiyor.** Yani HTML kazımaya
(scraping) hiç gerek yok — doğrudan yapısal veri geliyor. `pytefas`
kütüphanesi bu iki endpoint'i sarmalıyor, biz de onu kullanıyoruz.

**Bilmen gereken 3 kısıt:**

1. **Dakikada 6 istek** sınırı var. `pytefas` bunu otomatik yönetiyor.
2. Tek istekte **en fazla ~1 ay** aralık çekilebilir. Uzun aralıklar
   otomatik parçalanıyor (1 yıl ≈ 3 dakika, 5 yıl ≈ 15 dakika).
3. Sabah 10:00'da yayınlanan fiyat genelde **bir önceki iş gününe** ait.
   Bu yüzden script tarihi sabit yazmıyor — veri bulunana kadar geriye
   bakıyor. Hafta sonu ve resmî tatiller böylece kendiliğinden atlanıyor.

---

## Bölüm 2 — Kurulum (Windows 11)

### 2.1 Python kur

python.org/downloads → indir → kurulumda **"Add python.exe to PATH"
kutusunu mutlaka işaretle.**

Kontrol: Başlat → `cmd` → şunu yaz:
```
python --version
```
Bir sürüm numarası görüyorsan tamam.

### 2.2 Gerekli paketleri kur

```
pip install pytefas pandas pyarrow
```

### 2.3 Dosyaları yerleştir

`C:\TEFAS\` diye bir klasör aç, şu 3 dosyayı içine at:
- `tefas_gunluk.py`
- `tefas_getiri.py`
- `tefas_calistir.bat`

### 2.4 İlk testi yap

`cmd` içinde:
```
cd C:\TEFAS
python tefas_gunluk.py
```

Veriler `C:\Users\<kullanıcı_adın>\TEFAS_VERI\` altına düşecek.
Ekranda "TAMAMLANDI" görmen lazım.

---

## Bölüm 3 — Her gün 10:10'da otomatik çalıştır

### Görev Zamanlayıcı (Task Scheduler) ile

1. Başlat → **"Görev Zamanlayıcı"** yaz, aç.
2. Sağ panel → **Görev Oluştur** (Create Task — "Basit Görev" değil, tam olan).
3. **Genel** sekmesi:
   - Ad: `TEFAS Günlük Veri`
   - ⚙️ **"Kullanıcı oturum açmış olsun ya da olmasın çalıştır"** seç
   - ✅ **"En yüksek ayrıcalıklarla çalıştır"**
4. **Tetikleyiciler** → Yeni:
   - Görev başlatma: **Zamanlamaya göre** → **Haftalık**
   - Başlangıç saati: **10:10**
   - Gün: Pzt, Sal, Çar, Per, Cum (hafta sonu işaretsiz)
   - ✅ Etkin
5. **Eylemler** → Yeni:
   - Eylem: Programı başlat
   - Program: `C:\TEFAS\tefas_calistir.bat`
   - Başlangıç yeri: `C:\TEFAS`  ← **bu alanı boş bırakma**
6. **Koşullar** sekmesi:
   - ❌ "Yalnızca AC gücündeyse başlat" işaretini **kaldır** (laptop kullanıyorsun)
   - ✅ "Görevi çalıştırmak için bilgisayarı uyandır"
7. **Ayarlar**:
   - ✅ "Zamanlanmış başlangıç kaçırılırsa görevi en kısa sürede başlat"
     — bu önemli: laptop 10:10'da kapalıysa, açtığında çalışır.
   - ✅ "Başarısız olursa yeniden başlat": 10 dakikada bir, 3 kez

**Test:** Görev listesinde sağ tık → **Çalıştır**. `TEFAS_VERI\log.txt`
dosyasına bak.

---

## Bölüm 4 — Bulut alternatifi (bilgisayar açık olmasa da çalışır)

Laptop kapalıysa görev çalışmaz. Kalıcı çözüm: **GitHub Actions** —
ücretsiz, sunucusuz, her gün kendi kendine çalışır.

GitHub'da özel (private) bir repo aç, scriptleri koy, sonra
`.github/workflows/tefas.yml` dosyasını ekle:

```yaml
name: TEFAS Gunluk Veri

on:
  schedule:
    # UTC saati! TSİ 10:10 = UTC 07:10
    - cron: '10 7 * * 1-5'
  workflow_dispatch:        # elle de tetiklenebilsin

jobs:
  cek:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - run: pip install pytefas pandas pyarrow

      - run: python tefas_gunluk.py
        env:
          HOME: ${{ github.workspace }}

      - name: Veriyi repoya kaydet
        run: |
          git config user.name  "tefas-bot"
          git config user.email "bot@users.noreply.github.com"
          git add -A TEFAS_VERI
          git diff --staged --quiet || git commit -m "TEFAS verisi $(date +%F)"
          git push
```

> **Not:** GitHub Actions'ın cron'u yoğun saatlerde 5–20 dakika gecikebilir.
> Kritikse `'0 7 * * 1-5'` yaz (TSİ 10:00), script zaten veri gelene kadar
> tekrar deniyor.

---

## Bölüm 5 — Günlük kullanım

**Veriyi çekmek** (otomatik zaten çalışıyor, elle de yapabilirsin):
```
python tefas_gunluk.py
```

**Geriye dönük doldurma** — geçmiş 1 yılı bir kerede indir:
```
python tefas_gunluk.py 2025-07-28 2026-07-28
```
(~3 dakika sürer, rate-limit yüzünden)

**Getirileri hesaplamak:**
```
python tefas_getiri.py            → tüm fonlar
python tefas_getiri.py AAK TTE    → sadece bu fonlar
```

### Çıkan dosyalar

| Dosya | İçerik |
|---|---|
| `gunluk/tefas_info_YYYY-MM-DD.csv` | O günün fiyatları (Excel'de çift tıkla açılır, TR formatı) |
| `gunluk/tefas_dagilim_YYYY-MM-DD.csv` | O günün portföy dağılımları |
| `master_info.parquet` | **Asıl veri tabanın** — tüm geçmiş fiyatlar, mükerrersiz |
| `master_dagilim.parquet` | Tüm geçmiş portföy dağılımları |
| `getiriler_YYYY-MM-DD.csv` | Hesaplanmış dönemsel getiriler |
| `log.txt` | Ne zaman çalıştı, hata var mı |

**Parquet nedir?** CSV'nin sıkıştırılmış, hızlı versiyonu. 5 yıllık tüm
fon verisi CSV'de ~2 GB tutarken Parquet'te ~50 MB. Python'da tek satırla
okunur: `pd.read_parquet("master_info.parquet")`. Excel doğrudan açamaz —
o yüzden günlük CSV'ler de ayrıca yazılıyor.

---

## Bölüm 6 — Sorun giderme

| Belirti | Sebep / Çözüm |
|---|---|
| `ModuleNotFoundError: pytefas` | `pip install pytefas` yapılmamış; ya da Task Scheduler farklı Python kullanıyor → `.bat` içindeki `set PY=` satırına tam yol yaz |
| `TefasRateLimitError` | Çok sık istek. Script zaten bekliyor; `max_retry` değerini artır |
| Boş DataFrame dönüyor | Tatil günü veya veri henüz yayınlanmamış. Script 5 dakika arayla 4 kez deniyor |
| Görev çalışıyor ama dosya yok | `.bat` içinde "Başlangıç yeri" boş kalmıştır → `C:\TEFAS` yaz |
| Bir gün her şey bozulursa | TEFAS yine site değiştirmiştir. `pip install -U pytefas` ile güncelle; hâlâ olmuyorsa GitHub'da issue aç |

---

## Bölüm 7 — Kütüphane seçimi hakkında not

| Kütüphane | Durum |
|---|---|
| **pytefas** ✅ | Yeni API'yi kullanıyor, portföy dağılımı (50+ kolon) dahil. Haftalık otomatik test ("canary") ile API'nin çalıştığı doğrulanıyor. **Önerilen.** |
| tefas-crawler | Ekosistemin en eski/bilinen paketi, 2026'da yeni API'ye taşındı. Ancak yeni backend fiyatı **fon başına** verdiği için tüm fonları çekmek yavaş, ayrıca **portföy dağılımı ve yatırımcı sayısı artık dönmüyor.** Tek fon takibi için hâlâ iyi. |
| Kendi `requests` kodun | Mümkün — endpoint'ler yukarıda. Ama rate-limit, chunking, tarih formatı, kolon eşleme işlerini kendin yazmak zorunda kalırsın. Öğrenmek istersen `pytefas` kaynak kodunu okumak iyi bir başlangıç. |

---

## Sonraki adım fikirleri

- Fonları BIST/USD/altın ile korelasyona sokmak (ATLAS tarafına bağlanır)
- Portföy dağılımı değişimlerinden fon yöneticisinin pozisyon değiştirdiğini
  yakalamak — bu API'nin en değerli ve en az kullanılan tarafı
- Belirli fonlara EMA/SMA sistemini uygulamak
- Getiri tablosunu haftalık HTML rapora çevirmek
