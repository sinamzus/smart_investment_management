@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Hamta - data update
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set PYTHONUTF8=1
echo Hamta: fetching data (new symbols, daily prices, official indices, corporate actions of changed symbols)...
python tools/update_pipeline.py fetch
echo.
echo Done. Reload the page. Then run rebuild_all.bat to recompute.
pause
