@echo off
REM EU4 Mod Maker - single-file exe build script
REM Output: dist\EU4ModMaker.exe (standalone, no Python required)

cd /d "%~dp0"

echo === [1/3] Installing dependencies ===
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
python -m pip install pyinstaller
if errorlevel 1 goto :fail

echo === [2/3] Cleaning previous build ===
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo === [3/3] Running PyInstaller ===
python -m PyInstaller --clean --noconfirm EU4ModMaker.spec
if errorlevel 1 goto :fail

echo.
echo === BUILD SUCCESS ===
echo Output: %CD%\dist\EU4ModMaker.exe
echo Distribute this single file (no Python / Pillow needed).
echo.
pause
exit /b 0

:fail
echo.
echo *** BUILD FAILED ***
pause
exit /b 1
