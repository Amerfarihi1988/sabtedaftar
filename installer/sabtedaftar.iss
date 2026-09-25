; ═══════════════════════════════════════════════════════════
;  نصاب نرم‌افزار دفتر خروج کالا — Inno Setup 6
;  ساخت نصاب: پس از build.bat، این فایل را با Inno Setup
;  (ISCC.exe) کامپایل کنید:
;      ISCC.exe installer\sabtedaftar.iss
;  خروجی: installer\Output\SetupDafterKhorojKala.exe
; ═══════════════════════════════════════════════════════════

#define MyAppName "نرم‌افزار دفتر خروج کالا"
#define MyAppVersion "1.3.0"
; نسخه را همگام با config.py نگه دارید
#define MyAppExeName "DafterKhorojKala.exe"

[Setup]
AppId={{8A7C4E3F-2B1D-4E6A-9F0C-5D8E1A2B3C4D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={autopf}\DafterKhorojKala
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputBaseFilename=SetupDafterKhorojKala
OutputDir=Output
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; برنامه داده‌هایش را در پوشه‌ی خودش (data\backups) نگه می‌دارد
; و به Admin فقط برای نوشتن در Program Files نیاز دارد
PrivilegesRequired=admin
DirExistsWarning=no
ShowLanguageDialog=no

[Languages]
Name: "farsi"; MessagesFile: "compiler:Languages\Default.isl"

[CustomMessages]
farsi.CreateDesktopIcon=ایجاد میان‌بر روی دسکتاپ
farsi.launchApp=اجرای %1

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "میان‌برها:"

[Files]
; EXE ساخته‌شده توسط build.bat
Source: "..\dist\DafterKhorojKala.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\logo.ico"
Name: "{group}\حذف {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:launchApp,{#MyAppName}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; داده‌های کاربر (دیتابیس/اسکن/پشتیبان) عمداً حفظ می‌شوند؛
; اگر کاربر پاک‌سازی کامل خواست، پوشه‌ی برنامه را دستی حذف کند.
Type: filesandordirs; Name: "{app}\data\scans"
