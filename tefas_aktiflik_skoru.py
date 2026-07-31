"""
TEFAS Aktif Yonetim Skoru Hesaplama
=====================================
Bir fonun varlik dagilimini (hisse/tahvil/doviz/altin vb. 50+ kalem)
GUN GUN ne kadar degistirdigini olcerek, o fonun ne kadar "aktif
yonetildigini" tahmin eder. Fikir basit: eger yonetici surekli pozisyon
degistiriyorsa (piyasa gorusune gore alim/satim yapiyorsa), dagilim
vektoru gunden gune belirgin sekilde degisir. Eger dagilim neredeyse
sabit kaliyorsa, fon byuk olasilikla pasif/durgun yonetiliyordur.

YONTEM (L1 mesafe / Toplam Mutlak Fark):
  Her gun icin, bir onceki gune gore TUM varlik kalemlerindeki mutlak
  degisimlerin toplami hesaplanir:

      gunluk_degisim(t) = sum(|agirlik_i(t) - agirlik_i(t-1)|)  (i = 54 varlik kalemi)

  Ornek: Hisse agirligi %40 -> %35 (fark -5), Tahvil %30 -> %35 (fark +5)
  ise bu tek hareket |−5| + |+5| = 10 puan katki yapar.

  Bu gunluk degisim degerleri, farkli zaman pencereleri (1 Hafta, 1 Ay,
  2 Ay, 3 Ay) icinde ORTALAMASI alinarak tek bir "aktiflik skoru" elde
  edilir. Yuksek skor = daha sik/buyuk pozisyon degisikligi = daha aktif
  yonetim izlenimi.

KAPSAM: Sadece YAT (yatirim) fonlari - EMK ve BYF haric, kayan pencere
fiyat sistemimizle (tefas_kayan_pencere.py) tutarli olsun diye.

PERCENTILE: Ham skorun yaninda, her fon icin kendi semsiye_turu ve
kendi kategori grubu icindeki percentile (0-100) de hesaplanir - boylece
"bu fon, kendi turundeki fonlarin %80'inden daha aktif" gibi bir
karsilastirma yapilabilir. Ikisi AYRI AYRI sutunlar olarak tutulur.

Veri kaynagi: master_dagilim.parquet (tefas_gunluk.py'nin biriktirdigi
tum gecmis portfoy dagilimi). Bu script oradan SADECE YAT tipini ve
SADECE son ~95 gunluk kismini alip ayri, KUCUK ve SABIT BOYUTLU bir
kayan pencere dosyasina yazar - master_dagilim.parquet gibi surekli
BUYUMEZ.

Ciktilar (VERI_KLASORU altina):
  dagilim_kayan_pencere.parquet  -> son ~95 gunun YAT dagilim gecmisi
  aktiflik_skoru.parquet          -> her YAT fonu icin 4 pencere skoru +
                                      percentile'lar (semsiye_turu ve
                                      kategori bazinda ayri ayri)

Kullanim:
  python tefas_aktiflik_skoru.py
"""

import sys
import logging
from pathlib import Path
from datetime import timedelta

import pandas as pd

