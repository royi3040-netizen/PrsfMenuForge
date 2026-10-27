@echo off
setlocal
cd /d "%~dp0"
if not exist "TOOLS" mkdir "TOOLS"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m venv "TOOLS\venv"
) else (
  python -m venv "TOOLS\venv"
)
if errorlevel 1 goto failed
"%~dp0TOOLS\venv\Scripts\python.exe" -m pip install --upgrade pip
"%~dp0TOOLS\venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Installation completed successfully. Run PrsfMenuForge.bat
pause
exit /b 0
:failed
echo.
echo Installation failed. Install Python 3.11 or later and ensure internet access.
pause
exit /b 1
