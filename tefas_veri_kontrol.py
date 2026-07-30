"""
TEFAS Veri Kontrol Scripti
============================
master_info.parquet dosyasindaki verinin saglikli olup olmadigini kontrol eder:
  - Hangi tarih araligi cekilmis (en eski / en yeni gun)
  - Kac farkli is gunu var
  - Beklenen is gunleri ile karsilastirip HANGI GUNLERIN EKSIK oldugunu gosterir
  - Hafta sonlari otomatik dislanir (zaten veri olmamasi normal)
  - fund_code bazinda kac gunluk veri oldugunu da ozetler (opsiyonel detay)

Bu script SADECE OKUR, hicbir dosyayi degistirmez veya silmez.

Kullanim:
  python tefas_veri_kontrol.py                  -> master_info.parquet'i kontrol eder
  python tefas_veri_kontrol.py 2025-07-28 2026-07-28   -> belirli bir araligi da ayrica dogrular
"""

import sys
from pathlib import Path
from datetime import date, timedelta

import pandas as pd

VERI_KLASORU = Path.home() / "TEFAS_VERI"
DOSYA = VERI_KLASORU / "master_info.parquet"
DAGILIM_DOSYA = VERI_KLASORU / "master_dagilim.parquet"


def is_gunleri_uret(bas: date, bit: date) -> list[date]:
    """bas..bit araliginda (dahil) hafta ici gunleri dondurur."""
    gunler = []
    gun = bas
    while gun <= bit:
        if gun.weekday() < 5:   # 0-4 = Pazartesi-Cuma
            gunler.append(gun)
        gun += timedelta(days=1)
    return gunler


def ozet_bas(baslik: str) -> None:
    print("\n" + "=" * 70)
    print(baslik)
    print("=" * 70)


def main() -> int:
    if not DOSYA.exists():
        print(f"HATA: {DOSYA} bulunamadi.")
        return 1

    df = pd.read_parquet(DOSYA)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    ozet_bas("GENEL DURUM - master_info.parquet")
    print(f"Toplam satir sayisi   : {len(df):,}")
    print(f"Farkli fon sayisi     : {df['fund_code'].nunique():,}")
    print(f"En eski tarih         : {df['date'].min()}")
    print(f"En yeni tarih         : {df['date'].max()}")

    mevcut_gunler = sorted(df["date"].unique())
    print(f"Veri iceren toplam gun sayisi (benzersiz): {len(mevcut_gunler)}")

    # Genel aralikta (min-max) beklenen is gunlerine kiyasla eksik gun var mi?
    beklenen = is_gunleri_uret(df["date"].min(), df["date"].max())
    eksik_genel = sorted(set(beklenen) - set(mevcut_gunler))

    ozet_bas("EKSIK GUN KONTROLU (en eski -> en yeni tarih araliginda)")
    print(f"Bu aralikta olmasi beklenen is gunu sayisi: {len(beklenen)}")
    print(f"Gercekte veri olan is gunu sayisi         : {len(mevcut_gunler)}")
    if eksik_genel:
        print(f"\nUYARI: {len(eksik_genel)} is gununde veri YOK (tatil de olabilir, kontrol et):")
        for g in eksik_genel:
            print(f"   - {g}  ({g.strftime('%A')})")
    else:
        print("\nHarika: min-max tarih araliginda eksik is gunu yok.")

    # Eger kullanici belirli bir aralik verdiyse, o araligi da ayrica dogrula
    if len(sys.argv) == 3:
        bas = date.fromisoformat(sys.argv[1])
        bit = date.fromisoformat(sys.argv[2])
        beklenen_ozel = is_gunleri_uret(bas, bit)
        eksik_ozel = sorted(set(beklenen_ozel) - set(mevcut_gunler))

        ozet_bas(f"BELIRTILEN ARALIK KONTROLU: {bas} -> {bit}")
        print(f"Bu aralikta olmasi beklenen is gunu sayisi: {len(beklenen_ozel)}")
        if eksik_ozel:
            print(f"\nUYARI: Bu aralikta {len(eksik_ozel)} is gununde veri YOK:")
            for g in eksik_ozel:
                print(f"   - {g}  ({g.strftime('%A')})")
        else:
            print("\nBu belirtilen aralikta eksik is gunu yok - tam gorunuyor.")

    # Dagilim dosyasi da varsa hizli bir karsilastirma yapalim
    if DAGILIM_DOSYA.exists():
        dag = pd.read_parquet(DAGILIM_DOSYA)
        dag["date"] = pd.to_datetime(dag["date"]).dt.date
        dag_gunler = set(dag["date"].unique())
        info_gunler = set(mevcut_gunler)

        ozet_bas("INFO vs DAGILIM KARSILASTIRMASI")
        print(f"master_info.parquet gun sayisi   : {len(info_gunler)}")
        print(f"master_dagilim.parquet gun sayisi : {len(dag_gunler)}")
        sadece_info = sorted(info_gunler - dag_gunler)
        sadece_dagilim = sorted(dag_gunler - info_gunler)
        if sadece_info:
            print(f"\nSadece INFO'da olup DAGILIM'da olmayan gunler ({len(sadece_info)}):")
            for g in sadece_info:
                print(f"   - {g}")
        if sadece_dagilim:
            print(f"\nSadece DAGILIM'da olup INFO'da olmayan gunler ({len(sadece_dagilim)}):")
            for g in sadece_dagilim:
                print(f"   - {g}")
        if not sadece_info and not sadece_dagilim:
            print("\nIki dosya birbiriyle tam tutarli (ayni gunler mevcut).")

    ozet_bas("SONUC")
    print("Bu script sadece OKUYUCU niteliginde, hicbir veriyi degistirmedi.")
    print("Eksik gun listesi varsa, o gunleri tek tek asagidaki gibi tekrar cekebilirsin:")
    print("  python tefas_gunluk.py 2026-XX-XX 2026-XX-XX")
    return 0


if __name__ == "__main__":
    sys.exit(main())
