"""
TEFAS Getiri + Sema/Kategori Bilgisi (Resmi Karsilastirma Ekrani API'si)
=========================================================================
Bu modul, TEFAS'in kendi "Fon Getirileri" karsilastirma sayfasinin
(tefas.gov.tr/tr/fon-getirileri) arka planda kullandigi API'yi cagirir.

pytefas kutuphanesindeki iki endpoint'ten (fiyat + varlik dagilimi) FARKLI
bir uctur - bunu tarayici Network sekmesinden (.har dosyasi) bulup
dogruladik. Kutuphane degil, kendi yazdigimiz sade bir 'requests' cagrisi.

Bu API sunlari VERIYOR (pytefas'ta OLMAYAN alanlar):
  - fonTurAciklama : semsiye fon turu / kategori (ornek: "Hisse Senedi
                     Semsiye Fonu", "Kiymetli Madenler Semsiye Fonu")
  - riskDegeri     : TEFAS resmi risk skalasi (1-7)
  - getiri1a, getiri3a, getiri6a, getiri1y, getiriyb, getiri3y, getiri5y
                     : TEFAS'in KENDI HESAPLADIGI hazir getiri yuzdeleri
                     (bizim kendi hesapladigimiz tefas_getiri.py'a
                     alternatif/dogrulama olarak kullanilabilir)

Ayrica kurucu (fonKurucuGetir) ve fon turu (fonDetayGetir) referans
listelerini de ceker - filtreleme/gruplama icin.

Eger VERI_KLASORU altinda fon_kategori_referans.csv varsa (elle
hazirlanmis, semsiye_turu'ndan daha ince bir siniflandirma - Altin
Fonlari, Gumus Fonlari gibi), bu da AYRI bir "kategori" kolonu olarak
getiri_kategori_*.csv'ye eklenir. Dosya yoksa bu adim sessizce atlanir.

Kurulum:
  pip install requests pandas

Kullanim:
  python tefas_getiri_kategori.py            -> YAT + EMK + BYF, tumu
  python tefas_getiri_kategori.py YAT         -> sadece yatirim fonlari
"""

import sys
import json
import time
import logging
from pathlib import Path

import requests
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
log = logging.getLogger("tefas-getiri-kategori")

BASE = "https://www.tefas.gov.tr/api/funds"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/tr/fon-getirileri?fundType=YAT",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
}

# TEFAS'in kendi kolon adlarini okunabilir Turkce/Ingilizce karisik
# isimlere ceviriyoruz (mevcut master_info.parquet ile tutarli olsun diye
# fund_code / fund_name kullanildi, digerleri acik Turkce birakildi)
KOLON_ESLEME = {
    "fonKodu": "fund_code",
    "fonUnvan": "fund_name",
    "fonTurAciklama": "semsiye_turu",
    "tefasDurum": "tefas_islem_goruyor",
    "getiri1a": "getiri_1A_%",
    "getiri3a": "getiri_3A_%",
    "getiri6a": "getiri_6A_%",
    "getiri1y": "getiri_1Y_%",
    "getiriyb": "getiri_YBB_%",
    "getiri3y": "getiri_3Y_%",
    "getiri5y": "getiri_5Y_%",
    "riskDegeri": "risk_degeri",
}


