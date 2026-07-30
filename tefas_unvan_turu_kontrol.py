"""
TEFAS API - Fon Unvan Turu / Alt Tur Kontrolu
================================================
Bulunan gercek endpoint: fonGnlBlgSiraliGetir (fiyat endpoint'i ile AYNI,
ama farkli govde ile cagriliyor - sfonTurKod filtresiyle).

Bu script sirasiyla:
  1) fonTurGetir cagirir -> sfonTurKod -> alt tur ismi eslemesini gosterir
     (orn: 105 -> "Altin" gibi)
  2) fonUnvanGetir cagirir -> unvan tipi listesini gosterir
  3) fonGnlBlgSiraliGetir'i sfonTurKod=105 ("Altin") FILTRESIYLE cagirir
     ve donen kayitlarin TUM alanlarini gosterir - boylece her fon
     satirinda alt-tur bilgisinin GERCEKTEN nasil goründügünü goruruz.
  4) Aynı endpoint'i HICBIR FILTRE OLMADAN (sfonTurKod: null) cagirir -
     boylece normal gunluk cekimde (tefas_gunluk.py'nin kullandigi sekilde)
     bu alanin gelip gelmedigini kontrol eder.

Bu script sadece OKUR, hicbir dosya olusturmaz/degistirmez.

Kullanim:
  python tefas_unvan_turu_kontrol.py
"""

import sys
import json

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


def istek(endpoint: str, govde: dict) -> dict:
    r = requests.post(f"{BASE}/{endpoint}", json=govde, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def baslik(metin: str) -> None:
    print("\n" + "=" * 70)
    print(metin)
    print("=" * 70)


def main() -> int:
    # 1) fonTurGetir -> sfonTurKod -> isim eslemesi
    baslik("1) fonTurGetir - sfonTurKod -> alt tur ismi eslemesi")
    try:
        data = istek("fonTurGetir", {"dil": "TR", "flag": 1})
        kayitlar = data.get("resultList") or data.get("data") or []
        if isinstance(kayitlar, list) and kayitlar:
            print(f"Toplam {len(kayitlar)} kayit. Ilk kaydin alanlari:")
            for k, v in kayitlar[0].items():
                print(f"  {k:20s} -> {v!r}")
            print("\n105 kodlu olan var mi (Altin bekleniyor)?")
            for k in kayitlar:
                if str(k.get("fonTurKod") or k.get("sfonTurKod") or "") == "105":
                    print(f"  BULUNDU: {k}")
        else:
            print("Beklenmeyen format, ham cevap:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    except Exception as e:
        print(f"HATA: {e}")

    # 2) fonUnvanGetir
    baslik("2) fonUnvanGetir - unvan tipi listesi")
    try:
        data = istek("fonUnvanGetir", {"dil": "TR", "tur": "YAT"})
        kayitlar = data.get("resultList") or data.get("data") or []
        if isinstance(kayitlar, list) and kayitlar:
            print(f"Toplam {len(kayitlar)} kayit. Ilk 5 kayit:")
            for k in kayitlar[:5]:
                print(f"  {k}")
        else:
            print("Beklenmeyen format, ham cevap:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    except Exception as e:
        print(f"HATA: {e}")

    # 3) fonGnlBlgSiraliGetir - sfonTurKod=105 FILTRESIYLE (Altin)
    baslik("3) fonGnlBlgSiraliGetir - sfonTurKod=105 (Altin) FILTRESIYLE")
    bugun = "20260730"
    govde_filtreli = {
        "fonTipi": "YAT",
        "fonKodu": None,
        "aramaMetni": None,
        "fonTurKod": None,
        "fonGrubu": None,
        "sfonTurKod": "105",
        "basTarih": bugun,
        "bitTarih": bugun,
        "basSira": 1,
        "bitSira": 25,
        "fonTurAciklama": "Altın",
        "dil": "TR",
        "kurucuKod": None,
    }
    try:
        data = istek("fonGnlBlgSiraliGetir", govde_filtreli)
        kayitlar = data.get("resultList") or data.get("data") or []
        if isinstance(kayitlar, list) and kayitlar:
            print(f"Toplam {len(kayitlar)} kayit. Ilk kaydin TUM alanlari:")
            for k, v in kayitlar[0].items():
                print(f"  {k:25s} -> {v!r}")
        else:
            print("Bos veya beklenmeyen format, ham cevap:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
    except Exception as e:
        print(f"HATA: {e}")

    # 4) Ayni endpoint - FILTRESIZ (gunluk cekimde kullanilan hal)
    baslik("4) fonGnlBlgSiraliGetir - FILTRESIZ (gunluk cekimdeki gibi)")
    govde_filtresiz = dict(govde_filtreli)
    govde_filtresiz["sfonTurKod"] = None
    govde_filtresiz["fonTurAciklama"] = None
    govde_filtresiz["bitSira"] = 5  # sadece birkac kayda bakmak yeterli
    try:
        data = istek("fonGnlBlgSiraliGetir", govde_filtresiz)
        kayitlar = data.get("resultList") or data.get("data") or []
        if isinstance(kayitlar, list) and kayitlar:
            print(f"Toplam {len(kayitlar)} kayit. Ilk kaydin TUM alanlari:")
            for k, v in kayitlar[0].items():
                print(f"  {k:25s} -> {v!r}")
            print("\nBu alanlarin arasinda alt-tur/unvan-tipi bilgisi var mi kontrol et.")
        else:
            print("Bos veya beklenmeyen format, ham cevap:")
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
    except Exception as e:
        print(f"HATA: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
