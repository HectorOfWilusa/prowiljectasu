"""
TEFAS fonUnvanTip Filtre Dogrulama Testi
===========================================
tefas_fon_alt_turu.py'nin urettigi sonucta beklenmedik bir sey var: NAU
("Altin" olmasi beklenen bir fon) "Yabanci Fon Sepeti" olarak kaydedildi,
ve toplam fon sayisi (2032) beklenenden (~1043) cok fazla cikti.

Bu script, fonUnvanTip filtresinin GERCEKTEN dogru calisip calismadigini
test eder - ayni "Altin" filtresini birkac farkli sekilde deneyip
sonuclari karsilastirir.

Bu script sadece OKUR, hicbir dosya olusturmaz/degistirmez.

Kullanim:
  python tefas_unvan_filtre_test.py
"""

import sys
import json
from datetime import date

import requests

BASE = "https://www.tefas.gov.tr/api/funds"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/tr/fon-verileri?fundType=YAT&sfonTurKod=105&fonUnvanTip=Alt%C4%B1n",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    ),
}


def istek(govde: dict) -> dict:
    r = requests.post(f"{BASE}/fonGnlBlgSiraliGetir", json=govde, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def baslik(m):
    print("\n" + "=" * 70)
    print(m)
    print("=" * 70)


def main():
    bugun = date.today().strftime("%Y%m%d")

    # TEST 1: fonUnvanTip=Altin filtresiyle (tefas_fon_alt_turu.py'nin kullandigi hal)
    baslik("TEST 1: fonUnvanTip='Altın' ile istek")
    govde1 = {
        "fonTipi": "YAT", "fonKodu": None, "aramaMetni": None, "fonTurKod": None,
        "fonGrubu": None, "sfonTurKod": None, "fonUnvanTip": "Altın",
        "basTarih": bugun, "bitTarih": bugun, "basSira": 1, "bitSira": 100,
        "fonTurAciklama": None, "dil": "TR", "kurucuKod": None,
    }
    data1 = istek(govde1)
    kayitlar1 = data1.get("resultList") or []
    print(f"Donen kayit sayisi: {len(kayitlar1)}")
    print("Ilk 10 fon kodu:", [k.get("fonKodu") for k in kayitlar1[:10]])
    nau_var_mi = any(k.get("fonKodu") == "NAU" for k in kayitlar1)
    print(f"NAU bu listede var mi: {nau_var_mi}")

    # TEST 2: fonUnvanTip='Yabancı Fon Sepeti' ile istek - NAU burada mi cikiyor?
    baslik("TEST 2: fonUnvanTip='Yabancı Fon Sepeti' ile istek")
    govde2 = dict(govde1)
    govde2["fonUnvanTip"] = "Yabancı Fon Sepeti"
    data2 = istek(govde2)
    kayitlar2 = data2.get("resultList") or []
    print(f"Donen kayit sayisi: {len(kayitlar2)}")
    nau_var_mi2 = any(k.get("fonKodu") == "NAU" for k in kayitlar2)
    print(f"NAU bu listede var mi: {nau_var_mi2}")
    if nau_var_mi2:
        nau_kayit = next(k for k in kayitlar2 if k.get("fonKodu") == "NAU")
        print("NAU'nun bu filtredeki tam kaydi:", json.dumps(nau_kayit, ensure_ascii=False, indent=2))

    # TEST 3: fonUnvanTip=None (filtresiz) - NAU'nun "gercek" durumu ne?
    baslik("TEST 3: fonUnvanTip=None (FILTRESIZ) - NAU'yu direkt arayalim")
    govde3 = dict(govde1)
    govde3["fonUnvanTip"] = None
    govde3["fonKodu"] = "NAU"
    govde3["bitSira"] = 5
    data3 = istek(govde3)
    kayitlar3 = data3.get("resultList") or []
    print(f"Donen kayit sayisi: {len(kayitlar3)}")
    if kayitlar3:
        print("NAU'nun TUM alanlari (filtresiz sorguda):")
        for k, v in kayitlar3[0].items():
            print(f"  {k:25s} -> {v!r}")

    # TEST 4: sayfalama sinirini kontrol et - belki basSira/bitSira mantigi yanlis calisiyor
    baslik("TEST 4: Ayni 'Altın' filtresini FARKLI sayfa araliklariyla dene (sayfalama dogru mu?)")
    govde4 = dict(govde1)
    govde4["basSira"] = 1
    govde4["bitSira"] = 5
    data4a = istek(govde4)
    kayitlar4a = data4a.get("resultList") or []
    print("Sayfa 1-5 (Altın filtresi):", [k.get("fonKodu") for k in kayitlar4a])

    govde4["basSira"] = 101
    govde4["bitSira"] = 105
    data4b = istek(govde4)
    kayitlar4b = data4b.get("resultList") or []
    print("Sayfa 101-105 (Altın filtresi):", [k.get("fonKodu") for k in kayitlar4b])
    print("(Eger bu ikinci sayfa da doluysa, filtre calismiyor ve TUM fonlari donduruyor demektir - filtre gormezden geliniyor olabilir)")


if __name__ == "__main__":
    main()
