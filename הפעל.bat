@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0PrsfMenuForge.ps1"
if errorlevel 1 pause
