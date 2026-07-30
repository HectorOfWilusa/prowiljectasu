"""
TEFAS Fon Alt Turu (Unvan Turu) Cekme Scripti
=================================================
TEFAS'in normal fiyat/getiri API'leri (fonGnlBlgSiraliGetir,
fonGetiriBazliBilgiGetir) hicbir zaman "bu fon Altin'dir" gibi bir
alt-tur alani DONMEZ - bu bilgi sadece SORGU FILTRESI olarak var
(sfonTurKod), donen satirlarin icinde degil.

Bu yuzden alt-turu ogrenmenin tek yolu: her alt-tur kodu icin AYRI
AYRI istek atip, o filtrede hangi fon kodlarinin dondugunu not etmek.

Bu script:
  1) fonTurGetir'den TUM sfonTuru kodlarini ve aciklamalarini ceker
     (Altin, Gumus, Doviz, Hisse Senedi Semsiye Fonu vs. - kac tane
     varsa hepsini, YAT/EMK/BYF ayri ayri da denenebilir)
  2) Her kod icin fonGnlBlgSiraliGetir'i o sfonTurKod filtresiyle
     cagirir, sayfalayarak (25'er 25'er) TUM fonlari toplar
  3) Sonucta fon_kodu -> alt_tur eslemesini iceren bir CSV/parquet
     dosyasi uretir: TEFAS_VERI/fon_alt_turu.csv

Bu tablo sik degismez (bir fonun alt turu neredeyse hic degismez),
bu yuzden GUNLUK degil, AYDA BIR ya da ELLE calistirmak yeterlidir -
tefas_ana.py'nin gunluk akisina DAHIL EDILMEMISTIR, bilerek ayri
tutulmustur.

Kurulum:
  pip install requests pandas

Kullanim:
  python tefas_fon_alt_turu.py            -> YAT icin tum alt turleri ceker
  python tefas_fon_alt_turu.py EMK         -> baska fon tipiyle
  python tefas_fon_alt_turu.py YAT EMK BYF -> birden fazla fon tipi birlikte
"""

import sys
import time
import logging
from pathlib import Path
from datetime import date

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
log = logging.getLogger("tefas-alt-turu")

BASE = "https://www.tefas.gov.tr/api/funds"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/tr/fon-verileri?fundType=YAT",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
}

SAYFA_BOYU = 100          # bir istekte kac fon istenecek (ust sinir denenmedi, guvenli deger)
ISTEKLER_ARASI_BEKLEME = 11.0  # saniye - TEFAS dakikada ~6 istek kabul ediyor (429 hatalari gozlendi),
                                # 11 sn araligi dakikada ~5.4 istege denk gelir, guvenli pay birakir


def istek_at(endpoint: str, govde: dict, deneme: int = 3) -> dict:
    son_hata = None
    for i in range(deneme):
        try:
            r = requests.post(f"{BASE}/{endpoint}", json=govde, headers=HEADERS, timeout=30)
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


def alt_tur_kodlarini_getir() -> pd.DataFrame:
    """fonTurGetir'den tum sfonTuru kodlarini ve aciklamalarini ceker.

    NOT: Bu sadece 10 adet UST SEVIYE semsiye turunu verir (Borclanma
    Araclari Semsiye Fonu gibi) - tefas_getiri_kategori.py'nin zaten
    verdigi "semsiye_turu" ile ayni seviye. Kullanicinin istedigi daha
    INCE alt-tur (Altin, Gumus gibi) bu listede DEGIL, ayri bir
    endpoint olan fonUnvanGetir'de.
    """
    data = istek_at("fonTurGetir", {"dil": "TR", "flag": 1})
    kayitlar = data.get("resultList") or data.get("data") or []
    df = pd.DataFrame(kayitlar)
    return df


def unvan_tiplerini_getir(fon_tipi: str) -> list[str]:
    """fonUnvanGetir'den ince alt-tur listesini ceker (Altin, Gumus, vs.)."""
    data = istek_at("fonUnvanGetir", {"dil": "TR", "tur": fon_tipi})
    kayitlar = data.get("resultList") or data.get("data") or []
    return [k.get("tanim") for k in kayitlar if k.get("tanim")]


