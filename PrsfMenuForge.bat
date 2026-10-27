@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0TOOLS\venv\Scripts\pythonw.exe" (
  start "" "%~dp0TOOLS\venv\Scripts\pythonw.exe" "%~dp0main.py"
  exit /b 0
)
echo PySide6 is not installed locally. Please run install.bat first.
pause
exit /b 1
