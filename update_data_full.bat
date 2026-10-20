@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Hamta - full data update
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set PYTHONUTF8=1
echo Hamta: full fetch (also all corporate actions, Farabi dividends, index-fund NAVs). Slow.
python tools/update_pipeline.py fetch --full
echo.
echo Done. Reload the page. Then run rebuild_all.bat to recompute.
pause
