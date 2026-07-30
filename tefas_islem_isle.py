"""
TEFAS Islem Isleme Scripti - Portfoyu Otomatik Gunceller
============================================================
Bu script, ham alim/satim islemlerini (islemler.csv) FIFO yontemiyle
isleyip iki dosyayi OTOMATIK olarak yeniden uretir:
  - portfoyum_lot_bazli.csv   (her acik lot ayri satir)
  - portfoyum_ozet.csv        (fon bazinda ozet - toplam pay, agirlikli
                                ortalama alis fiyati, toplam maliyet)

Boylece Excel'de elle hesaplama yapmana GEREK KALMAZ - sadece yeni bir
alim/satim yaptiginda islemler.csv'ye TEK SATIR eklemen yeterli, geri
kalan her sey (ortalama fiyat, kalan pay, lot dagilimi) burada otomatik
hesaplanir.

FIFO MANTIGI (satislarda) - KANAL BAZINDA AYRI HAVUZLAR:
  Ayni fon FARKLI KANALLARDAN (orn. YKB, VKF, KVT gibi farkli banka/
  araci kurum hesaplari) alinmis olabilir. Bu durumda FIFO HER FON+KANAL
  KOMBINASYONU ICIN AYRI AYRI uygulanir - yani VKF hesabindaki bir satis,
  YKB hesabindaki lotlari HIC ETKILEMEZ. Bu, gercek hayatta farkli
  hesaplarin birbirinden bagimsiz olmasiyla tutarlidir.

  onemli: bu kanal ayrimi SADECE hesaplama asamasinda (FIFO) kullanilir.
  portfoyum_ozet.csv'ye yazarken kanallar tekrar FON BAZINDA BIRLESTIRILIR
  (dashboard ve mevcut format degismesin diye) - yani RIK gibi hem YKB hem
  VKF'den alinmis bir fon, ozet tabloda YINE TEK SATIR olarak gorunur,
  toplam pay ve toplam maliyet kanallarin toplami olur. Kanal detayi
  sadece portfoyum_lot_bazli.csv'de saklanir (istenirse oradan incelenir).

islemler.csv formati (ayni klasorde, ; ile ayrilmis, TR ondalik):
  fon_kodu;fon_adi;kanal;islem_tipi;tarih;pay_sayisi;fiyat
  NAU;NEO PORTFOY ALTIN FONU;YKB;ALIM;2026-07-15;1000;2,4531
  NAU;NEO PORTFOY ALTIN FONU;YKB;SATIM;2026-07-28;300;2,6120

  islem_tipi: sadece "ALIM" veya "SATIM" (buyuk/kucuk harf onemli degil)
  tarih: GG.AA.YYYY veya YYYY-AA-GG format ikisi de calisir
  fiyat: TR formatinda (virgullu) da yazilabilir, noktali da
  kanal: hangi banka/araci kurum hesabindan yapildigi (serbest metin)

Bu script CALISTIGINDA:
  1) islemler.csv'yi okur (tum gecmis islemler, kronolojik siralanir)
  2) Her fon+kanal kombinasyonu icin FIFO uygulayarak ACIK LOTLARI hesaplar
  3) portfoyum_lot_bazli.csv'yi bu acik lotlarla YENIDEN YAZAR
  4) portfoyum_ozet.csv'yi bu lotlardan OZET olarak YENIDEN YAZAR
  5) (Eger varsa) eski portfoyum_ozet.csv / lot_bazli.csv dosyalarinin
     yedegini .yedek uzantisiyla alir - yanlislikla veri kaybini onler

NOT: Bu script portfoyum_ozet.csv ve portfoyum_lot_bazli.csv dosyalarinin
ICERIGINI TAMAMEN islemler.csv'den turetir. Yani islemler.csv artik
TEK GERCEK KAYNAK (source of truth) - diger iki dosyaya ELLE MUDAHALE
ETME, hep bu script uzerinden guncelle.

Kurulum:
  pip install pandas

Kullanim:
  python tefas_islem_isle.py
"""

import sys
import shutil
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd

