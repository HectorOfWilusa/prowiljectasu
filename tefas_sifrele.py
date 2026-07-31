"""
TEFAS Panosu - Dosya Sifreleme Scripti
========================================
tefas_ana.py calistiktan sonra uretilen CSV dosyalarini AES-256-GCM ile
sifreler. Sifreleme yontemi TARAYICININ kendi Web Crypto API'siyle
birebir uyumludur - dashboard tarafinda hicbir ek kutuphane gerekmez.

Neden bu yontem:
  - PBKDF2 (100.000 iterasyon) ile sifreden guclu bir anahtar turetilir
  - AES-256-GCM ile veri sifrelenir (kimlik dogrulamali - yanlis sifreyle
    KESINLIKLE cozulemez, "yaklasik dogru" diye bir sey yoktur)
  - Sifre hicbir yere (GitHub'a, sunucuya) gonderilmez, sadece senin
    tarayicinda kalir

Sifre, ortam degiskeninden (environment variable) okunur:
  TEFAS_PANO_SIFRE
Bu sayede sifre kod icine yazilmaz, GitHub Actions'ta "secret" olarak
saklanir. Yerel bilgisayarinda calistirirken de ayni degiskeni tanimlaman
gerekir (asagida "Yerel kullanim" bolumune bak).

Sifrelenen dosyalar:
  - getiri_kategori_YYYY-MM-DD.csv  (en guncel tarihli olan)
  - guncel_portfoy_degerleme.csv
  - portfoy_kategori_dagilimi.csv

Cikti: BU_KLASOR/sifreli/ altina, sabit isimlerle:
  - fonlar.enc.json
  - portfoy.enc.json
  - kategori.enc.json
  - meta.json  (sifreleme tarihi, kolon listesi - sifrelenmez, ic gorunmez veri yok)

Yerel kullanim (Windows cmd):
  set TEFAS_PANO_SIFRE=senin-sifren
  python tefas_sifrele.py

Kullanim:
  python tefas_sifrele.py
"""

import os
import sys
import json
import logging
import base64
from pathlib import Path
from datetime import datetime

import pandas as pd
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERI_KLASORU = Path.home() / "TEFAS_VERI"
BU_KLASOR = Path(__file__).resolve().parent
SIFRELI_KLASOR = BU_KLASOR / "sifreli"
SIFRELI_KLASOR.mkdir(exist_ok=True)

