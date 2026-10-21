@echo off
setlocal EnableDelayedExpansion
rem Hamta: handler for the start buttons of the "data and computations" panel (links hamta://fetch, hamta://fetch-full, hamta://rebuild).
rem One-time registration: register_ui_actions.bat in the repository root. Only these three actions are accepted; any other link is refused.
rem The link is read only through delayed expansion (!U!) so characters such as & in a crafted link never become commands.
rem Test without running a job: set HAMTA_DRYRUN=1 and call this file with a link; it prints the action it would run.
cd /d "%~dp0.."
set "U=%~1"
set "A="
for %%K in (rebuild fetch-full fetch) do (
  if /i "!U!"=="hamta://%%K" if not defined A set "A=%%K"
  if /i "!U!"=="hamta://%%K/" if not defined A set "A=%%K"
)
if defined HAMTA_DRYRUN (echo action=!A! & exit /b)
if "!A!"=="rebuild" (call "%CD%\rebuild_all.bat" & exit /b)
if "!A!"=="fetch-full" (call "%CD%\update_data_full.bat" & exit /b)
if "!A!"=="fetch" (call "%CD%\update_data.bat" & exit /b)
echo Unknown request. Only hamta://fetch, hamta://fetch-full and hamta://rebuild are accepted.
pause
