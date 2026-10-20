@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Hamta - rebuild calculations
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set PYTHONUTF8=1
echo Hamta: rebuilding all calculations and page data (30-60 minutes)...
python tools/update_pipeline.py rebuild
echo.
echo Done. Reload the page.
pause