PBKDF2_ITERASYON = 100_000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(VERI_KLASORU / "log.txt", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("tefas-sifrele")


def sifreyi_al() -> str:
    sifre = os.environ.get("TEFAS_PANO_SIFRE")
    if not sifre:
        raise RuntimeError(
            "TEFAS_PANO_SIFRE ortam degiskeni bulunamadi.\n"
            "Windows cmd'de calistirmadan once su komutu yaz:\n"
            "  set TEFAS_PANO_SIFRE=senin-sifren\n"
            "GitHub Actions'ta bu, repo Secrets bolumunden ayarlanir."
        )
    return sifre


def sifrele(veri_bytes: bytes, sifre: str) -> dict:
    salt = os.urandom(16)
    iv = os.urandom(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERASYON)
    anahtar = kdf.derive(sifre.encode("utf-8"))
    aesgcm = AESGCM(anahtar)
    sifreli = aesgcm.encrypt(iv, veri_bytes, None)
    return {
        "salt": base64.b64encode(salt).decode(),
        "iv": base64.b64encode(iv).decode(),
        "veri": base64.b64encode(sifreli).decode(),
        "iterasyon": PBKDF2_ITERASYON,
    }


def en_guncel_dosyayi_bul(desen: str) -> Path | None:
    """VERI_KLASORU icinde 'desen*' ile eslesen en son tarihli dosyayi bulur."""
    adaylar = sorted(VERI_KLASORU.glob(desen))
    return adaylar[-1] if adaylar else None


def df_sifrele(df: pd.DataFrame, sifre: str, cikti_adi: str, kaynak_adi: str) -> bool:
    """Bir DataFrame'i JSON'a cevirip sifreler, sifreli/ altina yazar.
    csv_yukle_ve_sifrele ve parquet_yukle_ve_sifrele tarafindan ortak
    kullanilan cekirdek adim - dosya format farki burada onemli degil,
    DataFrame elde edildikten sonraki islem her zaman aynidir."""
    kayitlar = df.to_dict(orient="records")

    # ONEMLI: pandas'ta bos/eksik sayisal hucreler NaN olarak durur, ve
    # float tipli sutunlarda DataFrame.where(...) ile None atamaya calismak
    # ISE YARAMAZ - pandas None'u otomatik olarak tekrar NaN'a cevirir
    # (float sutunlarda None kavramsal olarak yoktur). Bu yuzden temizligi
    # DataFrame uzerinde degil, to_dict() ile Python native dict'e
    # gectikten SONRA yapiyoruz - orada artik gercek None atanabiliyor.
    #
    # Python'un json.dumps() fonksiyonu NaN'i sessizce yazar ama bu GECERSIZ
    # JSON'dur (standart disi) - tarayicinin JSON.parse()'i bunu reddeder.
    def deger_temizle(v):
        # NaN (float ama kendine esit degil) -> None
        if isinstance(v, float) and v != v:
            return None
        # pandas/numpy Timestamp ve benzeri tarih tipleri JSON'a dogrudan
        # yazilamaz - ISO string'e cevrilir (dashboard tarafinda gerekirse
        # kolayca tekrar Date'e parse edilebilir).
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v

    def nan_temizle(satir: dict) -> dict:
        return {k: deger_temizle(v) for k, v in satir.items()}

    kayitlar = [nan_temizle(satir) for satir in kayitlar]

    # allow_nan=False: eger yukaridaki temizlik bir sekilde eksik kalirsa,
    # sessizce gecersiz JSON uretmek yerine burada acikca hata versin.
    json_metin = json.dumps(kayitlar, ensure_ascii=False, allow_nan=False)

    paket = sifrele(json_metin.encode("utf-8"), sifre)
    hedef = SIFRELI_KLASOR / cikti_adi
    with open(hedef, "w", encoding="utf-8") as f:
        json.dump(paket, f)

    log.info("Sifrelendi: %s -> %s (%d satir)", kaynak_adi, hedef.name, len(df))
    return True


def csv_yukle_ve_sifrele(dosya_yolu: Path, sifre: str, cikti_adi: str) -> bool:
    if dosya_yolu is None or not dosya_yolu.exists():
        log.warning("Bulunamadi, atlaniyor: %s", cikti_adi)
        return False

    df = pd.read_csv(dosya_yolu, sep=";", decimal=",", encoding="utf-8-sig")

    # JSON'a cevirirken virgullu-TR sayi formatindan kacinmak icin
    # standart (nokta ondalikli) JSON kullaniyoruz - dashboard tarafinda
    # ekstra parse karmasasi olmasin diye.
    return df_sifrele(df, sifre, cikti_adi, dosya_yolu.name)


def parquet_yukle_ve_sifrele(dosya_yolu: Path, sifre: str, cikti_adi: str) -> bool:
    if dosya_yolu is None or not dosya_yolu.exists():
        log.warning("Bulunamadi, atlaniyor: %s", cikti_adi)
        return False

    df = pd.read_parquet(dosya_yolu)
    return df_sifrele(df, sifre, cikti_adi, dosya_yolu.name)


def main() -> int:
    sifre = sifreyi_al()

    sonuclar = {}

    fonlar_dosya = en_guncel_dosyayi_bul("getiri_kategori_*.csv")
    sonuclar["fonlar"] = csv_yukle_ve_sifrele(fonlar_dosya, sifre, "fonlar.enc.json")

    portfoy_dosya = VERI_KLASORU / "guncel_portfoy_degerleme.csv"
    sonuclar["portfoy"] = csv_yukle_ve_sifrele(
        portfoy_dosya if portfoy_dosya.exists() else None, sifre, "portfoy.enc.json"
    )

    kategori_dosya = VERI_KLASORU / "portfoy_kategori_dagilimi.csv"
    sonuclar["kategori"] = csv_yukle_ve_sifrele(
        kategori_dosya if kategori_dosya.exists() else None, sifre, "kategori.enc.json"
    )

    # islemler.csv repo kokunde (BU_KLASOR) durur - tefas_issue_isle.py
    # tarafindan GitHub Issues akisiyla guncellenir. Public repoda
    # sifresiz durmasin diye digerleriyle ayni sekilde sifrelenir.
    islemler_dosya = BU_KLASOR / "islemler.csv"
    sonuclar["islemler"] = csv_yukle_ve_sifrele(
        islemler_dosya if islemler_dosya.exists() else None, sifre, "islemler.enc.json"
    )

    # NOT: Kayan pencere getirileri (1G/1H/2H/3H/2A) ayrica sifrelenmiyor -
    # tefas_getiri_kategori.py ve tefas_portfoy_degerle.py bu getirileri
    # zaten getiri_kategori_*.csv ve guncel_portfoy_degerleme.csv icine
    # birlestiriyor, yani fonlar.enc.json ve portfoy.enc.json ile birlikte
    # otomatik olarak dashboard'a ulasiyorlar.

    # Aktif yonetim skoru (1H/1A/2A/3A + percentile'lar) - tefas_aktiflik_skoru.py'nin
    # ciktisi, ayri bir dosya oldugu icin (fonlar/portfoy'a merge edilmedi,
    # cunku sadece YAT fonlarini kapsiyor ve kendi basina bagimsiz bir
    # gorunumu var) burada ayrica sifrelenir.
    aktiflik_dosya = VERI_KLASORU / "aktiflik_skoru.parquet"
    sonuclar["aktiflik"] = parquet_yukle_ve_sifrele(
        aktiflik_dosya if aktiflik_dosya.exists() else None, sifre, "aktiflik.enc.json"
    )

    meta = {
        "son_guncelleme": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sifrelenen_dosyalar": {k: v for k, v in sonuclar.items()},
    }
    with open(SIFRELI_KLASOR / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    basarili_sayisi = sum(1 for v in sonuclar.values() if v)
    log.info("-" * 60)
    log.info("TAMAMLANDI: %d/%d dosya sifrelendi.", basarili_sayisi, len(sonuclar))
    log.info("Sifreli dosyalar: %s", SIFRELI_KLASOR)
    return 0 if basarili_sayisi > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
