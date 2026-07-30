"""
TEFAS Issue -> Islem Ekleme Scripti (GitHub Actions icin)
=============================================================
Bu script, dashboard'dan acilan bir GitHub Issue'nun icerigini okuyup
islemler.csv'ye yeni bir satir olarak ekler, sonra tefas_islem_isle.py'yi
calistirarak portfoyu gunceller.

BU SCRIPT SADECE GITHUB ACTIONS ICINDE CALISTIRILMAK UZERE TASARLANDI -
Issue baslik/govdesini ortam degiskenlerinden (environment variables) okur:
  ISSUE_TITLE : Issue basligi
  ISSUE_BODY  : Issue govdesi (JSON formatinda islem detaylari beklenir)

Beklenen Issue govdesi formati (dashboard formu bunu otomatik uretir):
  {
    "fon_kodu": "NAU",
    "fon_adi": "NEO PORTFOY ALTIN FONU",
    "kanal": "YKB",
    "islem_tipi": "ALIM",
    "tarih": "2026-07-30",
    "pay_sayisi": 500,
    "fiyat": 1.45
  }

Basarili olursa:
  - islemler.csv'ye yeni satir eklenir
  - tefas_islem_isle.py calistirilir (portfoyu gunceller)
  - 0 (basari) ile cikilir, GITHUB_STEP_SUMMARY'ye ozet yazilir

Basarisiz olursa (JSON parse hatasi, eksik alan, gecersiz deger):
  - 1 ile cikilir, hata mesaji stderr'e yazilir - workflow bu hatayi
    Issue'ya yorum olarak ekleyebilir
"""

import os
import sys
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd

BU_KLASOR = Path(__file__).resolve().parent
ISLEMLER_DOSYA = BU_KLASOR / "islemler.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("issue-to-islem")

GEREKLI_ALANLAR = {"fon_kodu", "fon_adi", "kanal", "islem_tipi", "tarih", "pay_sayisi", "fiyat"}


def issue_govdesini_parse_et(govde: str) -> dict:
    """Issue govdesinden JSON blogunu cikarir ve dogrular.

    Govde tamamen JSON olabilecegi gibi, JSON bir kod blogu icinde de
    olabilir (```json ... ``` seklinde) - dashboard formu hangi sekilde
    urettiyse ikisini de destekler.
    """
    govde = govde.strip()

    # Kod blogu icindeyse (```json ... ``` veya ``` ... ```) temizle
    if govde.startswith("```"):
        satirlar = govde.split("\n")
        # ilk ve son satiri (``` isaretlerini) at
        govde = "\n".join(satirlar[1:-1]) if len(satirlar) > 2 else govde

    try:
        veri = json.loads(govde)
    except json.JSONDecodeError as e:
        raise ValueError(f"Issue govdesi gecerli JSON degil: {e}\nGovde:\n{govde}")

    eksik = GEREKLI_ALANLAR - set(veri.keys())
    if eksik:
        raise ValueError(f"Issue govdesinde eksik alanlar: {eksik}")

    islem_tipi = str(veri["islem_tipi"]).upper().strip()
    if islem_tipi not in {"ALIM", "SATIM"}:
        raise ValueError(f"Gecersiz islem_tipi: {veri['islem_tipi']} (ALIM veya SATIM olmali)")
    veri["islem_tipi"] = islem_tipi

    try:
        pd.to_datetime(veri["tarih"], dayfirst=True)
    except Exception as e:
        raise ValueError(f"Tarih parse edilemedi ({veri['tarih']}): {e}")

    try:
        veri["pay_sayisi"] = float(veri["pay_sayisi"])
        veri["fiyat"] = float(veri["fiyat"])
    except (TypeError, ValueError) as e:
        raise ValueError(f"pay_sayisi veya fiyat sayiya cevrilemedi: {e}")

    if veri["pay_sayisi"] <= 0 or veri["fiyat"] <= 0:
        raise ValueError("pay_sayisi ve fiyat pozitif olmali.")

    veri["fon_kodu"] = str(veri["fon_kodu"]).strip().upper()
    veri["fon_adi"] = str(veri["fon_adi"]).strip()
    veri["kanal"] = str(veri["kanal"]).strip().upper()

    return veri


