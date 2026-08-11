"""
TEFAS Gunluk Veri Cekme Scripti
================================
Her is gunu 10:10'da calisir. TEFAS'in resmi JSON API'sinden
tum fonlarin fiyat bilgisini ve portfoy dagilimini ceker.

Ciktilar (VERI_KLASORU altina):
  gunluk/tefas_info_YYYY-MM-DD.csv       -> o gunun fiyat/buyukluk verisi
  gunluk/tefas_dagilim_YYYY-MM-DD.csv    -> o gunun portfoy dagilimi
  master_info.parquet                    -> son ~95 gunluk KAYAN PENCERE (tekrarsiz)
  master_dagilim.parquet                 -> son ~95 gunluk KAYAN PENCERE (tekrarsiz)
  log.txt                                -> calisma kaydi

Kurulum:
  pip install pytefas pandas pyarrow

Kullanim:
  python tefas_gunluk.py              -> son yayinlanan gunu ceker
  python tefas_gunluk.py 2026-07-24   -> belirli bir gunu ceker
  python tefas_gunluk.py 2026-01-01 2026-07-24  -> tarih araligi (geriye donuk doldurma)
"""

import sys
import time
import logging
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
from pytefas import Crawler, TefasAPIError, TefasRateLimitError

# ----------------------------------------------------------------------
# AYARLAR - kendine gore degistir
# ----------------------------------------------------------------------
VERI_KLASORU = Path.home() / "TEFAS_VERI"   # Windows'ta: C:\Users\<sen>\TEFAS_VERI
FON_TIPLERI  = ("YAT", "EMK", "BYF")        # Yatirim / Emeklilik / Borsa Yatirim fonlari
DAGILIM_CEK  = True                         # portfoy dagilimi da cekilsin mi
GERI_BAKIS   = 5                            # veri bulunamazsa kac gun geriye bakilsin
DENEME       = 4                            # 10:10'da veri yoksa kac kez tekrar denensin
DENEME_ARASI = 300                          # saniye (5 dakika)

# Master dosyalarin ne kadarlik gecmisi tutacagi (kayan pencere).
# Aktif Yonetim Skoru en uzun 90 gunluk (3 Ay) pencereyi kullaniyor,
# bu yuzden en az o kadar + tampon gerekiyor. Ayni sayi
# tefas_aktiflik_skoru.py icindeki TUTULACAK_TAKVIM_GUNU ile TUTARLI
# tutulmali - biri degisirse digeri de guncellenmeli.
TUTULACAK_TAKVIM_GUNU = 95

# ----------------------------------------------------------------------