BU_KLASOR = Path(__file__).resolve().parent
VERI_KLASORU = Path.home() / "TEFAS_VERI"
VERI_KLASORU.mkdir(parents=True, exist_ok=True)

ISLEMLER_DOSYA = BU_KLASOR / "islemler.csv"
LOT_DOSYA = BU_KLASOR / "portfoyum_lot_bazli.csv"
OZET_DOSYA = BU_KLASOR / "portfoyum_ozet.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(VERI_KLASORU / "log.txt", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tefas-islem-isle")


def islemleri_yukle() -> pd.DataFrame:
    if not ISLEMLER_DOSYA.exists():
        raise FileNotFoundError(
            f"{ISLEMLER_DOSYA} bulunamadi. Once en az bir islem satiri icermesi lazim.\n"
            "Format: fon_kodu;fon_adi;kanal;islem_tipi;tarih;pay_sayisi;fiyat"
        )
    df = pd.read_csv(ISLEMLER_DOSYA, sep=";", decimal=",", encoding="utf-8-sig")
    gerekli = {"fon_kodu", "fon_adi", "kanal", "islem_tipi", "tarih", "pay_sayisi", "fiyat"}
    eksik = gerekli - set(df.columns)
    if eksik:
        raise ValueError(f"islemler.csv icinde eksik kolonlar: {eksik}")

    df["islem_tipi"] = df["islem_tipi"].str.upper().str.strip()
    gecersiz_tip = set(df["islem_tipi"].unique()) - {"ALIM", "SATIM"}
    if gecersiz_tip:
        raise ValueError(f"islemler.csv icinde gecersiz islem_tipi degerleri: {gecersiz_tip} (sadece ALIM/SATIM olmali)")

    # Tarih iki formatta da gelebilir: GG.AA.YYYY veya YYYY-AA-GG
    df["tarih"] = pd.to_datetime(df["tarih"], dayfirst=True, errors="coerce")
    if df["tarih"].isna().any():
        hatali = df[df["tarih"].isna()]
        raise ValueError(f"Tarih parse edilemeyen satirlar var:\n{hatali}")

    df["pay_sayisi"] = pd.to_numeric(df["pay_sayisi"], errors="coerce")
    df["fiyat"] = pd.to_numeric(df["fiyat"], errors="coerce")
    if df["pay_sayisi"].isna().any() or df["fiyat"].isna().any():
        raise ValueError("pay_sayisi veya fiyat kolonunda sayiya cevrilemeyen deger var.")

    df["kanal"] = df["kanal"].fillna("").astype(str).str.strip()

    df = df.sort_values(["fon_kodu", "kanal", "tarih"]).reset_index(drop=True)
    return df


def fifo_uygula(islemler: pd.DataFrame) -> pd.DataFrame:
    """Her fon+kanal kombinasyonu icin FIFO uygulayip ACIK LOTLARI dondurur.

    Donen DataFrame: fon_kodu, fon_adi, kanal, alis_tarihi, pay_sayisi,
    alis_fiyati, maliyet_tl (portfoyum_lot_bazli.csv ile ayni format + kanal)
    """
    acik_lotlar = []

    for (fon_kodu, kanal), grup in islemler.groupby(["fon_kodu", "kanal"]):
        fon_adi = grup["fon_adi"].iloc[0]
        # Bu fon+kanal kombinasyonu icin kendi lot kuyrugu (FIFO)
        kuyruk = []

        for _, satir in grup.iterrows():
            if satir["islem_tipi"] == "ALIM":
                kuyruk.append([satir["tarih"], satir["pay_sayisi"], satir["fiyat"]])
            else:  # SATIM
                satilacak = satir["pay_sayisi"]
                if satilacak <= 0:
                    continue
                while satilacak > 0:
                    if not kuyruk:
                        log.warning(
                            "UYARI: %s (kanal=%s) icin satilan pay sayisi, mevcut lotlardan fazla "
                            "(islemler.csv'de bir hata olabilir, tarih sirasini kontrol et).",
                            fon_kodu, kanal,
                        )
                        break
                    en_eski = kuyruk[0]
                    if en_eski[1] <= satilacak:
                        satilacak -= en_eski[1]
                        kuyruk.pop(0)
                    else:
                        en_eski[1] -= satilacak
                        satilacak = 0

        for tarih, kalan_pay, alis_fiyati in kuyruk:
            if kalan_pay <= 0:
                continue
            acik_lotlar.append({
                "fon_kodu": fon_kodu,
                "fon_adi": fon_adi,
                "kanal": kanal,
                "alis_tarihi": tarih.strftime("%d.%m.%Y"),
                "pay_sayisi": kalan_pay,
                "alis_fiyati": alis_fiyati,
                "maliyet_tl": kalan_pay * alis_fiyati,
            })

    return pd.DataFrame(acik_lotlar)


