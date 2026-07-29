@echo off
REM ====================================================================
REM TEFAS gunluk veri cekme - Windows Gorev Zamanlayici baslatici
REM Bu dosyayi scriptlerle ayni klasore koy: C:\TEFAS\
REM ====================================================================

cd /d "%~dp0"

REM Python yolu otomatik bulunamazsa asagidaki satiri kendi yolunla degistir
REM ornek: set PY="C:\Users\Alptug\AppData\Local\Programs\Python\Python312\python.exe"
set PY=python

set TEFAS_PANO_SIFRE=Claude.2026.Tefas
%PY% tefas_ana.py

if errorlevel 1 (
    echo [HATA] Veri cekilemedi. log.txt dosyasina bak.
    exit /b 1
)

echo [OK] Tamamlandi.
exit /b 0
