"""
TEFAS Gunluk Calisma - Ana Script (Gorev Zamanlayici bunu cagirir)
====================================================================
Her is gunu 10:10'da calisir. Sirasiyla:
  1) tefas_gunluk.py            -> fiyat + varlik dagilimi (pytefas)
  2) tefas_getiri_kategori.py   -> semsiye turu + risk + hazir getiriler
  3) tefas_kayan_pencere.py     -> 1G/1H/2H/3H/2A kayan pencere getirileri (YAT)
  4) tefas_portfoy_degerle.py   -> portfoy degerleme (portfoyum_ozet.csv varsa)
  5) tefas_sifrele.py           -> dashboard icin CSV'leri sifreler (TEFAS_PANO_SIFRE gerekir)
  6) tefas_git_gonder.py        -> sifreli dosyalari GitHub'a gonderir

Hepsi kendi log kayitlarini TEFAS_VERI/log.txt'e yazar.
Bu script sadece sirasiyla cagirir ve genel bir ozet basar.

5. ve 6. adimlar GitHub/sifreleme kurulumu henuz yapilmadiysa (ortam
degiskeni veya git repo yoksa) sessizce atlanir - ilk dort adim her
zaman calisir, mevcut yerel kullanim bozulmaz.

Kullanim:
  python tefas_ana.py
"""

import os
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

    # Kayan pencere getirileri (1G/1H/2H/3H/2A), master_info.parquet'in
    # guncel olmasina bagimli - bu yuzden tefas_gunluk.py'den hemen sonra,
    # portfoy degerlemeden once calisir.
    sonuc_kayan = calistir("tefas_kayan_pencere.py")

    # Portfoy degerleme, ilk ikisinin verisine bagimli oldugu icin en son calisir.
    # portfoyum_ozet.csv yoksa (henuz olusturulmadiysa) bu adimi atla, digerlerini bozma.
    portfoy_dosyasi = BU_KLASOR / "portfoyum_ozet.csv"
    if portfoy_dosyasi.exists():
        sonuc_3 = calistir("tefas_portfoy_degerle.py")
    else:
        log.info("portfoyum_ozet.csv bulunamadi, portfoy degerleme adimi atlaniyor.")
        sonuc_3 = True

    # Sifreleme + GitHub'a gonderme, sadece kurulum tamamlanmissa calisir.
    # TEFAS_PANO_SIFRE yoksa (yani bulut/sifreleme kurulumu henuz yapilmadiysa)
    # bu iki adim sessizce atlanir - yerel kullanimda hicbir sey bozulmaz.
    sifre_var = bool(os.environ.get("TEFAS_PANO_SIFRE"))
    git_repo_var = (BU_KLASOR / ".git").exists()

    if sifre_var:
        sonuc_4 = calistir("tefas_sifrele.py")
    else:
        log.info("TEFAS_PANO_SIFRE tanimli degil, sifreleme adimi atlaniyor.")
        sonuc_4 = True

    if sifre_var and git_repo_var:
        sonuc_5 = calistir("tefas_git_gonder.py")
    else:
        if not git_repo_var:
            log.info("Git reposu bulunamadi (.git yok), GitHub'a gonderme adimi atlaniyor.")
        sonuc_5 = True

    sure = (datetime.now() - baslangic).total_seconds()
    log.info("-"*60)
    if sonuc_1 and sonuc_2 and sonuc_kayan and sonuc_3 and sonuc_4 and sonuc_5:
        log.info("TUM ADIMLAR BASARILI. Sure: %.0f saniye", sure)
        donus = 0
    else:
        log.error("BAZI ADIMLAR BASARISIZ OLDU. Sure: %.0f saniye. log.txt'i kontrol et.", sure)
        donus = 1
    log.info("="*60)
    return donus


if __name__ == "__main__":
    sys.exit(main())
