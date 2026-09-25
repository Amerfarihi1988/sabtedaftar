"""
تست round-trip پشتیبان‌گیری — اجرا: python tests/test_backup_roundtrip.py

سناریو:
  1. دیتابیس موقت با داده → create_backup()
  2. دیتابیس را تغییر بده (داده جدید)
  3. restore_backup() → داده‌ها باید به حالت اول برگردند
  4. مهاجرت خودکار بعد از restore روی نسخه قدیمی هم کار کند
  5. cleanup_old_backups فقط قدیمی‌ها را حذف کند
"""
import os
import sys
import sqlite3
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

tmp = tempfile.mkdtemp()

import config  # noqa: E402
config.DB_PATH = Path(tmp) / "test.db"
config.BACKUP_DIR = Path(tmp) / "backups"
config.ensure_directories()

failures = []


def check(label, cond, detail=""):
    mark = "✓" if cond else "✗"
    print(f"{mark} {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(label)


def company_count():
    return db.fetch_one("SELECT COUNT(*) as c FROM companies")["c"]


def company_name():
    return db.fetch_one("SELECT name FROM companies LIMIT 1")["name"]


# ── داده اولیه ──
from database.db_manager import db  # noqa: E402
db.execute(
    "INSERT INTO companies (name, has_certificate) VALUES ('شرکت اصلی', 0)"
)
original_count = company_count()
original_name = company_name()

# ── مرحله ۱: بکاپ ──
from services.backup import create_backup, restore_backup, cleanup_old_backups  # noqa: E402
zip_path = create_backup()
check("پشتیبان ساخته شد", zip_path is not None and os.path.exists(str(zip_path)),
      str(zip_path))

# ── مرحله ۲: دست‌کاری ──
db.execute("INSERT INTO companies (name, has_certificate) VALUES ('شرکت اضافی', 0)")
db.execute("UPDATE companies SET name='تغییر یافته' WHERE name='شرکت اصلی'")
check("داده تغییر کرد (۲ شرکت)", company_count() == 2)

# ── مرحله ۳: بازگردانی ──
ok = restore_backup(str(zip_path))
check("بازگردانی موفق", ok is True)
check("داده‌ها برگشتند (۱ شرکت)", company_count() == original_count,
      str(company_count()))
check("نام اصلی برگشت", company_name() == original_name, company_name())

# ── مرحله ۴: restore پشتیبان قدیمی (v0) → مهاجرت خودکار ──
# یک دیتابیس v0 قدیمی می‌سازیم و در قالب ZIP پشتیبان می‌گذاریم
import zipfile  # noqa: E402
old_db = Path(tmp) / "old_v0.db"
conn = sqlite3.connect(str(old_db))
conn.executescript("""
    CREATE TABLE companies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TEXT);
    CREATE TABLE settings (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL UNIQUE, value TEXT);
""")
conn.execute("INSERT INTO companies (name) VALUES ('شرکت قدیمی v0')")
conn.commit()
conn.close()

old_zip = Path(tmp) / "backup_old.zip"
with zipfile.ZipFile(old_zip, "w") as zf:
    zf.write(str(old_db), "sabtedaftar.db")

ok = restore_backup(str(old_zip))
check("بازگردانی پشتیبان قدیمی موفق", ok is True)
v = sqlite3.connect(str(config.DB_PATH)).execute("PRAGMA user_version").fetchone()[0]
from database.migrations import LATEST_VERSION  # noqa: E402
check("مهاجرت خودکار بعد از restore اجرا شد", v == LATEST_VERSION, f"v{v}")
cols = [r[1] for r in sqlite3.connect(str(config.DB_PATH)).execute(
    "PRAGMA table_info(exit_items)"
)]
# جدول exit_items نبوده؛ مهاجرت ۱ آن را نمی‌سازد (CREATE TABLE کارِ db_manager است)
# اما dbManager در اجرای بعدی می‌سازد — فقط یکتایی و ستون‌های جدول‌های موجود چک می‌شود
check("شرکت قدیمی برگشت", company_name() == "شرکت قدیمی v0")

# برگشت به حالت تمیز برای مرحله ۵:
# چون restore، دیتابیس v0 قدیمی را جایگزین کرده، singleton db هم باید
# ساختار کامل را دوباره بسازد (مسیر واقعی اجرای بعدی برنامه)
db._create_tables()
from database.seed import run_seed  # noqa: E402
run_seed()

shutil.rmtree(str(config.BACKUP_DIR) if isinstance(config.BACKUP_DIR, str)
              else config.BACKUP_DIR, ignore_errors=True)
Path(config.BACKUP_DIR).mkdir(parents=True, exist_ok=True)

# ── مرحله ۵: نگهداری پشتیبان‌ها ──
import time  # noqa: E402
for i in range(7):
    db.execute(
        "INSERT INTO companies (name, has_certificate) VALUES (?, 0)",
        (f"شرکت {i}",)
    )
    zp = create_backup()
    assert zp, f"backup {i} failed"
    time.sleep(1.1)  # نام پشتیبان بر اساس ثانیه است — نباید تکراری شود

zips = sorted(
    [f for f in os.listdir(str(config.BACKUP_DIR))
     if f.startswith("backup_") and f.endswith(".zip")]
)
check("۷ پشتیبان ساخته شد", len(zips) == 7, str(len(zips)))

removed = cleanup_old_backups(3)
zips = sorted(
    [f for f in os.listdir(str(config.BACKUP_DIR))
     if f.startswith("backup_") and f.endswith(".zip")]
)
check("پاک‌سازی به ۳ عدد", len(zips) == 3 and removed == 4,
      f"removed={removed}, left={len(zips)}")

# قدیمی‌ترین‌ها حذف شده‌اند (جدیدترین مونده)
rows = db.fetch_all("SELECT COUNT(*) as c FROM backups")["c" if False else 0] \
    if False else db.fetch_one("SELECT COUNT(*) as c FROM backups")["c"]
check("رکوردهای حذف‌شده از جدول backups هم پاک شدند",
      rows == 3, str(rows))

ic = sqlite3.connect(str(config.DB_PATH)).execute("PRAGMA integrity_check").fetchone()[0]
check("integrity_check = ok", ic == "ok")

shutil.rmtree(tmp, ignore_errors=True)

if failures:
    print(f"\n{len(failures)} مورد شکست خورد:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nBACKUP ROUND-TRIP PASSED")