VERI_KLASORU.mkdir(parents=True, exist_ok=True)
(VERI_KLASORU / "gunluk").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(VERI_KLASORU / "log.txt", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tefas")


def son_yayinlanan_gunu_bul(tefas: Crawler) -> tuple[pd.DataFrame, date] | tuple[None, None]:
    """Bugunden baslayip geriye dogru veri bulunan ilk gunu dondurur.

    TEFAS sabah 10:00 civarinda genellikle BIR ONCEKI is gununun fiyatlarini
    yayinlar. Bu yuzden 'bugunun tarihi' sabit yazilmaz - veri bulunana kadar
    geriye bakilir. Hafta sonu ve resmi tatiller de boylece otomatik atlanir.
    """
    bugun = date.today()
    for i in range(GERI_BAKIS + 1):
        gun = bugun - timedelta(days=i)
        if gun.weekday() >= 5:          # 5=Cumartesi, 6=Pazar
            continue
        try:
            df = tefas.fetch_many(gun, kinds=FON_TIPLERI, columns="info")
        except (TefasAPIError, TefasRateLimitError) as e:
            log.warning("%s icin API hatasi: %s", gun, e)
            time.sleep(10)
            continue
        if df is not None and not df.empty:
            log.info("Veri bulundu: %s (%d fon)", gun, len(df))
            return df, gun
        log.info("%s icin veri yok, bir onceki gune bakiliyor...", gun)
    return None, None


def birlestir_kaydet(yeni: pd.DataFrame, dosya: Path, anahtar: list[str]) -> None:
    """Yeni veriyi master dosyaya ekler, mukerrer satirlari temizler,
    ve TUTULACAK_TAKVIM_GUNU'ndan eski satirlari ATAR (kayan pencere).

    Boylece master_info.parquet / master_dagilim.parquet buyumeye devam
    etmez - her gun en eski gun dusup en yeni gun eklenir, dosya boyutu
    sabit kalir."""
    if dosya.exists():
        eski = pd.read_parquet(dosya)
        birlesik = pd.concat([eski, yeni], ignore_index=True)
    else:
        birlesik = yeni
    birlesik = (
        birlesik.drop_duplicates(subset=anahtar, keep="last")
        .sort_values(anahtar)
        .reset_index(drop=True)
    )

    if "date" in birlesik.columns and not birlesik.empty:
        son_tarih = pd.to_datetime(birlesik["date"]).max()
        sinir_tarih = son_tarih - pd.Timedelta(days=TUTULACAK_TAKVIM_GUNU)
        oncesi_satir = len(birlesik)
        birlesik = birlesik[pd.to_datetime(birlesik["date"]) >= sinir_tarih].reset_index(drop=True)
        atilan = oncesi_satir - len(birlesik)
        if atilan:
            log.info("%s: %d gunden eski %d satir kayan pencereden cikarildi.",
                     dosya.name, TUTULACAK_TAKVIM_GUNU, atilan)

    birlesik.to_parquet(dosya, index=False)
    log.info("%s guncellendi -> toplam %d satir", dosya.name, len(birlesik))


def gunu_isle(tefas: Crawler, info: pd.DataFrame, gun: date) -> None:
    etiket = gun.isoformat()

    info.to_csv(
        VERI_KLASORU / "gunluk" / f"tefas_info_{etiket}.csv",
        index=False, encoding="utf-8-sig", sep=";", decimal=",",
    )
    birlestir_kaydet(info, VERI_KLASORU / "master_info.parquet",
                     ["date", "kind", "fund_code"])

    if DAGILIM_CEK:
        try:
            dag = tefas.fetch_many(gun, kinds=FON_TIPLERI, columns="breakdown")
            if dag is not None and not dag.empty:
                dag.to_csv(
                    VERI_KLASORU / "gunluk" / f"tefas_dagilim_{etiket}.csv",
                    index=False, encoding="utf-8-sig", sep=";", decimal=",",
                )
                birlestir_kaydet(dag, VERI_KLASORU / "master_dagilim.parquet",
                                 ["date", "kind", "fund_code"])
        except (TefasAPIError, TefasRateLimitError) as e:
            log.error("Dagilim verisi cekilemedi: %s", e)


def main() -> int:
    tefas = Crawler(timeout=60, max_retry=5)

    # --- Elle tarih verilmisse: tek gun veya aralik ---
    if len(sys.argv) > 1:
        bas = sys.argv[1]
        bit = sys.argv[2] if len(sys.argv) > 2 else None
        log.info("Elle cekim: %s -> %s", bas, bit or bas)
        info = tefas.fetch_many(bas, bit, kinds=FON_TIPLERI, columns="info")
        if info is None or info.empty:
            log.error("Veri gelmedi.")
            return 1
        for gun, grup in info.groupby("date"):
            gunu_isle(tefas, grup, pd.Timestamp(gun).date())
        return 0

    # --- Otomatik gunluk cekim ---
    for deneme in range(1, DENEME + 1):
        info, gun = son_yayinlanan_gunu_bul(tefas)
        if info is not None:
            gunu_isle(tefas, info, gun)
            log.info("TAMAMLANDI.")
            return 0
        log.warning("Deneme %d/%d basarisiz. %d sn sonra tekrar.",
                    deneme, DENEME, DENEME_ARASI)
        if deneme < DENEME:
            time.sleep(DENEME_ARASI)

    log.error("Veri alinamadi - tum denemeler tukendi.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
