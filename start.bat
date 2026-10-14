@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 run.py %*
  goto finished
)
where python >nul 2>nul
if %errorlevel% equ 0 (
  python run.py %*
  goto finished
)
echo Python 3.10 or newer is required. Install Python, then run this file again.
:finished
pause
