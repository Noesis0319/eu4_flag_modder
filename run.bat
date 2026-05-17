@echo off
REM Run from source (dev mode). For end users, distribute dist\EU4ModMaker.exe.
cd /d "%~dp0"
python main.py
if errorlevel 1 pause
