"""
پشتیبان‌گیری خودکار از پایگاه داده — نسخه امن

اصلاحات امنیتی:
- کپی دیتابیس با sqlite3 backup API (سازگار با اتصال‌های باز، بدون خطر کپی ناقص)
- استفاده از SCANS_DIR مطلق از config به‌جای مسیر نسبی وابسته به پوشه‌ی اجرا
- استخراج امن ZIP با مقابله با Zip Slip (ورود مسیرهای ../.. یا مطلق)
- رفع NameError ثبت لاگ خطا و گزارش اندازه‌ی غیرمنطقی فایل دیتابیس
"""
import os
import shutil
import sqlite3
import zipfile
import jdatetime
from database.db_manager import db
from config import DB_PATH, SCANS_DIR, BACKUP_DIR

# سقف منطقی برای فایل دیتابیس بازگردانی‌شده (محافظت در برابر فایل خراب/Zip Bomb)
MAX_DB_RESTORE_SIZE = 512 * 1024 * 1024  # 512MB


def _backup_database(dest_db_path):
    """
    کپی امن دیتابیس با sqlite3 backup API.
    برخلاف کپی مستقیم فایل، اگر اتصال دیگری باز باشد یا WAL فعال باشد،
    نسخه‌ی سازگار و کامل از دیتابیس می‌گیرد.
    """
    src = sqlite3.connect(str(DB_PATH))
    try:
        dst = sqlite3.connect(str(dest_db_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _safe_extract_zip(zip_path, dest_dir):
    """
    استخراج امن ZIP با مقابله با Zip Slip:
    هر ورودی باید داخل dest_dir بماند؛ مسیرهای مطلق و «..» رد می‌شوند.
    """
    dest_root = os.path.realpath(dest_dir)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            name = info.filename
            if os.path.isabs(name) or name.startswith(("/", "\\")):
                raise ValueError(f"مسیر مطلق غیرمجاز در پشتیبان: {name}")
            target = os.path.realpath(os.path.join(dest_dir, name))
            if not (target == dest_root or target.startswith(dest_root + os.sep)):
                raise ValueError(f"مسیر ناامن در پشتیبان (Zip Slip): {name}")

            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue

            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def create_backup():
    """
    ساخت فایل پشتیبان از پایگاه داده و اسکن‌ها.
    خروجی: مسیر فایل پشتیبان یا None
    """
    backup_name = None
    now = jdatetime.datetime.now()

    try:
        date_str = now.strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{date_str}"
        backup_path = os.path.join(str(BACKUP_DIR), backup_name)

        # پوشه‌ی موقت
        os.makedirs(backup_path, exist_ok=True)

        # کپی امن دیتابیس
        if os.path.exists(str(DB_PATH)):
            _backup_database(os.path.join(backup_path, "sabtedaftar.db"))

        # کپی اسکن‌ها (مسیر مطلق از config — مستقل از پوشه‌ی اجرا)
        if os.path.exists(str(SCANS_DIR)):
            shutil.copytree(str(SCANS_DIR), os.path.join(backup_path, "scans"))

        # فشرده‌سازی به ZIP
        zip_path = backup_path + ".zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(backup_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, backup_path)
                    zf.write(file_path, arcname)

        # حذف پوشه‌ی موقت
        shutil.rmtree(backup_path)

        # ثبت لاگ
        db.execute(
            "INSERT INTO backups (filename, file_path, created_at, status) VALUES (?, ?, ?, ?)",
            (backup_name + ".zip", zip_path, now.strftime("%Y/%m/%d %H:%M:%S"), "success")
        )

        return zip_path

    except Exception as e:
        print(f"[پشتیبان] خطا: {e}")
        try:
            db.execute(
                "INSERT INTO backups (filename, file_path, created_at, status) VALUES (?, ?, ?, ?)",
                ((backup_name or "unknown") + ".zip", "", now.strftime("%Y/%m/%d %H:%M:%S"), f"failed: {e}")
            )
        except Exception:
            pass
        return None


def restore_backup(zip_path):
    """
    بازگردانی پشتیبان از فایل ZIP — با استخراج امن (ضد Zip Slip).
    پس از بازگردانی موفق، برنامه باید مجدداً اجرا شود.
    """
    import tempfile
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()

        # استخراج امن
        _safe_extract_zip(zip_path, temp_dir)

        # بازگردانی دیتابیس (با کنترل اندازه‌ی منطقی)
        db_file = os.path.join(temp_dir, "sabtedaftar.db")
        if os.path.exists(db_file):
            if os.path.getsize(db_file) > MAX_DB_RESTORE_SIZE:
                raise ValueError("فایل دیتابیس پشتیبان غیرمنطقی بزرگ است")
            shutil.copy2(db_file, str(DB_PATH))

        # بازگردانی اسکن‌ها (مسیر مطلق از config)
        scans_backup = os.path.join(temp_dir, "scans")
        if os.path.exists(scans_backup):
            if os.path.exists(str(SCANS_DIR)):
                shutil.rmtree(str(SCANS_DIR))
            shutil.copytree(scans_backup, str(SCANS_DIR))

        shutil.rmtree(temp_dir, ignore_errors=True)
        return True

    except Exception as e:
        print(f"[بازگردانی] خطا: {e}")
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return False


def auto_backup_if_needed():
    """
    پشتیبان‌گیری خودکار بر اساس تنظیمات.
    هر روز یک‌بار هنگام باز شدن برنامه.
    """
    try:
        setting = db.fetch_one("SELECT value FROM settings WHERE key='auto_backup'")
        if not setting or setting["value"] != "1":
            return None

        today = jdatetime.date.today().strftime("%Y/%m/%d")
        last = db.fetch_one(
            "SELECT created_at FROM backups WHERE status='success' "
            "ORDER BY created_at DESC LIMIT 1"
        )

        if last and last["created_at"].startswith(today):
            return None  # امروز پشتیبان گرفته شده

        return create_backup()
    except Exception as e:
        print(f"[پشتیبان خودکار] خطا: {e}")
        return None


def get_backup_list():
    """لیست پشتیبان‌ها"""
    return db.fetch_all("SELECT * FROM backups ORDER BY created_at DESC LIMIT 50")
