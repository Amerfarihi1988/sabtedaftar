@echo off
chcp 65001 >nul
echo ============================================
echo   ساخت فایل نصبی - نرم‌افزار دفتر خروج کالا
echo ============================================
echo.

REM ساخت از فایل spec (منبع واحد تنظیمات: datas, hiddenimports, icon)
REM spec از نوع onefile است — خروجی یک فایل EXE مستقل است
pyinstaller --noconfirm --clean DafterKhorojKala.spec

echo.
if not exist "dist\DafterKhorojKala.exe" (
    echo خطا در ساخت! پیام‌های بالا را بررسی کنید.
    pause
    exit /b 1
)

echo ============================================
echo   EXE ساخته شد: dist\DafterKhorojKala.exe
echo   این یک فایل واحد مستقل است — کافیست همان یک فایل را
echo   روی سیستم مقصد کپی و اجرا کنید.
echo.
echo   نکته: در اولین اجرا، ویندوز چند ثانیه مکث دارد
echo   ^(باز کردن بسته داخلی^) — طبیعی است.
echo ============================================

REM ─── ساخت نصاب Inno Setup (اختیاری — اگر ISCC نصب باشد) ───
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"

if defined ISCC (
    echo.
    echo ساخت نصاب با Inno Setup...
    "%ISCC%" installer\sabtedaftar.iss
    if exist "installer\Output\SetupDafterKhorojKala.exe" (
        echo ============================================
        echo   نصاب ساخته شد: installer\Output\SetupDafterKhorojKala.exe
        echo   برای نصب روی سیستم مقصد، همین فایل نصاب را اجرا کنید.
        echo ============================================
    ) else (
        echo نصاب ساخته نشد — پیام‌های Inno Setup را بررسی کنید.
    )
) else (
    echo.
    echo [اختیاری] Inno Setup 6 یافت نشد — نصاب ساخته نشد.
    echo برای ساخت نصاب: https://jrsoftware.org/isdl.php را نصب کنید
    echo و دوباره build.bat را اجرا کنید.
)

echo.
pause
