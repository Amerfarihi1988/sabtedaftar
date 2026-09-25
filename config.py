"""
فایل تنظیمات کلی نرم‌افزار
«نرم‌افزار دفتر خروج کالا» - مدیریت مجوز خروج کالا
"""
import sys
import os
from pathlib import Path

# ─── مسیر پایه ───
# وقتی برنامه به EXE تبدیل شده، داده‌ها کنار فایل EXE ذخیره می‌شوند
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

# ─── مسیر فایل‌های داخلی (استایل و...) ───
if getattr(sys, 'frozen', False):
    # در حالت EXE، فایل‌های باندل‌شده در پوشه‌ی _internal هستند
    ASSETS_DIR = Path(getattr(sys, '_MEIPASS', BASE_DIR)) / "assets"
    # آیکون برنامه داخل باندل است (از spec به ریشه‌ی باندل اضافه می‌شود)
    ICON_PATH = Path(getattr(sys, '_MEIPASS', BASE_DIR)) / "logo.ico"
else:
    ASSETS_DIR = BASE_DIR / "assets"
    ICON_PATH = BASE_DIR / "logo.ico"

DB_PATH = BASE_DIR / "data" / "sabtedaftar.db"
SCANS_DIR = BASE_DIR / "data" / "scans"
BACKUP_DIR = BASE_DIR / "backups"
TEMPLATES_DIR = BASE_DIR / "templates"

# ─── تنظیمات شماره‌گذاری ───
PERMIT_NUMBER_FORMAT = "{year}/{number:03d}"

# ─── تنظیمات سهمیه ───
QUOTA_WARNING_THRESHOLD = 0.9  # ۹۰٪ مصرف → هشدار زرد

# ─── نام نرم‌افزار ───
APP_NAME = "نرم‌افزار دفتر خروج کالا"
APP_VERSION = "1.3.0"


def ensure_directories():
    """ساخت پوشه‌های لازم در صورت عدم وجود"""
    for directory in [SCANS_DIR, BACKUP_DIR, TEMPLATES_DIR, ASSETS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def get_db_path():
    return str(DB_PATH)


def get_scans_dir():
    return str(SCANS_DIR)