def ozet_uret(lotlar: pd.DataFrame) -> pd.DataFrame:
    """Acik lotlardan FON BAZINDA (kanallar birlestirilerek) ozet tablo uretir.

    NOT: FIFO hesabi kanal bazinda ayri yapildi (bkz. fifo_uygula), ama bu
    ozet tabloda goruntu amacli fon bazinda TEK SATIRA birlestiriyoruz -
    dashboard ve mevcut portfoyum_ozet.csv formatiyla tutarli kalsin diye.
    Kanal detayi istenirse portfoyum_lot_bazli.csv'de hala mevcuttur.
    """
    if lotlar.empty:
        return pd.DataFrame(columns=[
            "fon_kodu", "fon_adi", "toplam_pay", "agirlikli_ort_alis_fiyati",
            "ilk_alis_tarihi", "lot_sayisi", "toplam_maliyet_tl",
        ])

    lotlar = lotlar.copy()
    lotlar["_tarih_dt"] = pd.to_datetime(lotlar["alis_tarihi"], dayfirst=True)

    satirlar = []
    for fon_kodu, grup in lotlar.groupby("fon_kodu"):
        toplam_pay = grup["pay_sayisi"].sum()
        toplam_maliyet = grup["maliyet_tl"].sum()
        agirlikli_ort = toplam_maliyet / toplam_pay if toplam_pay else 0
        ilk_tarih = grup["_tarih_dt"].min()
        satirlar.append({
            "fon_kodu": fon_kodu,
            "fon_adi": grup["fon_adi"].iloc[0],
            "toplam_pay": toplam_pay,
            "agirlikli_ort_alis_fiyati": round(agirlikli_ort, 6),
            "ilk_alis_tarihi": ilk_tarih.strftime("%d.%m.%Y"),
            "lot_sayisi": len(grup),
            "toplam_maliyet_tl": round(toplam_maliyet, 2),
        })

    return pd.DataFrame(satirlar).sort_values("toplam_maliyet_tl", ascending=False)


def yedek_al(dosya: Path) -> None:
    if dosya.exists():
        yedek = dosya.with_suffix(dosya.suffix + ".yedek")
        shutil.copy2(dosya, yedek)
        log.info("Yedek alindi: %s", yedek.name)


def main() -> int:
    log.info("=" * 60)
    log.info("TEFAS ISLEM ISLEME BASLADI - %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    log.info("=" * 60)

    islemler = islemleri_yukle()
    log.info("Toplam %d islem okundu (%d fon, %d fon+kanal kombinasyonu).",
              len(islemler), islemler["fon_kodu"].nunique(),
              islemler.groupby(["fon_kodu", "kanal"]).ngroups)

    lotlar = fifo_uygula(islemler)
    log.info("FIFO sonrasi acik lot sayisi: %d", len(lotlar))

    ozet = ozet_uret(lotlar)
    log.info("Ozet tablo olusturuldu: %d fon+kanal satiri.", len(ozet))

    yedek_al(LOT_DOSYA)
    yedek_al(OZET_DOSYA)

    lotlar.to_csv(LOT_DOSYA, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    ozet.to_csv(OZET_DOSYA, index=False, encoding="utf-8-sig", sep=";", decimal=",")

    log.info("-" * 60)
    log.info("GUNCELLENDI: %s", LOT_DOSYA)
    log.info("GUNCELLENDI: %s", OZET_DOSYA)
    log.info("TAMAMLANDI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