def islemi_ekle(veri: dict) -> None:
    """Yeni islemi islemler.csv'ye tek satir olarak ekler."""
    yeni_satir = pd.DataFrame([{
        "fon_kodu": veri["fon_kodu"],
        "fon_adi": veri["fon_adi"],
        "kanal": veri["kanal"],
        "islem_tipi": veri["islem_tipi"],
        "tarih": veri["tarih"],
        "pay_sayisi": veri["pay_sayisi"],
        "fiyat": veri["fiyat"],
    }])

    if ISLEMLER_DOSYA.exists():
        mevcut = pd.read_csv(ISLEMLER_DOSYA, sep=";", decimal=",", encoding="utf-8-sig")
        birlesik = pd.concat([mevcut, yeni_satir], ignore_index=True)
    else:
        birlesik = yeni_satir

    birlesik.to_csv(ISLEMLER_DOSYA, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    log.info("islemler.csv guncellendi: %s %s %s %s pay @ %s (kanal: %s)",
              veri["fon_kodu"], veri["islem_tipi"], veri["tarih"],
              veri["pay_sayisi"], veri["fiyat"], veri["kanal"])


def portfoyu_guncelle() -> bool:
    """tefas_islem_isle.py'yi calistirir (FIFO hesabini yeniler)."""
    sonuc = subprocess.run(
        [sys.executable, str(BU_KLASOR / "tefas_islem_isle.py")],
        cwd=str(BU_KLASOR),
    )
    return sonuc.returncode == 0


def ozet_yaz(basarili: bool, veri: dict | None, hata: str | None) -> None:
    """GitHub Actions'in adim ozetine (step summary) yazi ekler - Actions
    arayuzunde gorunur, Issue'ya da yorum olarak eklenebilir."""
    ozet_dosya = os.environ.get("GITHUB_STEP_SUMMARY")
    if not ozet_dosya:
        return
    with open(ozet_dosya, "a", encoding="utf-8") as f:
        if basarili:
            f.write(f"## Islem basariyla eklendi\n\n")
            f.write(f"- **Fon:** {veri['fon_kodu']} ({veri['fon_adi']})\n")
            f.write(f"- **Kanal:** {veri['kanal']}\n")
            f.write(f"- **Islem:** {veri['islem_tipi']}\n")
            f.write(f"- **Tarih:** {veri['tarih']}\n")
            f.write(f"- **Pay:** {veri['pay_sayisi']}\n")
            f.write(f"- **Fiyat:** {veri['fiyat']}\n")
        else:
            f.write(f"## Islem eklenemedi\n\n")
            f.write(f"**Hata:** {hata}\n")


def main() -> int:
    baslik = os.environ.get("ISSUE_TITLE", "")
    govde = os.environ.get("ISSUE_BODY", "")

    log.info("Issue basligi: %s", baslik)

    try:
        veri = issue_govdesini_parse_et(govde)
    except ValueError as e:
        log.error("Issue govdesi islenemedi: %s", e)
        ozet_yaz(False, None, str(e))
        # Hata mesajini stdout'a da yaz - workflow bunu Issue yorumuna ekleyebilir
        print(f"::error::{e}")
        return 1

    islemi_ekle(veri)

    if not portfoyu_guncelle():
        log.error("tefas_islem_isle.py basarisiz oldu.")
        ozet_yaz(False, veri, "islem islemler.csv'ye eklendi ama tefas_islem_isle.py calistirilirken hata olustu.")
        return 1

    ozet_yaz(True, veri, None)
    log.info("TAMAMLANDI.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
