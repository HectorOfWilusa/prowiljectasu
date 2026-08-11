"""
TEFAS Panosu - Sifreli Dosyalari GitHub'a Gonderme Scripti
=============================================================
tefas_sifrele.py'nin urettigi sifreli/ klasorunu git ile GitHub
reposuna gonderir (add, commit, push).

Bu script hem YEREL bilgisayarda hem GitHub Actions icinde calisir:
  - Yerelde: git zaten kurulu ve repoya baglanmis olmali (bkz. KURULUM.md)
  - GitHub Actions'ta: is akisinin kendisi git kimligini ayarlar, bu
    script sadece add/commit/push yapar

Degisiklik yoksa (bugunku veri dunkuyle birebir ayniysa) commit
atlanir - bos commit hatasi vermez.

Kullanim:
  python tefas_git_gonder.py
"""

import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime

VERI_KLASORU = Path.home() / "TEFAS_VERI"
BU_KLASOR = Path(__file__).resolve().parent
SIFRELI_KLASOR = BU_KLASOR / "sifreli"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(VERI_KLASORU / "log.txt", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tefas-git")


def komut_calistir(komut: list[str]) -> tuple[bool, str]:
    sonuc = subprocess.run(
        komut, cwd=str(BU_KLASOR), capture_output=True, text=True
    )
    cikti = (sonuc.stdout or "") + (sonuc.stderr or "")
    return sonuc.returncode == 0, cikti.strip()


# Bu dosyalar GitHub Actions'ta her calisma bagimsiz bir ortamda basladigi
# icin (repo her seferinde sifirdan indirilir), eger buraya commit
# EDILMEZSE ertesi gunku calisma dunku veriyi hic GORMEZ - master_info,
# master_dagilim, kayan pencere gibi "birikimli" dosyalar aslinda hicbir
# zaman birikmez, her gun tek gunluk veriyle sifirdan baslar. Kayan
# pencere / aktiflik skoru gibi "ardisik gun karsilastirmasi" gerektiren
# hesaplamalar bu yuzden surekli "yeterli veri yok" hatasi verir.
#
# Cozum: sifreli/ ile BIRLIKTE bu ham/ara veri dosyalarini da commit'liyoruz.
# Bunlar sifrelenmemis durumda kalir (zaten TEFAS'in kendi genel/kamuya
# acik API verisi - gizli/kisisel bir sey icermiyor). log.txt kasten
# DAHIL EDILMEDI - surekli buyuyen, deger tasimayan bir dosya.
TAKIP_EDILECEK_VERI_DOSYALARI = [
    "TEFAS_VERI/master_info.parquet",
    "TEFAS_VERI/master_dagilim.parquet",
    "TEFAS_VERI/kayan_pencere_60gun.parquet",
    "TEFAS_VERI/getiri_kayan_pencere.parquet",
    "TEFAS_VERI/dagilim_kayan_pencere.parquet",
    "TEFAS_VERI/aktiflik_skoru.parquet",
]


def main() -> int:
    if not SIFRELI_KLASOR.exists():
        log.error("sifreli/ klasoru bulunamadi. Once tefas_sifrele.py calistirilmali.")
        return 1

    eklenecekler = ["sifreli/"]
    for goreli_yol in TAKIP_EDILECEK_VERI_DOSYALARI:
        if (BU_KLASOR / goreli_yol).exists():
            eklenecekler.append(goreli_yol)
        else:
            log.info("Bulunamadi, commit'e eklenmiyor: %s", goreli_yol)

    basarili, cikti = komut_calistir(["git", "add"] + eklenecekler)
    if not basarili:
        log.error("git add basarisiz: %s", cikti)
        return 1

    # Degisiklik yoksa commit atlanir - bu hata degil, normal bir durumdur.
    durum_basarili, durum_cikti = komut_calistir(["git", "status", "--porcelain"] + eklenecekler)
    if durum_basarili and not durum_cikti:
        log.info("Degisiklik yok, gonderilecek yeni veri bulunmuyor. Atlaniyor.")
        return 0

    tarih_etiket = datetime.now().strftime("%Y-%m-%d %H:%M")
    basarili, cikti = komut_calistir(
        ["git", "commit", "-m", f"TEFAS veri guncelleme - {tarih_etiket}"]
    )
    if not basarili:
        log.error("git commit basarisiz: %s", cikti)
        return 1
    log.info("Commit olusturuldu: %s", cikti.splitlines()[0] if cikti else "")

    basarili, cikti = komut_calistir(["git", "push"])
    if not basarili:
        log.error("git push basarisiz: %s", cikti)
        return 1

    log.info("GitHub'a gonderildi (push basarili).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