def _istek_at(endpoint: str, gövde: dict, deneme: int = 3) -> dict:
    """POST istegi atar, basarisizsa kisa bekleyip tekrar dener."""
    url = f"{BASE}/{endpoint}"
    son_hata = None
    for i in range(deneme):
        try:
            r = requests.post(url, json=gövde, headers=HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()
            if data.get("errorCode"):
                raise RuntimeError(f"TEFAS API hatasi: {data.get('errorMessage')}")
            return data
        except Exception as e:
            son_hata = e
            log.warning("%s denemesi basarisiz (%d/%d): %s", endpoint, i + 1, deneme, e)
            time.sleep(5)
    raise RuntimeError(f"{endpoint} icin tum denemeler basarisiz: {son_hata}")


def getiri_ve_kategori_cek(fon_tipi: str = "YAT") -> pd.DataFrame:
    """Tum fonlarin semsiye turu + hazir getiri yuzdelerini ceker.

    fon_tipi: 'YAT' (yatirim), 'EMK' (emeklilik), 'BYF' (borsa yatirim)
    """
    gövde = {
        "dil": "TR",
        "fonTipi": fon_tipi,
        "kurucuKodu": None,
        "sfonTurKod": None,
        "fonTurAciklama": None,
        "islem": 1,
        "fonTurKod": None,
        "fonGrubu": None,
        "donemGetiri1a": "1",
        "donemGetiri3a": "1",
        "donemGetiri6a": "1",
        "donemGetiri1y": "1",
        "donemGetiriyb": "1",
        "donemGetiri3y": "1",
        "donemGetiri5y": "1",
        "basTarih": None,
        "bitTarih": None,
        "calismaTipi": 2,
        "getiriOrani": "1",
    }
    data = _istek_at("fonGetiriBazliBilgiGetir", gövde)
    df = pd.DataFrame(data.get("resultList") or [])
    if df.empty:
        return df
    df = df.rename(columns=KOLON_ESLEME)
    df.insert(0, "fon_tipi", fon_tipi)
    return df


def kurucu_listesi_cek(fon_tipi: str = "YAT") -> pd.DataFrame:
    """Portfoy yonetim sirketleri / kurucu listesi (filtre icin referans)."""
    data = _istek_at("fonKurucuGetir", {"fonTipi": fon_tipi, "dil": "TR"})
    df = pd.DataFrame(data.get("resultList") or [])
    if not df.empty:
        df = df.rename(columns={
            "kurucuKodu": "kurucu_kodu",
            "kurucuUnvan": "kurucu_unvan",
            "fonTipi": "fon_tipi",
        })
    return df


def fon_turu_listesi_cek(fon_tipi: str = "YAT") -> pd.DataFrame:
    """Semsiye fon turu / kategori referans listesi (filtre icin)."""
    data = _istek_at("fonDetayGetir", {"fonTipi": fon_tipi, "dil": "TR"})
    df = pd.DataFrame(data.get("resultList") or [])
    if not df.empty:
        df = df.rename(columns={
            "fonTipi": "fon_tipi",
            "fonTurKod": "fon_turu_kodu",
            "fonTurAciklama": "fon_turu_aciklama",
        })
    return df


def fon_kategori_referans_yukle() -> pd.DataFrame | None:
    """fon_kategori_referans.csv'yi yukler (elle hazirlanan, TEFAS'in resmi
    semsiye_turu'ndan DAHA INCE siniflandirma - Altin Fonlari, Gumus Fonlari
    gibi). Bu, semsiye_turu'nun YERINE DEGIL, ONUN YANINA eklenen AYRI bir
    "kategori" kolonu olarak kullanilir.

    Dosya formati (; ile ayrilmis, UTF-8):
      fon_kodu;kategoriler
      NAU;Altın Fonları, Emtia Fonları

    Dosya yoksa (henuz hazirlanmadiysa) sessizce None doner - diger her
    sey calismaya devam eder, "kategori" kolonu sadece eklenmez.
    """
    yol = VERI_KLASORU / "fon_kategori_referans.csv"
    if not yol.exists():
        log.warning("fon_kategori_referans.csv bulunamadi - 'kategori' kolonu eklenmeyecek.")
        return None
    df = pd.read_csv(yol, sep=";", encoding="utf-8-sig")
    gerekli = {"fon_kodu", "kategoriler"}
    eksik = gerekli - set(df.columns)
    if eksik:
        log.warning("fon_kategori_referans.csv icinde eksik kolonlar (%s) - atlaniyor.", eksik)
        return None
    df = df.rename(columns={"kategoriler": "kategori"})
    return df[["fon_kodu", "kategori"]].drop_duplicates(subset="fon_kodu", keep="last")


def main() -> int:
    fon_tipleri = sys.argv[1:] if len(sys.argv) > 1 else ["YAT", "EMK", "BYF"]

    tum_getiriler = []
    tum_kurucular = []
    tum_turler = []

    for tip in fon_tipleri:
        log.info("Cekiliyor: %s", tip)
        try:
            g = getiri_ve_kategori_cek(tip)
            tum_getiriler.append(g)
            log.info("  getiri/kategori: %d fon", len(g))
        except Exception as e:
            log.error("  getiri/kategori cekilemedi (%s): %s", tip, e)

        try:
            k = kurucu_listesi_cek(tip)
            tum_kurucular.append(k)
        except Exception as e:
            log.error("  kurucu listesi cekilemedi (%s): %s", tip, e)

        try:
            t = fon_turu_listesi_cek(tip)
            tum_turler.append(t)
        except Exception as e:
            log.error("  fon turu listesi cekilemedi (%s): %s", tip, e)

    if tum_getiriler:
        getiriler = pd.concat(tum_getiriler, ignore_index=True)

        kategori_referans = fon_kategori_referans_yukle()
        if kategori_referans is not None:
            getiriler = getiriler.merge(
                kategori_referans, left_on="fund_code", right_on="fon_kodu", how="left"
            ).drop(columns=["fon_kodu"], errors="ignore")
            log.info("Ince kategori bilgisi eklendi (%d/%d fon eslesti).",
                      getiriler["kategori"].notna().sum(), len(getiriler))

        bugun = pd.Timestamp.now().strftime("%Y-%m-%d")
        cikti = VERI_KLASORU / f"getiri_kategori_{bugun}.csv"
        getiriler.to_csv(cikti, index=False, encoding="utf-8-sig", sep=";", decimal=",")
        log.info("Kaydedildi: %s (%d satir)", cikti, len(getiriler))

        # Ayrica bir "guncel" kopya da tutalim - dashboard bunu okuyacak
        getiriler.to_parquet(VERI_KLASORU / "guncel_getiri_kategori.parquet", index=False)

    if tum_kurucular:
        kurucular = pd.concat(tum_kurucular, ignore_index=True).drop_duplicates()
        kurucular.to_csv(VERI_KLASORU / "referans_kurucular.csv",
                          index=False, encoding="utf-8-sig", sep=";")

    if tum_turler:
        turler = pd.concat(tum_turler, ignore_index=True).drop_duplicates()
        turler.to_csv(VERI_KLASORU / "referans_fon_turleri.csv",
                       index=False, encoding="utf-8-sig", sep=";")

    log.info("TAMAMLANDI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
