# TEFAS Panosu — Bulut Kurulumu (iPad / Telefon Erişimi)

Bu rehber, laptop kapalıyken de her gün 10:10'da verinin otomatik
çekilip GitHub'a şifreli olarak gönderilmesini, ve dashboard'u
telefon/iPad'den şifreyle açabilmeni sağlar.

**Repo:** `https://github.com/HectorOfWilusa/prowiljectasu` (zaten kuruldu)

---

## 1. Yeni dosyaları repo'ya ekle

`C:\TEFAS` klasörüne şu dosyaları koy (üzerine yazsın):
- `tefas_sifrele.py`
- `tefas_git_gonder.py`
- `tefas_ana.py` (güncellendi — artık 5 adımı sırayla çalıştırıyor)
- `tefas_panosu.html` (güncellendi — üstte "Buluttan otomatik yükle" kutusu var)
- `.github/workflows/tefas-gunluk.yml` — **bu bir klasör yapısı**, `.github` adında bir klasör açıp içine `workflows` klasörü, onun içine de bu dosyayı koy: `C:\TEFAS\.github\workflows\tefas-gunluk.yml`

cmd'de:
```
cd C:\TEFAS
git add .
git commit -m "bulut ve sifreleme sistemi eklendi"
git push
```

---

## 2. GitHub'da "Secret" (gizli şifre) tanımla

Script'in kullandığı şifre, kod içine hiç yazılmıyor — GitHub'ın kendi
güvenli "Secrets" bölümünde saklanacak.

1. Repo sayfana git: `https://github.com/HectorOfWilusa/prowiljectasu`
2. Üstteki **Settings** (Ayarlar) sekmesine tıkla.
3. Sol menüden **Secrets and variables** → **Actions** seç.
4. **New repository secret** butonuna bas.
5. **Name** (İsim) kutusuna tam olarak şunu yaz: `TEFAS_PANO_SIFRE`
6. **Secret** kutusuna, dashboard'u açarken kullanacağın şifreyi yaz
   (güçlü bir şifre seç, gerçek portföy verine kilit olacak).
7. **Add secret** ile kaydet.

**Bu şifreyi unutma** — hem burada hem dashboard'da hem de kendi
bilgisayarında (yerel çalıştırmalar için) aynı şifreyi kullanacaksın.

---

## 3. Yerel bilgisayarında da aynı şifreyi tanımla

Kendi laptop'unda `tefas_ana.py` çalıştırdığında da veriyi şifreleyip
GitHub'a göndermesini istiyorsan, her çalıştırmadan önce (veya Görev
Zamanlayıcı'nın `.bat` dosyasına ekleyerek) şu ortam değişkenini tanımla:

```
set TEFAS_PANO_SIFRE=senin-sifren
```

**`tefas_calistir.bat` dosyasını güncelle** — `python tefas_ana.py`
satırının HEMEN ÜSTÜNE şunu ekle:
```
set TEFAS_PANO_SIFRE=senin-sifren
```

Bu değişken tanımlı değilse, `tefas_ana.py` şifreleme adımını
otomatik atlar (hata vermez) — yani bunu yapmazsan sadece bulut
tarafı çalışmaz, yerel sistem eskisi gibi çalışmaya devam eder.

---

## 4. Dashboard'daki GitHub adresini kontrol et

`tefas_panosu.html` içinde şu satırı ara (JavaScript kısmında, en altlara yakın):
```js
const GITHUB_RAW_TEMEL = "https://raw.githubusercontent.com/HectorOfWilusa/prowiljectasu/main/sifreli";
```
Bu zaten senin repo adresine göre ayarlandı, değiştirmene gerek yok
— repo adını/kullanıcı adını değiştirirsen burayı da güncellemen gerekir.

---

## 5. İlk testi yap

1. cmd'de:
   ```
   cd C:\TEFAS
   set TEFAS_PANO_SIFRE=senin-sifren
   python tefas_ana.py
   ```
2. Log'da şunu görmen lazım:
   ```
   Sifrelendi: ...
   GitHub'a gonderildi (push basarili).
   TUM ADIMLAR BASARILI.
   ```
3. GitHub repo sayfana git, `sifreli/` klasörünün içinde `fonlar.enc.json`,
   `portfoy.enc.json`, `kategori.enc.json`, `meta.json` dosyalarını
   görmen lazım.

---

## 6. Dashboard'u telefon/iPad'den açma

`tefas_panosu.html` dosyası şu an sadece bilgisayarında duruyor —
telefondan açabilmek için bunu da bir web adresine koymamız lazım
(**GitHub Pages**, ücretsiz). Bu adımı bir sonraki oturumda birlikte
yapacağız çünkü küçük bir ayar gerektiriyor.

Şimdilik test için: `tefas_panosu.html` dosyasını kendine (örneğin
Google Drive, WhatsApp'tan kendine, veya email ile) gönderip
telefonda/iPad'de açabilirsin — üstteki "Buluttan otomatik yükle"
kutusuna şifreni yazıp "Yükle" dediğinde, GitHub'daki güncel veriyi
çekip göstermesi lazım.

---

## 7. Otomatik zamanlama ne zaman devreye girer

`.github/workflows/tefas-gunluk.yml` dosyası GitHub'a gönderildiği
andan itibaren, **hafta içi her gün TSİ 10:10'da** (GitHub'ın yoğunluğuna
göre birkaç dakika gecikmeli) otomatik çalışmaya başlar — senin
bilgisayarının açık olması gerekmez.

**Elle tetiklemek istersen:** Repo sayfasında **Actions** sekmesine
git, sol menüden **"TEFAS Gunluk Veri Cekme"** seç, sağdaki
**"Run workflow"** butonuna bas.

---

## Sorun giderme

| Belirti | Sebep / Çözüm |
|---|---|
| Dashboard'da "şifre yanlış olabilir" | Secret'taki şifre ile dashboard'a girdiğin şifre birebir aynı olmalı (büyük/küçük harf dahil) |
| `sifreli/` klasörü GitHub'da hiç oluşmamış | Actions sekmesinde workflow'un çalışıp çalışmadığına bak, kırmızı X varsa üzerine tıklayıp hata logunu oku |
| Workflow "TEFAS'a erişilemedi" hatası veriyor | GitHub'ın sunucuları TEFAS'ı bazen kısıtlıyor olabilir — nadir ama mümkün, o günlük veri atlanır, ertesi gün tekrar dener |
| Yerelde çalışıyor ama GitHub Actions'ta çalışmıyor | Secret adının tam olarak `TEFAS_PANO_SIFRE` olduğunu kontrol et (büyük harf, alt çizgi) |
