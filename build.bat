@echo off
echo ============================================
echo   Build Installer - DafterKhorojKala
echo ============================================
echo.

REM Build from spec file (single source of truth: datas, hiddenimports, icon)
REM Spec is onefile type - output is a single standalone EXE
pyinstaller --noconfirm --clean DafterKhorojKala.spec

echo.
if not exist "dist\DafterKhorojKala.exe" (
    echo BUILD FAILED! Check messages above.
    pause
    exit /b 1
)

echo ============================================
echo   EXE built: dist\DafterKhorojKala.exe
echo   This is a single standalone file - just copy
echo   this one file to the target system and run it.
echo.
echo   Note: on first run Windows pauses a few seconds
echo   ^(extracting internal bundle^) - this is normal.
echo ============================================

REM --- Optional Inno Setup installer (only if ISCC is installed) ---
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"

if defined ISCC (
    echo.
    echo Building installer with Inno Setup...
    "%ISCC%" installer\sabtedaftar.iss
    if exist "installer\Output\SetupDafterKhorojKala.exe" (
        echo ============================================
        echo   Installer built: installer\Output\SetupDafterKhorojKala.exe
        echo   Run this installer file on the target system.
        echo ============================================
    ) else (
        echo Installer NOT built - check Inno Setup messages above.
    )
) else (
    echo.
    echo [optional] Inno Setup 6 not found - installer not built.
    echo To build the installer, download and install: https://jrsoftware.org/isdl.php
    echo then run build.bat again.
)

echo.
pause
