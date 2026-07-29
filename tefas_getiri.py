"""
TEFAS Getiri Hesaplayici
=========================
master_info.parquet icindeki birikmis fiyat gecmisinden donemsel
getirileri hesaplar (1H / 1A / 3A / 6A / YBB / 1Y).

TEFAS sitesindeki "getiri" tablosunun karsiligidir - ama API bu
degerleri hazir vermedigi icin fiyat gecmisinden kendimiz hesapliyoruz.
Avantaji: istedigin donemi tanimlayabilirsin.

Kullanim:
  python tefas_getiri.py                 -> tum fonlar, ekrana + CSV
  python tefas_getiri.py AAK TTE YAC     -> sadece belirtilen fonlar
"""

import sys
from pathlib import Path
from datetime import timedelta

import pandas as pd

VERI_KLASORU = Path.home() / "TEFAS_VERI"
MASTER = VERI_KLASORU / "master_info.parquet"

DONEMLER = {
    "1H":  timedelta(days=7),
    "1A":  timedelta(days=30),
    "3A":  timedelta(days=90),
    "6A":  timedelta(days=180),
    "1Y":  timedelta(days=365),
}


def en_yakin_fiyat(seri: pd.Series, hedef_tarih) -> float | None:
    """Hedef tarihe esit veya ondan onceki en son fiyati dondurur."""
    uygun = seri[seri.index <= hedef_tarih]
    return float(uygun.iloc[-1]) if len(uygun) else None


def main() -> int:
    if not MASTER.exists():
        print(f"Once tefas_gunluk.py calistirilmali. Bulunamadi: {MASTER}")
        return 1

    df = pd.read_parquet(MASTER)
    df["date"] = pd.to_datetime(df["date"])

    if len(sys.argv) > 1:
        kodlar = [k.upper() for k in sys.argv[1:]]
        df = df[df["fund_code"].isin(kodlar)]
        if df.empty:
            print("Bu fon kodlari icin veri yok:", ", ".join(kodlar))
            return 1

    son_tarih = df["date"].max()
    yil_basi = pd.Timestamp(year=son_tarih.year, month=1, day=1)

    satirlar = []
    for (kod, tip), grup in df.groupby(["fund_code", "kind"]):
        seri = grup.set_index("date")["price"].sort_index().dropna()
        if seri.empty:
            continue
        guncel = float(seri.iloc[-1])
        satir = {
            "fon_kodu": kod,
            "tip": tip,
            "fon_adi": grup["fund_name"].iloc[-1],
            "tarih": son_tarih.date(),
            "fiyat": guncel,
        }
        for ad, delta in DONEMLER.items():
            gecmis = en_yakin_fiyat(seri, son_tarih - delta)
            satir[f"getiri_{ad}_%"] = (
                round((guncel / gecmis - 1) * 100, 2) if gecmis else None
            )
        ybb = en_yakin_fiyat(seri, yil_basi)
        satir["getiri_YBB_%"] = round((guncel / ybb - 1) * 100, 2) if ybb else None
        satirlar.append(satir)

    sonuc = pd.DataFrame(satirlar).sort_values("getiri_1A_%", ascending=False)

    cikti = VERI_KLASORU / f"getiriler_{son_tarih.date()}.csv"
    sonuc.to_csv(cikti, index=False, encoding="utf-8-sig", sep=";", decimal=",")

    print(f"\nVeri tarihi: {son_tarih.date()}  |  Fon sayisi: {len(sonuc)}")
    print(f"Kaydedildi: {cikti}\n")
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(sonuc.head(25).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
