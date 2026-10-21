@echo off
rem Hamta: one-time registration of hamta:// links so the start buttons in the "data and computations" panel can launch
rem update_data.bat, update_data_full.bat and rebuild_all.bat. Writes only under the current Windows user
rem (HKCU\Software\Classes\hamta); no administrator rights. To remove: register_ui_actions.bat /u
cd /d "%~dp0"
if /i "%~1"=="/u" (
  reg delete "HKCU\Software\Classes\hamta" /f >nul 2>&1
  echo hamta:// links removed.
  pause
  exit /b
)
set "ACT=%CD%\tools\ui_action.bat"
reg add "HKCU\Software\Classes\hamta" /ve /d "URL:Hamta actions" /f >nul
reg add "HKCU\Software\Classes\hamta" /v "URL Protocol" /d "" /f >nul
reg add "HKCU\Software\Classes\hamta\shell\open\command" /ve /d "\"%ACT%\" \"%%1\"" /f >nul
if errorlevel 1 (echo Registration failed. & pause & exit /b 1)
echo Registered. The start buttons now launch:
echo   hamta://fetch       = update_data.bat
echo   hamta://fetch-full  = update_data_full.bat
echo   hamta://rebuild     = rebuild_all.bat
echo The browser asks once whether to open the link; allow it.
pause
