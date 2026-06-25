@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "OPEN_PLANA_ROOT=%~dp0.."
if not defined PYTHONDONTWRITEBYTECODE set "PYTHONDONTWRITEBYTECODE=1"
if defined OPEN_PLANA_PYTHON (
  if exist "%OPEN_PLANA_PYTHON%" (
    "%OPEN_PLANA_PYTHON%" "%~dp0open_plana.py" %*
    exit /b !errorlevel!
  )
)
set "CODEX_RUNTIME_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%CODEX_RUNTIME_PYTHON%" (
  "%CODEX_RUNTIME_PYTHON%" "%~dp0open_plana.py" %*
  exit /b !errorlevel!
)
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0open_plana.py" %*
  exit /b %errorlevel%
)
for /f "delims=" %%P in ('where python 2^>nul') do (
  echo %%P | findstr /i "\\Microsoft\\WindowsApps\\" >nul
  if errorlevel 1 (
    "%%P" "%~dp0open_plana.py" %*
    exit /b !errorlevel!
  )
)
echo Python 3 was not found. Install Python 3.10+ and run: pip install -r "%~dp0requirements.txt"
echo Or set OPEN_PLANA_PYTHON to a Python executable path.
exit /b 1
