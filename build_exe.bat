@echo off
REM EU4 Mod Maker - single-file exe build script
REM Output: <out root>\eu4_flag_modder\dist\EU4ModMaker.exe (standalone, no Python required)
REM out root: D:\out, or C:\dev\out on a PC without D:

cd /d "%~dp0"
if exist D:\ (set "OUT=D:\out\eu4_flag_modder") else (set "OUT=C:\dev\out\eu4_flag_modder")

echo === [1/3] Installing dependencies ===
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
python -m pip install pyinstaller
if errorlevel 1 goto :fail

echo === [2/3] Cleaning previous build ===
if exist "%OUT%\build" rmdir /s /q "%OUT%\build"
if exist "%OUT%\dist"  rmdir /s /q "%OUT%\dist"

echo === [3/3] Running PyInstaller ===
python -m PyInstaller --clean --noconfirm --workpath "%OUT%\build" --distpath "%OUT%\dist" EU4ModMaker.spec
if errorlevel 1 goto :fail

echo.
echo === BUILD SUCCESS ===
echo Output: %OUT%\dist\EU4ModMaker.exe
echo Distribute this single file (no Python / Pillow needed).
echo.
pause
exit /b 0

:fail
echo.
echo *** BUILD FAILED ***
pause
exit /b 1
