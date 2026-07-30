"""
TEFAS Kategori Kontrol Scripti
================================
guncel_portfoy_degerleme.csv dosyasini acar ve fon_kodu, fon_adi,
kategori kolonlarini ekrana basar - yeni eklenen "kategori" sutununun
dogru gelip gelmedigini kontrol etmek icin.

Bu script sadece OKUR, hicbir dosyayi degistirmez.

Kullanim:
  python kontrol.py
"""

import os
import sys

import pandas as pd

VERI_KLASORU = os.path.join(os.path.expanduser("~"), "TEFAS_VERI")
DOSYA = os.path.join(VERI_KLASORU, "guncel_portfoy_degerleme.csv")


def main():
    if not os.path.exists(DOSYA):
        print(f"HATA: {DOSYA} bulunamadi.")
        return 1

    df = pd.read_csv(DOSYA, sep=";", decimal=",", encoding="utf-8-sig")

    if "kategori" not in df.columns:
        print("UYARI: 'kategori' kolonu bu dosyada YOK.")
        print("Mevcut kolonlar:", list(df.columns))
        return 1

    print("=" * 70)
    print("FON KODU / FON ADI / KATEGORI")
    print("=" * 70)
    print(df[["fon_kodu", "fon_adi", "kategori"]].to_string())

    print()
    print("=" * 70)
    print("OZET")
    print("=" * 70)
    toplam = len(df)
    eslesen = df["kategori"].notna().sum()
    print(f"Toplam fon sayisi        : {toplam}")
    print(f"Kategorisi eslesen fon    : {eslesen}")
    print(f"Kategorisi eslesmeyen fon : {toplam - eslesen}")

    if eslesen < toplam:
        print()
        print("Kategorisi eslesmeyen fonlar:")
        for kod in df[df["kategori"].isna()]["fon_kodu"].tolist():
            print(f"  - {kod}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