VERI_KLASORU = Path.home() / "TEFAS_VERI"
VERI_KLASORU.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(VERI_KLASORU / "log.txt", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tefas-aktiflik-skoru")

# En uzun pencere 3 Ay (~90 gun) oldugu icin, hafta sonu/tatil kaymalarina
# karsi tampon payiyla ~95 takvim gunu tutulur.
TUTULACAK_TAKVIM_GUNU = 95

# Hesaplanacak pencereler: (etiket, kac takvim gunu once)
PENCERELER = [
    ("1H", 7),
    ("1A", 30),
    ("2A", 60),
    ("3A", 90),
]

# master_dagilim.parquet'teki sabit kolonlar (varlik kalemi DEGIL).
SABIT_KOLONLAR = {"date", "kind", "fund_code", "fund_name"}


# Bir gunun gecerli sayilmasi icin, 54 varlik kaleminin toplaminin bu
# araliktaki bir yerde olmasi gerekir. TEFAS bazi nadir gunlerde eksik/
# bozuk veri dondurebiliyor (orn. tum kalemler ~0 gelirse toplam 0 olur,
# bu da bir onceki/sonraki gune gore YAPAY ve devasa bir "degisim" gibi
# gorunur). Bu gunler pencereden tamamen CIKARILIR - sanki hic olusmamis
# gibi, bir sonraki gecerli gunun farki bir onceki GECERLI gune gore
# hesaplanir.
GECERLI_TOPLAM_ALT_SINIR = 90
GECERLI_TOPLAM_UST_SINIR = 110

# Tek bir varlik kaleminin kendisi de mantiksal olarak 0-100 disina
# CIKAMAZ (bir fon, tek bir varlik turunde toplam degerinin %100'unden
# fazlasini tutamaz). TEFAS'in API'sinde nadiren tek bir kalemde olcek/
# birim hatasi goruluyor (orn. repo_pct=716 gibi) - toplam kontrolu bunu
# HER ZAMAN yakalamayabilir (baska bir kalem negatif/dusuk cikip
# dengeleyebilir). Bu yuzden kalem bazinda da ayri bir kontrol yapilir.
KALEM_ALT_SINIR = -1  # kucuk negatif tolerans (yuvarlama hatalari icin)
KALEM_UST_SINIR = 101  # kucuk pozitif tolerans

# Ek guvenlik agi: yukaridaki iki kontrolden sizan gunler olsa bile,
# teorik olarak bir gunluk L1 mesafe en fazla 200 olabilir (tum agirlik
# bir kalemden digerine tam kayarsa). Bu tavanin uzerindeki degerler
# GERCEK bir pozisyon degisikliginden degil, veri hatasindan kaynaklanir -
# bu yuzden skor hesaplamasinda 200'e KIRPILIR (clip), o gun/fon tamamen
# atilmaz.
GUNLUK_DEGISIM_TAVANI = 200


def gecersiz_gunleri_ayikla(pencere: pd.DataFrame, varlik_kolonlari: list[str]) -> pd.DataFrame:
    """Toplam agirligi GECERLI_TOPLAM_ALT_SINIR/UST_SINIR disinda kalan,
    VEYA herhangi bir tek kalemi KALEM_ALT_SINIR/UST_SINIR disinda kalan
    satirlari (fon-gun ciftlerini) pencereden cikarir."""
    toplam = pencere[varlik_kolonlari].sum(axis=1)
    toplam_gecerli = (toplam >= GECERLI_TOPLAM_ALT_SINIR) & (toplam <= GECERLI_TOPLAM_UST_SINIR)

    kalem_gecersiz = (
        (pencere[varlik_kolonlari] < KALEM_ALT_SINIR) |
        (pencere[varlik_kolonlari] > KALEM_UST_SINIR)
    ).any(axis=1)

    gecerli_maske = toplam_gecerli & (~kalem_gecersiz)

    cikarilan_sayisi = (~gecerli_maske).sum()
    if cikarilan_sayisi:
        log.warning(
            "%d satir gecersiz veri nedeniyle pencereden cikarildi "
            "(toplam disi ya da tek kalem disi deger).",
            cikarilan_sayisi
        )
    return pencere[gecerli_maske].reset_index(drop=True)


def master_dagilim_yukle() -> pd.DataFrame:
    yol = VERI_KLASORU / "master_dagilim.parquet"
    if not yol.exists():
        raise FileNotFoundError(
            f"{yol} bulunamadi. Once tefas_gunluk.py (veya tefas_ana.py) calistirilmali."
        )
    df = pd.read_parquet(yol)
    df["date"] = pd.to_datetime(df["date"])
    return df


def yat_kayan_pencereyi_olustur(master: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """master_dagilim'den SADECE YAT fonlarini ve SADECE son
    TUTULACAK_TAKVIM_GUNU kadar veriyi alir. Varlik kalemi kolonlarinin
    listesini de dondurur (SABIT_KOLONLAR haricindeki her sey)."""
    yat = master[master["kind"] == "YAT"].copy()
    if yat.empty:
        log.warning("master_dagilim.parquet icinde YAT tipi fon bulunamadi.")
        return yat, []

    varlik_kolonlari = [c for c in yat.columns if c not in SABIT_KOLONLAR]

    son_tarih = yat["date"].max()
    baslangic_tarih = son_tarih - timedelta(days=TUTULACAK_TAKVIM_GUNU)
    pencere = yat[yat["date"] >= baslangic_tarih][["date", "fund_code"] + varlik_kolonlari].copy()
    pencere = pencere.sort_values(["fund_code", "date"]).reset_index(drop=True)
    return pencere, varlik_kolonlari


def gunluk_degisimleri_hesapla(pencere: pd.DataFrame, varlik_kolonlari: list[str]) -> pd.DataFrame:
    """Her fon icin, ardisik gunler arasindaki L1 mesafeyi (toplam mutlak
    fark) hesaplar. Donen DataFrame: fund_code, date, gunluk_degisim.

    Guvenlik agi: gecersiz_gunleri_ayikla() cogu veri hatasini temizlemis
    olsa da, sizan degerlere karsi gunluk_degisim GUNLUK_DEGISIM_TAVANI
    degerine KIRPILIR (clip) - teorik olarak bir gunde mumkun olan en
    buyuk gercek degisim budur (tum agirlik bir kalemden digerine tam
    kayarsa |−100|+|100|=200)."""
    sonuclar = []
    for fon_kodu, grup in pencere.groupby("fund_code"):
        grup = grup.sort_values("date")
        farklar = grup[varlik_kolonlari].diff().abs().sum(axis=1).clip(upper=GUNLUK_DEGISIM_TAVANI)
        gecici = pd.DataFrame({
            "fund_code": fon_kodu,
            "date": grup["date"].values,
            "gunluk_degisim": farklar.values,
        })
        # Ilk gun icin diff() NaN doner (onceki gun yok) - o satiri atiyoruz.
        sonuclar.append(gecici.iloc[1:])

    if not sonuclar:
        return pd.DataFrame(columns=["fund_code", "date", "gunluk_degisim"])
    return pd.concat(sonuclar, ignore_index=True)


def aktiflik_skorlarini_hesapla(gunluk_degisimler: pd.DataFrame) -> pd.DataFrame:
    """Her fon icin PENCERELER listesindeki her arali icin, o pencere
    icindeki gunluk degisimlerin ORTALAMASINI alarak aktiflik skoru
    hesaplar. Sonuc: fund_code + her pencere icin bir aktiflik_XX skoru."""
    if gunluk_degisimler.empty:
        return pd.DataFrame()

    sonuclar = []
    for fon_kodu, grup in gunluk_degisimler.groupby("fund_code"):
        grup = grup.sort_values("date")
        son_tarih = grup["date"].max()

        satir = {"fund_code": fon_kodu}
        for etiket, gun_sayisi in PENCERELER:
            baslangic = son_tarih - timedelta(days=gun_sayisi)
            pencere_verisi = grup[grup["date"] > baslangic]
            if pencere_verisi.empty:
                satir[f"aktiflik_{etiket}"] = None
            else:
                satir[f"aktiflik_{etiket}"] = round(pencere_verisi["gunluk_degisim"].mean(), 4)
        sonuclar.append(satir)

    return pd.DataFrame(sonuclar)


def kategori_bilgisini_yukle() -> pd.DataFrame | None:
    """guncel_getiri_kategori.parquet'ten semsiye_turu ve kategori
    bilgisini yukler - percentile hesaplari icin gruplama anahtari."""
    yol = VERI_KLASORU / "guncel_getiri_kategori.parquet"
    if not yol.exists():
        log.warning("guncel_getiri_kategori.parquet bulunamadi - percentile hesaplanamayacak.")
        return None
    df = pd.read_parquet(yol)
    kolonlar = [c for c in ["fund_code", "semsiye_turu", "kategori"] if c in df.columns]
    return df[kolonlar].drop_duplicates(subset="fund_code", keep="last")


def percentile_hesapla(skorlar: pd.DataFrame, grup_kolonu: str, skor_kolonu: str) -> pd.Series:
    """Verilen grup_kolonu (orn. semsiye_turu) icinde, skor_kolonu'nun
    percentile rank'ini (0-100) hesaplar. Grup icinde tek fon varsa ya da
    skor eksikse NaN doner."""
    def _rank(g):
        return g.rank(pct=True) * 100

    return skorlar.groupby(grup_kolonu)[skor_kolonu].transform(_rank)


def main() -> int:
    log.info("Aktiflik skoru hesaplama basladi.")

    master = master_dagilim_yukle()
    pencere, varlik_kolonlari = yat_kayan_pencereyi_olustur(master)

    if pencere.empty:
        log.error("Kayan pencere olusturulamadi, veri yok.")
        return 1

    pencere = gecersiz_gunleri_ayikla(pencere, varlik_kolonlari)
    if pencere.empty:
        log.error("Gecersiz gun ayiklamasi sonrasi veri kalmadi.")
        return 1

    pencere_yol = VERI_KLASORU / "dagilim_kayan_pencere.parquet"
    pencere.to_parquet(pencere_yol, index=False)
    log.info("Dagilim kayan penceresi kaydedildi: %s (%d satir, %d fon, %d varlik kalemi, %s -> %s)",
              pencere_yol, len(pencere), pencere["fund_code"].nunique(), len(varlik_kolonlari),
              pencere["date"].min().date(), pencere["date"].max().date())

    gunluk_degisimler = gunluk_degisimleri_hesapla(pencere, varlik_kolonlari)
    if gunluk_degisimler.empty:
        log.error("Gunluk degisimler hesaplanamadi (yeterli ardisik gun verisi yok).")
        return 1

    skorlar = aktiflik_skorlarini_hesapla(gunluk_degisimler)
    if skorlar.empty:
        log.error("Aktiflik skorlari hesaplanamadi.")
        return 1

    kategori = kategori_bilgisini_yukle()
    if kategori is not None:
        skorlar = skorlar.merge(kategori, on="fund_code", how="left")

        skor_kolonlari = [f"aktiflik_{etiket}" for etiket, _ in PENCERELER]
        for skor_kolonu in skor_kolonlari:
            if "semsiye_turu" in skorlar.columns:
                skorlar[f"{skor_kolonu}_percentile_semsiye"] = percentile_hesapla(
                    skorlar, "semsiye_turu", skor_kolonu
                ).round(1)
            if "kategori" in skorlar.columns:
                # kategori bircok fon icin virgullu/coklu deger tasiyabilir
                # (orn. "Yerli Hisse, Hisse Senedi Yogun") - percentile
                # hesabinda TAM metni tek bir grup anahtari olarak kullaniyoruz
                # (alt-kategori bazinda ayristirma karmasikligi simdilik
                # eklenmedi, ileride genisletilebilir).
                skorlar[f"{skor_kolonu}_percentile_kategori"] = percentile_hesapla(
                    skorlar, "kategori", skor_kolonu
                ).round(1)
        log.info("Percentile hesaplamalari eklendi (semsiye_turu ve kategori bazinda).")
    else:
        log.warning("Kategori bilgisi olmadigi icin percentile hesaplanmadi.")

    skor_yol = VERI_KLASORU / "aktiflik_skoru.parquet"
    skorlar.to_parquet(skor_yol, index=False)
    log.info("Aktiflik skorlari kaydedildi: %s (%d fon)", skor_yol, len(skorlar))

    log.info("TAMAMLANDI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
