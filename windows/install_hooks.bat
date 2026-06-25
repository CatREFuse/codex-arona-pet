@echo off
setlocal
cd /d "%~dp0"
set "OPEN_PLANA_ROOT=%~dp0.."
call "%~dp0run_open_plana.bat" --install-hooks
