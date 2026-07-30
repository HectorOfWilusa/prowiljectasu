"""
TEFAS API - Ham Alan Kontrolu
================================
tefas_getiri_kategori.py'nin kullandigi ayni API'yi cagirir, ama kolon
esleme yapmadan ONCE gelen JSON'daki TUM alan adlarini ve ilk birkac
kaydin tum icerigini oldugu gibi ekrana basar.

Amac: "Fon Unvan Turu" (Altin, Doviz, Hisse gibi alt tur) bilgisinin
API cevabinda GERCEKTEN var olup olmadigini, varsa hangi alan adiyla
geldigini gormek. tefas_getiri_kategori.py'deki KOLON_ESLEME sozlugu
sadece bilinen/kullanilan alanlari CSV'ye yaziyor - baska alanlar
gelse bile sessizce atiliyor. Bu script hicbir seyi atmadan hepsini gosterir.

Bu script sadece OKUR, hicbir dosya olusturmaz/degistirmez.

Kullanim:
  python tefas_api_alan_kontrol.py            -> YAT fon tipi ile dener
  python tefas_api_alan_kontrol.py EMK        -> baska fon tipiyle dener
"""

import sys
import json

import requests

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


def istek_at(fon_tipi: str) -> dict:
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
    r = requests.post(f"{BASE}/fonGetiriBazliBilgiGetir", json=gövde, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> int:
    fon_tipi = sys.argv[1] if len(sys.argv) > 1 else "YAT"
    print(f"API'ye istek atiliyor (fonTipi={fon_tipi})...\n")

    data = istek_at(fon_tipi)
    kayitlar = data.get("resultList") or []

    if not kayitlar:
        print("HATA: resultList bos geldi. API cevabinin tamamini asagida goruyorsun:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
        return 1

    print(f"Toplam kayit sayisi: {len(kayitlar)}\n")
    print("=" * 70)
    print("TUM ALAN ADLARI (ilk kayittan):")
    print("=" * 70)
    ilk = kayitlar[0]
    for alan_adi, deger in ilk.items():
        print(f"  {alan_adi:25s} -> {deger!r}")

    # Ozellikle "unvan", "tur", "kod" gecen alanlari ayrica vurgula -
    # aradigimiz "Fon Unvan Turu" muhtemelen bunlarin arasinda.
    print("\n" + "=" * 70)
    print("ISIM ICINDE 'unvan' / 'tur' / 'kod' GECEN ALANLAR (adaylar):")
    print("=" * 70)
    for alan_adi in ilk.keys():
        kucuk = alan_adi.lower()
        if "unvan" in kucuk or "tur" in kucuk or "kod" in kucuk:
            print(f"  {alan_adi:25s} -> {ilk[alan_adi]!r}")

    # NAU kodlu fonu ozel olarak arayip tum alanlarini basalim (varsa)
    print("\n" + "=" * 70)
    print("NAU KODLU FON ARANIYOR (varsa tum alanlariyla):")
    print("=" * 70)
    nau = next((k for k in kayitlar if str(k.get("fonKodu", "")).upper() == "NAU"), None)
    if nau:
        for alan_adi, deger in nau.items():
            print(f"  {alan_adi:25s} -> {deger!r}")
    else:
        print("  Bu fon tipinde NAU bulunamadi (baska fonTipi ile deneyebilirsin, orn: EMK).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
