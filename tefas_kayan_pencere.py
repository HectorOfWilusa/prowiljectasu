"""
TEFAS Kayan Pencere Getiri Hesaplama
=====================================
TEFAS'in resmi API'si sadece belirli sabit donemler icin hazir getiri
veriyor (1A, 3A, 6A, 1Y, YBB, 3Y, 5Y - bkz. tefas_getiri_kategori.py).
Bu script, TEFAS'in VERMEDIGI daha kisa/esnek araliklari KENDIMIZ
hesapliyoruz:

    1 Gun, 1 Hafta, 2 Hafta, 3 Hafta, 2 Ay

Veri kaynagi: master_info.parquet (tefas_gunluk.py'nin biriktirdigi tum
gecmis fiyat verisi). Bu script oradan SADECE YAT (yatirim fonlari)
tipini ve SADECE son ~65 gunluk kismini alip ayri, KUCUK ve SABIT
BOYUTLU bir "kayan pencere" dosyasina yazar:

    kayan_pencere_60gun.parquet

Bu dosya master_info.parquet gibi surekli BUYUMEZ - her calismada eski
gunler atilir, sadece en son ~65 is gunu tutulur. Boylece dashboard
tarafinda kucuk/hizli bir dosya olarak kalir.

Getiri hesabi TAKVIM GUNU ile yapilir (1 hafta = tam 7 takvim gunu
once, hafta sonu/tatil dahil). Hedef tarihte fiyat yoksa (hafta sonu/
resmi tatil), o tarihten once bulunan EN YAKIN is gununun fiyati
kullanilir - TEFAS'in kendi "veri bulunana kadar geriye bak" mantigiyla
tutarli olsun diye.

EMK (emeklilik) ve BYF (borsa yatirim fonu) fonlari bu hesaba DAHIL
DEGIL - sadece YAT (yatirim) fonlari icin calisir.

Ciktilar (VERI_KLASORU altina):
  kayan_pencere_60gun.parquet   -> son ~65 is gununun YAT fiyat gecmisi
  getiri_kayan_pencere.parquet  -> her YAT fonu icin hesaplanan % getiriler
                                    (fund_code, getiri_1G_%, getiri_1H_%,
                                     getiri_2H_%, getiri_3H_%, getiri_2A_%)

Kullanim:
  python tefas_kayan_pencere.py
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
log = logging.getLogger("tefas-kayan-pencere")

# En uzun pencere 2 Ay (~60 gun) oldugu icin, hafta sonu/tatil kaymalarina
# karsi biraz tampon payi ile ~70 takvim gunu = yaklasik 50 is gunu tutulur.
# Is gunlerinde bu fazlasiyla yeterli (70 gun icinde en az ~10 hafta sonu/
# tatil olsa bile 60 is gunu civarinda veri kalir).
TUTULACAK_TAKVIM_GUNU = 70

# Hesaplanacak pencereler: (etiket, kac takvim gunu once)
PENCERELER = [
    ("1G", 1),
    ("1H", 7),
    ("2H", 14),
    ("3H", 21),
    ("2A", 60),
]


def master_veriyi_yukle() -> pd.DataFrame:
    yol = VERI_KLASORU / "master_info.parquet"
    if not yol.exists():
        raise FileNotFoundError(
            f"{yol} bulunamadi. Once tefas_gunluk.py (veya tefas_ana.py) calistirilmali."
        )
    df = pd.read_parquet(yol)
    df["date"] = pd.to_datetime(df["date"])
    return df


def yat_kayan_pencereyi_olustur(master: pd.DataFrame) -> pd.DataFrame:
    """master_info'dan SADECE YAT fonlarini ve SADECE son
    TUTULACAK_TAKVIM_GUNU kadar veriyi alir - kucuk/sabit boyutlu
    kayan pencere dosyasini olusturur."""
    yat = master[master["kind"] == "YAT"].copy()
    if yat.empty:
        log.warning("master_info.parquet icinde YAT tipi fon bulunamadi.")
        return yat

    son_tarih = yat["date"].max()
    baslangic_tarih = son_tarih - timedelta(days=TUTULACAK_TAKVIM_GUNU)
    pencere = yat[yat["date"] >= baslangic_tarih][["date", "fund_code", "price"]].copy()
    pencere = pencere.sort_values(["fund_code", "date"]).reset_index(drop=True)
    return pencere


def en_yakin_onceki_fiyati_bul(fon_verisi: pd.DataFrame, hedef_tarih: pd.Timestamp) -> float | None:
    """Verilen fonun kendi tarih-fiyat gecmisinde, hedef_tarih'e esit veya
    ondan ONCEKI en yakin tarihin fiyatini dondurur. Bulunamazsa None."""
    uygun = fon_verisi[fon_verisi["date"] <= hedef_tarih]
    if uygun.empty:
        return None
    return uygun.iloc[-1]["price"]


def getirileri_hesapla(pencere: pd.DataFrame) -> pd.DataFrame:
    """Her fon icin PENCERELER listesindeki her arali icin % getiri
    hesaplar. Sonuc: fund_code + her pencere icin bir getiri_XX_% kolonu."""
    if pencere.empty:
        return pd.DataFrame()

    sonuclar = []
    for fon_kodu, grup in pencere.groupby("fund_code"):
        grup = grup.sort_values("date")
        son_satir = grup.iloc[-1]
        guncel_fiyat = son_satir["price"]
        guncel_tarih = son_satir["date"]

        satir = {"fund_code": fon_kodu}
        for etiket, gun_sayisi in PENCERELER:
            hedef_tarih = guncel_tarih - timedelta(days=gun_sayisi)
            eski_fiyat = en_yakin_onceki_fiyati_bul(grup, hedef_tarih)
            if eski_fiyat is None or eski_fiyat == 0:
                satir[f"getiri_{etiket}_%"] = None
            else:
                satir[f"getiri_{etiket}_%"] = round((guncel_fiyat / eski_fiyat - 1) * 100, 4)
        sonuclar.append(satir)

    return pd.DataFrame(sonuclar)


def main() -> int:
    log.info("Kayan pencere getiri hesaplama basladi.")

    master = master_veriyi_yukle()
    pencere = yat_kayan_pencereyi_olustur(master)

    if pencere.empty:
        log.error("Kayan pencere olusturulamadi, veri yok.")
        return 1

    pencere_yol = VERI_KLASORU / "kayan_pencere_60gun.parquet"
    pencere.to_parquet(pencere_yol, index=False)
    log.info("Kayan pencere kaydedildi: %s (%d satir, %d fon, %s -> %s)",
              pencere_yol, len(pencere), pencere["fund_code"].nunique(),
              pencere["date"].min().date(), pencere["date"].max().date())

    getiriler = getirileri_hesapla(pencere)
    if getiriler.empty:
        log.error("Getiri hesaplanamadi.")
        return 1

    getiri_yol = VERI_KLASORU / "getiri_kayan_pencere.parquet"
    getiriler.to_parquet(getiri_yol, index=False)
    log.info("Getiriler kaydedildi: %s (%d fon)", getiri_yol, len(getiriler))

    log.info("TAMAMLANDI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