def fonlari_getir_bir_unvan_tipi_icin(fon_tipi: str, unvan_tipi: str, bugun: str) -> list[str]:
    """Verilen fonUnvanTip filtresiyle TUM fon kodlarini sayfalayarak toplar."""
    fon_kodlari = []
    bas_sira = 1
    while True:
        govde = {
            "fonTipi": fon_tipi,
            "fonKodu": None,
            "aramaMetni": None,
            "fonTurKod": None,
            "fonGrubu": None,
            "sfonTurKod": None,
            "fonUnvanTip": unvan_tipi,
            "basTarih": bugun,
            "bitTarih": bugun,
            "basSira": bas_sira,
            "bitSira": bas_sira + SAYFA_BOYU - 1,
            "fonTurAciklama": None,
            "dil": "TR",
            "kurucuKod": None,
        }
        data = istek_at("fonGnlBlgSiraliGetir", govde)
        kayitlar = data.get("resultList") or data.get("data") or []
        if not kayitlar:
            break
        fon_kodlari.extend(k.get("fonKodu") for k in kayitlar if k.get("fonKodu"))
        if len(kayitlar) < SAYFA_BOYU:
            break
        bas_sira += SAYFA_BOYU
        time.sleep(ISTEKLER_ARASI_BEKLEME)
    return fon_kodlari



def main() -> int:
    fon_tipleri = sys.argv[1:] if len(sys.argv) > 1 else ["YAT"]
    bugun = date.today().strftime("%Y%m%d")

    tum_eslemeler = []

    for fon_tipi in fon_tipleri:
        log.info("=" * 60)
        log.info("FON TIPI: %s", fon_tipi)
        log.info("=" * 60)

        log.info("Unvan tipi (ince alt-tur) listesi cekiliyor (fonUnvanGetir)...")
        try:
            unvan_tipleri = unvan_tiplerini_getir(fon_tipi)
        except Exception as e:
            log.error("fonUnvanGetir basarisiz (%s): %s", fon_tipi, e)
            continue
        log.info("Bulunan unvan tipleri (%d adet): %s", len(unvan_tipleri), ", ".join(unvan_tipleri))
        time.sleep(ISTEKLER_ARASI_BEKLEME)

        for unvan_tipi in unvan_tipleri:
            log.info("Cekiliyor: fonUnvanTip=%s...", unvan_tipi)
            try:
                fon_kodlari = fonlari_getir_bir_unvan_tipi_icin(fon_tipi, unvan_tipi, bugun)
            except Exception as e:
                log.error("  HATA (fonUnvanTip=%s): %s", unvan_tipi, e)
                continue
            log.info("  -> %d fon bulundu", len(fon_kodlari))
            for fk in fon_kodlari:
                tum_eslemeler.append({
                    "fon_kodu": fk,
                    "alt_tur": unvan_tipi,
                    "fon_tipi": fon_tipi,
                })
            time.sleep(ISTEKLER_ARASI_BEKLEME)

    if not tum_eslemeler:
        log.error("Hicbir esleme toplanamadi.")
        return 1

    df = pd.DataFrame(tum_eslemeler).drop_duplicates(subset=["fon_kodu", "fon_tipi"], keep="last")

    cikti_csv = VERI_KLASORU / "fon_alt_turu.csv"
    df.to_csv(cikti_csv, index=False, encoding="utf-8-sig", sep=";")
    df.to_parquet(VERI_KLASORU / "fon_alt_turu.parquet", index=False)

    log.info("-" * 60)
    log.info("TAMAMLANDI: %d fon icin alt tur bilgisi kaydedildi.", len(df))
    log.info("Dosya: %s", cikti_csv)
    log.info("Ornek satirlar:")
    for _, satir in df.head(10).iterrows():
        log.info("  %s -> %s", satir["fon_kodu"], satir["alt_tur"])

    nau = df[df["fon_kodu"] == "NAU"]
    if not nau.empty:
        log.info("NAU kontrolu: %s", nau.iloc[0]["alt_tur"])
    else:
        log.info("NAU bu fon tipinde bulunamadi.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
