@echo off
chcp 65001 >nul
echo ============================================
echo   ساخت فایل نصبی - نرم‌افزار دفتر خروج کالا
echo ============================================
echo.

REM ساخت از فایل spec (منبع واحد تنظیمات: datas, hiddenimports, icon)
pyinstaller --noconfirm --clean DafterKhorojKala.spec

echo.
if exist "dist\DafterKhorojKala\DafterKhorojKala.exe" (
    echo ============================================
    echo   ساخته شد! خروجی:
    echo   dist\DafterKhorojKala\DafterKhorojKala.exe
    echo   (کل پوشه dist\DafterKhorojKala را همراه EXE منتقل کنید)
    echo ============================================
) else (
    echo خطا در ساخت! پیام‌های بالا را بررسی کنید.
)
pause
