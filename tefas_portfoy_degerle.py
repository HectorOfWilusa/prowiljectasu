"""
TEFAS Portfoy Degerleme Scripti
=================================
Bu script sunlari birlestirir:
  1) portfoyum_ozet.csv         -> hangi fondan kac pay, ne maliyetle aldin
  2) portfoyum_lot_bazli.csv    -> (varsa) her alimin kendi tarihi/fiyati - gunluk kazanc hesabi icin
  3) TEFAS_VERI/master_info.parquet -> gunun en guncel TEFAS fiyati (tefas_gunluk.py'nin ciktisi)

...ve her fon icin GUNCEL DEGER + KAR/ZARAR + GUNLUK ORTALAMA KAZANC hesaplar.
Ayrica varsa guncel_getiri_kategori.parquet dosyasindan semsiye turu/risk
bilgisini de ekler (kategori bazinda dagilim analizi icin).

GUNLUK ORTALAMA KAZANC YONTEMI (onemli - kaba "ilk alimdan bugune gun farki"
YONTEMI DEGIL):
  Her ayri alim (lot) kendi alis tarihinden bugune kac gun gectigini bilir.
  Once HER LOT icin ayri ayri gunluk ortalama getiri hesaplanir:
      lot_getiri_% = (guncel_fiyat / lot_alis_fiyati - 1) * 100
      lot_gunluk_% = lot_getiri_% / lot_yasi_gun
  Sonra fon bazinda bu lot'lar, LOT MALIYETI ile agirliklandirilarak
  tek bir "gunluk_ortalama_kazanc_%" degerine birlestirilir:
      gunluk_ortalama_kazanc_% = sum(lot_gunluk_% * lot_maliyeti) / sum(lot_maliyeti)
  Bu sayede yakin zamanda alinan buyuk bir lot ile uzun suredir elde tutulan
  kucuk bir lot birbirini yanlis yonde etkilemez.

  portfoyum_lot_bazli.csv yoksa bu adim sessizce atlanir (diger her sey
  calismaya devam eder), cunku gunluk kazanc hesabi icin lot detayi sarttir.

portfoyum_ozet.csv formati (Excel'de bu sekilde tut):
  fon_kodu ; fon_adi ; toplam_pay ; agirlikli_ort_alis_fiyati ; ilk_alis_tarihi ; lot_sayisi ; toplam_maliyet_tl

portfoyum_lot_bazli.csv formati (varsa, gunluk kazanc icin kullanilir):
  fon_kodu ; fon_adi ; alis_tarihi ; pay_sayisi ; alis_fiyati ; maliyet_tl

Ciktilar (VERI_KLASORU altina):
  portfoy_degerleme_YYYY-MM-DD.csv   -> guncel deger + kar/zarar + gunluk kazanc tablosu
  portfoy_kategori_dagilimi.csv      -> semsiye turune gore portfoy agirligi

Kullanim:
  python tefas_portfoy_degerle.py
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd

VERI_KLASORU = Path.home() / "TEFAS_VERI"
BU_KLASOR = Path(__file__).resolve().parent

PORTFOY_ARANACAK_YERLER = [
    BU_KLASOR / "portfoyum_ozet.csv",
    VERI_KLASORU / "portfoyum_ozet.csv",
]
LOT_ARANACAK_YERLER = [
    BU_KLASOR / "portfoyum_lot_bazli.csv",
    VERI_KLASORU / "portfoyum_lot_bazli.csv",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(VERI_KLASORU / "log.txt", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tefas-portfoy")


def portfoy_dosyasini_bul() -> Path:
    for yol in PORTFOY_ARANACAK_YERLER:
        if yol.exists():
            return yol
    aranan = "\n  ".join(str(y) for y in PORTFOY_ARANACAK_YERLER)
    raise FileNotFoundError(
        f"portfoyum_ozet.csv bulunamadi. Su konumlara bakildi:\n  {aranan}\n"
        f"Dosyayi bu script ile ayni klasore (TEFAS klasoru) koy."
    )


def lot_dosyasini_bul() -> Path | None:
    for yol in LOT_ARANACAK_YERLER:
        if yol.exists():
            return yol
    return None


def guncel_fiyatlari_yukle() -> pd.DataFrame:
    yol = VERI_KLASORU / "master_info.parquet"
    if not yol.exists():
        raise FileNotFoundError(
            f"{yol} bulunamadi. Once tefas_gunluk.py (veya tefas_ana.py) calistirilmali."
        )
    df = pd.read_parquet(yol)
    df["date"] = pd.to_datetime(df["date"])
    son = (
        df.sort_values("date")
        .groupby("fund_code", as_index=False)
        .last()[["fund_code", "date", "price"]]
        .rename(columns={"date": "fiyat_tarihi", "price": "guncel_fiyat"})
    )
    return son


def kategori_bilgisini_yukle() -> pd.DataFrame | None:
    yol = VERI_KLASORU / "guncel_getiri_kategori.parquet"
    if not yol.exists():
        log.warning("guncel_getiri_kategori.parquet bulunamadi - kategori/risk bilgisi eklenmeyecek.")
        return None
    df = pd.read_parquet(yol)
    kolonlar = ["fund_code", "semsiye_turu", "kategori", "risk_degeri",
                "getiri_1A_%", "getiri_3A_%", "getiri_6A_%", "getiri_YBB_%", "getiri_1Y_%"]
    mevcut = [k for k in kolonlar if k in df.columns]
    return df[mevcut].drop_duplicates(subset="fund_code", keep="last")


def kayan_pencere_getirilerini_yukle() -> pd.DataFrame | None:
    """tefas_kayan_pencere.py'nin ciktisi (1G/1H/2H/3H/2A getirileri).
    Dosya yoksa (henuz calistirilmadiysa) sessizce None doner."""
    yol = VERI_KLASORU / "getiri_kayan_pencere.parquet"
    if not yol.exists():
        log.warning("getiri_kayan_pencere.parquet bulunamadi - kisa vadeli getiriler eklenmeyecek.")
        return None
    df = pd.read_parquet(yol)
    return df.drop_duplicates(subset="fund_code", keep="last")


def gunluk_ortalama_kazanc_hesapla(guncel_fiyatlar: pd.DataFrame) -> pd.DataFrame | None:
    """Her fon icin lot-agirlikli gunluk ortalama kazanc yuzdesini hesaplar.

    Donen DataFrame: fon_kodu, gunluk_ortalama_kazanc_%
    Lot dosyasi yoksa None doner (cagiran taraf bu adimi atlar).
    """
    lot_yolu = lot_dosyasini_bul()
    if lot_yolu is None:
        log.warning("portfoyum_lot_bazli.csv bulunamadi - gunluk ortalama kazanc hesaplanmayacak.")
        return None

    lotlar = pd.read_csv(lot_yolu, sep=";", decimal=",", encoding="utf-8-sig")
    gerekli = {"fon_kodu", "alis_tarihi", "pay_sayisi", "alis_fiyati"}
    eksik = gerekli - set(lotlar.columns)
    if eksik:
        log.warning("portfoyum_lot_bazli.csv icinde eksik kolonlar (%s) - gunluk kazanc atlaniyor.", eksik)
        return None

    lotlar["alis_tarihi"] = pd.to_datetime(lotlar["alis_tarihi"], dayfirst=True, errors="coerce")
    if lotlar["alis_tarihi"].isna().any():
        log.warning("Bazi lot satirlarinda tarih parse edilemedi, o satirlar atlanacak.")
        lotlar = lotlar.dropna(subset=["alis_tarihi"])

    lotlar = lotlar.merge(
        guncel_fiyatlar[["fund_code", "guncel_fiyat"]],
        left_on="fon_kodu", right_on="fund_code", how="left"
    ).drop(columns=["fund_code"])

    lotlar = lotlar[lotlar["guncel_fiyat"].notna()].copy()
    if lotlar.empty:
        return None

    bugun = pd.Timestamp.now().normalize()
    lotlar["lot_yasi_gun"] = (bugun - lotlar["alis_tarihi"]).dt.days
    # Bugun alinmis bir lot (0 gun) bolme hatasi vermesin diye en az 1 gun sayiyoruz.
    lotlar["lot_yasi_gun"] = lotlar["lot_yasi_gun"].clip(lower=1)

    lotlar["lot_maliyeti"] = lotlar["pay_sayisi"] * lotlar["alis_fiyati"]
    lotlar["lot_getiri_%"] = (lotlar["guncel_fiyat"] / lotlar["alis_fiyati"] - 1) * 100
    lotlar["lot_gunluk_%"] = lotlar["lot_getiri_%"] / lotlar["lot_yasi_gun"]

    def agirlikli_gunluk(g: pd.DataFrame) -> float:
        toplam_maliyet = g["lot_maliyeti"].sum()
        if toplam_maliyet == 0:
            return float("nan")
        return (g["lot_gunluk_%"] * g["lot_maliyeti"]).sum() / toplam_maliyet

    sonuc = (
        lotlar.groupby("fon_kodu")
        .apply(agirlikli_gunluk, include_groups=False)
        .reset_index(name="gunluk_ortalama_kazanc_%")
    )
    return sonuc


def main() -> int:
    portfoy_yolu = portfoy_dosyasini_bul()
    log.info("Portfoy dosyasi: %s", portfoy_yolu)

    portfoy = pd.read_csv(portfoy_yolu, sep=";", decimal=",", encoding="utf-8-sig")
    gerekli = {"fon_kodu", "fon_adi", "toplam_pay", "agirlikli_ort_alis_fiyati", "toplam_maliyet_tl"}
    eksik = gerekli - set(portfoy.columns)
    if eksik:
        raise ValueError(f"portfoyum_ozet.csv icinde eksik kolonlar: {eksik}")

    guncel = guncel_fiyatlari_yukle()

    birlesik = portfoy.merge(
        guncel, left_on="fon_kodu", right_on="fund_code", how="left"
    ).drop(columns=["fund_code"])

    eslesmeyen = birlesik[birlesik["guncel_fiyat"].isna()]
    if not eslesmeyen.empty:
        log.warning(
            "UYARI: %d fon icin guncel fiyat bulunamadi (TEFAS'ta kod degismis/kapanmis olabilir): %s",
            len(eslesmeyen), ", ".join(eslesmeyen["fon_kodu"].tolist())
        )

    birlesik["guncel_deger_tl"] = birlesik["toplam_pay"] * birlesik["guncel_fiyat"]
    birlesik["kar_zarar_tl"] = birlesik["guncel_deger_tl"] - birlesik["toplam_maliyet_tl"]
    birlesik["kar_zarar_%"] = (
        (birlesik["guncel_deger_tl"] / birlesik["toplam_maliyet_tl"] - 1) * 100
    )

    gunluk_kazanc = gunluk_ortalama_kazanc_hesapla(guncel)
    if gunluk_kazanc is not None:
        birlesik = birlesik.merge(gunluk_kazanc, on="fon_kodu", how="left")
        log.info("Gunluk ortalama kazanc hesaplandi (%d fon).", gunluk_kazanc["fon_kodu"].nunique())

    kategori = kategori_bilgisini_yukle()
    if kategori is not None:
        birlesik = birlesik.merge(
            kategori, left_on="fon_kodu", right_on="fund_code", how="left"
        ).drop(columns=["fund_code"], errors="ignore")

    kayan_pencere = kayan_pencere_getirilerini_yukle()
    if kayan_pencere is not None:
        birlesik = birlesik.merge(
            kayan_pencere, left_on="fon_kodu", right_on="fund_code", how="left"
        ).drop(columns=["fund_code"], errors="ignore")
        log.info("Kayan pencere getirileri eklendi.")

    toplam_maliyet = birlesik["toplam_maliyet_tl"].sum()
    toplam_deger = birlesik["guncel_deger_tl"].sum(skipna=True)
    toplam_kz = toplam_deger - toplam_maliyet
    toplam_kz_pct = (toplam_deger / toplam_maliyet - 1) * 100 if toplam_maliyet else None

    birlesik = birlesik.sort_values("guncel_deger_tl", ascending=False)

    bugun = datetime.now().strftime("%Y-%m-%d")
    cikti_yol = VERI_KLASORU / f"portfoy_degerleme_{bugun}.csv"
    birlesik.to_csv(cikti_yol, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    birlesik.to_csv(VERI_KLASORU / "guncel_portfoy_degerleme.csv",
                     index=False, encoding="utf-8-sig", sep=";", decimal=",")

    if "semsiye_turu" in birlesik.columns:
        kat_dagilim = (
            birlesik.groupby("semsiye_turu", as_index=False)["guncel_deger_tl"]
            .sum()
            .sort_values("guncel_deger_tl", ascending=False)
        )
        kat_dagilim["agirlik_%"] = round(kat_dagilim["guncel_deger_tl"] / toplam_deger * 100, 2)
        kat_dagilim.to_csv(VERI_KLASORU / "portfoy_kategori_dagilimi.csv",
                           index=False, encoding="utf-8-sig", sep=";", decimal=",")
        log.info("Kategori dagilimi kaydedildi: portfoy_kategori_dagilimi.csv")

    log.info("-" * 60)
    log.info("TOPLAM MALIYET   : %.2f TL", toplam_maliyet)
    log.info("TOPLAM GUNCEL DEGER: %.2f TL", toplam_deger)
    log.info("TOPLAM KAR/ZARAR : %.2f TL (%.2f%%)", toplam_kz, toplam_kz_pct or 0)
    log.info("-" * 60)
    log.info("Detay kaydedildi: %s", cikti_yol)
    log.info("TAMAMLANDI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
