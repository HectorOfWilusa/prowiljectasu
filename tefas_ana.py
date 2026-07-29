"""
TEFAS Gunluk Calisma - Ana Script (Gorev Zamanlayici bunu cagirir)
====================================================================
Her is gunu 10:10'da calisir. Sirasiyla:
  1) tefas_gunluk.py            -> fiyat + varlik dagilimi (pytefas)
  2) tefas_getiri_kategori.py   -> semsiye turu + risk + hazir getiriler

Ikisi de kendi log kayitlarini TEFAS_VERI/log.txt'e yazar.
Bu script sadece sirasiyla cagirir ve genel bir ozet basar.

Kullanim:
  python tefas_ana.py
"""

import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime

VERI_KLASORU = Path.home() / "TEFAS_VERI"
VERI_KLASORU.mkdir(parents=True, exist_ok=True)
BU_KLASOR = Path(__file__).resolve().parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(VERI_KLASORU / "log.txt", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tefas-ana")


def calistir(script_adi: str) -> bool:
    yol = BU_KLASOR / script_adi
    log.info("BASLIYOR: %s", script_adi)
    sonuc = subprocess.run(
        [sys.executable, str(yol)],
        cwd=str(BU_KLASOR),
    )
    basarili = sonuc.returncode == 0
    log.info("%s -> %s (exit code %d)",
              script_adi, "BASARILI" if basarili else "BASARISIZ", sonuc.returncode)
    return basarili


def main() -> int:
    baslangic = datetime.now()
    log.info("="*60)
    log.info("TEFAS GUNLUK CALISMA BASLADI - %s", baslangic.strftime("%Y-%m-%d %H:%M:%S"))
    log.info("="*60)

    sonuc_1 = calistir("tefas_gunluk.py")
    sonuc_2 = calistir("tefas_getiri_kategori.py")

    # Portfoy degerleme, ilk ikisinin verisine bagimli oldugu icin en son calisir.
    # portfoyum_ozet.csv yoksa (henuz olusturulmadiysa) bu adimi atla, digerlerini bozma.
    portfoy_dosyasi = BU_KLASOR / "portfoyum_ozet.csv"
    if portfoy_dosyasi.exists():
        sonuc_3 = calistir("tefas_portfoy_degerle.py")
    else:
        log.info("portfoyum_ozet.csv bulunamadi, portfoy degerleme adimi atlaniyor.")
        sonuc_3 = True

    sure = (datetime.now() - baslangic).total_seconds()
    log.info("-"*60)
    if sonuc_1 and sonuc_2 and sonuc_3:
        log.info("TUM ADIMLAR BASARILI. Sure: %.0f saniye", sure)
        donus = 0
    else:
        log.error("BAZI ADIMLAR BASARISIZ OLDU. Sure: %.0f saniye. log.txt'i kontrol et.", sure)
        donus = 1
    log.info("="*60)
    return donus


if __name__ == "__main__":
    sys.exit(main())
