"""
تست بسته ۴ (امنیت داده): پشتیبان دوم هفتگی + رمز ورود اختیاری
اجرا: python tests/test_security_pack.py

سناریوها:
  A1: حالت پیش‌فرض — غیرفعال → skipped-disabled
  A2: فعال + مسیر محلی موقت → created و فایل ZIP سالم و آخرین پشتیبان
  A3: قاعده هفتگی — بلافاصله بعد از کپی → skipped-recent
  A4: بک‌دیت secondary_backup_last → کپی انجام می‌شود (idempotent در برابر خرابی)
  A5: مسیر غیرقابل دسترس → unreachable (بدون کرش)
  A6: بدون هیچ پشتیبانی → خودکار پشتیبان می‌سازد و کپی می‌کند
  B1..B4: رمز ورود — set/verify غلط/درست، clear، فرمت هش
"""
import os
import sys
import sqlite3
import tempfile
import shutil
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

tmp = tempfile.mkdtemp()

import config  # noqa: E402
config.DB_PATH = Path(tmp) / "test.db"
config.BACKUP_DIR = Path(tmp) / "backups"
config.ensure_directories()

failures = []


def check(label, cond, detail=""):
    mark = "OK " if cond else "FAIL"
    print(f"{mark} {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(label)


# ── دیتابیس ──
from database.db_manager import db  # noqa: E402
db.execute("INSERT INTO companies (name, has_certificate) VALUES ('شرکت تست', 0)")

# ── بخش A: پشتیبان دوم ──
from services import backup as bk  # noqa: E402


def set_key(key, value):
    db.execute(
        """INSERT INTO settings (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (key, value)
    )


def get_key(key):
    rec = db.fetch_one("SELECT value FROM settings WHERE key=?", (key,))
    return rec["value"] if rec else None


# A1: پیش‌فرض — غیرفعال
status, path = bk.run_secondary_backup_if_needed()
check("A1: غیرفعال → skipped-disabled", status == "skipped-disabled", status)

# A6: بدون هیچ پشتیبانی روی دیسک → خودکار پشتیبان می‌سازد و کپی می‌کند
sec_dir = os.path.join(tmp, "secondary")
set_key("secondary_backup_enabled", "1")
set_key("secondary_backup_path", sec_dir)
set_key("secondary_backup_last", "")
status, path = bk.run_secondary_backup_if_needed()
check("A6: بدون پشتیبان → خودکار ساخت و کپی کرد", status == "created", status)
check("A6: فایل کپی‌شده وجود دارد", path and os.path.exists(str(path)), str(path))
check("A6: تاریخ آخرین کپی ثبت شد",
      get_key("secondary_backup_last") not in (None, ""), 
      str(get_key("secondary_backup_last")))

# A2: کپی سالم — فایل ZIP معتبر و برابر آخرین پشتیبان روزانه
coppied_name = os.path.basename(str(path))
latest = os.path.basename(bk._find_latest_daily_backup_zip())
check("A2: کپی همان آخرین پشتیبان است", coppied_name == latest,
      f"{coppied_name} vs {latest}")
with __import__("zipfile").ZipFile(str(path)) as zf:
    names = zf.namelist()
check("A2: ZIP سالم شامل دیتابیس", "sabtedaftar.db" in names, str(names))

# A3: قاعده هفتگی — بلافاصله بعد از کپی → skipped-recent
status, path = bk.run_secondary_backup_if_needed()
check("A3: بلافاصله بعد از کپی → skipped-recent", status == "skipped-recent", status)

# A4: بک‌دیت تاریخ → دوباره کپی می‌کند
time.sleep(1.1)  # نام پشتیبان ثانیه‌ای است
bk.create_backup()
set_key("secondary_backup_last", "1300/01/01")
status, path = bk.run_secondary_backup_if_needed()
check("A4: تاریخ خراب/قدیمی → کپی مجدد", status == "created", status)

# A5: مسیر غیرقابل دسترس (فایل به‌جای پوشه) → unreachable بدون کرش
set_key("secondary_backup_last", "1300/01/01")  # قاعده هفتگی را فعال کن
blocked_file = os.path.join(tmp, "blocked_file")
with open(blocked_file, "w") as f:
    f.write("not a dir")
set_key("secondary_backup_path", blocked_file)
status, path = bk.run_secondary_backup_if_needed()
check("A5: مسیر غیرقابل دسترس → unreachable", status == "unreachable", status)

# force=True قاعده هفتگی را دور می‌زند
set_key("secondary_backup_path", sec_dir)
set_key("secondary_backup_last", "")  # امروز
status, path = bk.run_secondary_backup_if_needed(force=True)
check("A7: force=True قاعده هفتگی را دور می‌زند", status == "created", status)

# ── بخش B: رمز ورود ──
from services import auth  # noqa: E402

check("B1: ابتدا رمزی ثبت نشده", auth.is_password_set() is False)
check("B1: بدون رمز، هر ورودی مجاز است", auth.verify_password("anything") is True)

auth.set_password("رمز مخفی 123")
check("B2: رمز ثبت شد", auth.is_password_set() is True)
check("B2: رمز درست پذیرفته می‌شود", auth.verify_password("رمز مخفی 123") is True)
check("B2: رمز غلط رد می‌شود", auth.verify_password("رمز غلط") is False)
check("B2: رمز خالی رد می‌شود", auth.verify_password("") is False)

stored = get_key("password_hash")
check("B3: هش ذخیره شده (بدون رمز خام)", stored and stored.startswith("pbkdf2_sha256$"),
      (stored or "")[:40] + "...")
parts = stored.split("$")
check("B3: فرمت ۴ بخشی با salt", len(parts) == 4 and len(parts[2]) >= 32)
check("B3: رمز خام در دیتابیس نیست", "رمز مخفی" not in stored)

auth.set_password("رمز دوم")
check("B4: تغییر رمز — رمز قدیمی رد", auth.verify_password("رمز مخفی 123") is False)
check("B4: تغییر رمز — رمز جدید پذیرفته", auth.verify_password("رمز دوم") is True)

auth.clear_password()
check("B5: حذف رمز — دیگر فعال نیست", auth.is_password_set() is False)
check("B5: بعد از حذف، همه مجازند", auth.verify_password("") is True)

try:
    auth.set_password("   ")
    check("B6: رمز خالی/فقط فاصله رد می‌شود", False)
except ValueError:
    check("B6: رمز خالی/فقط فاصله رد می‌شود", True)

# integrity نهایی
ic = sqlite3.connect(str(config.DB_PATH)).execute("PRAGMA integrity_check").fetchone()[0]
check("integrity_check = ok", ic == "ok")

shutil.rmtree(tmp, ignore_errors=True)

if failures:
    print(f"\n{len(failures)} مورد شکست خورد:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nSECURITY PACK (بسته ۴) PASSED")
