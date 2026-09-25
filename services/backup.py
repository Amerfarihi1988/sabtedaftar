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
    اگر پشتیبان قدیمی باشد (نسخه‌ی ساختار پایین‌تر)، مهاجرت‌ها بلافاصله
    بعد از بازگردانی اجرا می‌شوند تا دیتابیس با ساختار برنامه هم‌تراز باشد.
    """
    import tempfile
    from database.migrations import run_migrations
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
            # هم‌ترازسازی ساختار با نسخه‌ی فعلی برنامه (idempotent است؛
            # اگر پشتیبان به‌روز باشد، کاری انجام نمی‌دهد)
            run_migrations(str(DB_PATH))

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

        result = create_backup()

        # پاک‌سازی پشتیبان‌های قدیمی بر اساس سیاست نگهداری در تنظیمات
        if result:
            keep = db.fetch_one(
                "SELECT value FROM settings WHERE key='backup_keep_count'"
            )
            if not keep:
                # seed خودکار کلید نگهداری اگر تنظیم نشده باشد (نصب قدیمی)
                db.execute(
                    "INSERT OR IGNORE INTO settings (key, value) "
                    "VALUES ('backup_keep_count', '30')"
                )
                keep_count = 30
            else:
                try:
                    keep_count = int(keep["value"])
                except (ValueError, TypeError):
                    keep_count = 30
            cleanup_old_backups(keep_count)

        return result
    except Exception as e:
        print(f"[پشتیبان خودکار] خطا: {e}")
        return None


def cleanup_old_backups(keep_count=30):
    """
    حذف پشتیبان‌های ZIP قدیمی‌تر از تعداد مجاز (پیش‌فرض ۳۰).
    رکوردهای بایگانی‌شده در جدول backups هم به‌روزرسانی می‌شوند.
    خروجی: تعداد فایل‌های حذف‌شده
    """
    try:
        keep_count = max(3, int(keep_count))
    except (TypeError, ValueError):
        keep_count = 30

    try:
        # فایل‌های ZIP روی دیسک — جدیدترین‌ها اول (نام شامل زمان‌مهر است)
        zip_files = sorted(
            [f for f in os.listdir(str(BACKUP_DIR))
             if f.startswith("backup_") and f.endswith(".zip")],
            reverse=True
        )
        old_files = zip_files[keep_count:]

        removed = 0
        for name in old_files:
            path = os.path.join(str(BACKUP_DIR), name)
            try:
                os.remove(path)
                removed += 1
            except OSError:
                continue
            db.execute(
                "DELETE FROM backups WHERE filename=?", (name,)
            )
        return removed
    except Exception as e:
        print(f"[پاک‌سازی پشتیبان] خطا: {e}")
        return 0


def get_backup_list():
    """لیست پشتیبان‌ها"""
    return db.fetch_all("SELECT * FROM backups ORDER BY created_at DESC LIMIT 50")


# ────────────────────────────────────────────────────────────────────────────
# پشتیبان دوم هفتگی (خارج از سیستم — محافظت در برابر خرابی دیسک/ویروس)
# ────────────────────────────────────────────────────────────────────────────

def _get_setting(key, default=None):
    rec = db.fetch_one("SELECT value FROM settings WHERE key=?", (key,))
    return rec["value"] if rec and rec["value"] is not None else default


def _set_setting(key, value):
    db.execute(
        """INSERT INTO settings (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (key, value)
    )


def _find_latest_daily_backup_zip():
    """جدیدترین ZIP پشتیبان موفق — از دیسک (نام شامل زمان‌مهر است)"""
    try:
        zip_files = sorted(
            [f for f in os.listdir(str(BACKUP_DIR))
             if f.startswith("backup_") and f.endswith(".zip")],
            reverse=True
        )
        if zip_files:
            return os.path.join(str(BACKUP_DIR), zip_files[0])
    except OSError:
        pass
    return None


def _copy_zip_to_secondary(source_zip, dest_dir):
    """
    کپی ZIP پشتیبان به مسیر دوم (فلش/شبکه/درایو دیگر).
    خروجی: مسیر فایل کپی‌شده یا None.
    اگر مسیر مقصد در دسترس نباشد (مثلاً فلش وصل نیست) خطا بالا داده نمی‌شود؛
    پیام برمی‌گردد تا لاگ شود و برنامه مختل نشود.
    """
    try:
        dest_dir = str(dest_dir)
        os.makedirs(dest_dir, exist_ok=True)
        # بررسی واقعی در دسترس بودن مقصد (شبکه قطع / فلش جدا شده)
        probe = os.path.join(dest_dir, ".backup_probe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)

        base = os.path.splitext(os.path.basename(source_zip))[0]
        dest_path = os.path.join(dest_dir, base + ".zip")
        shutil.copy2(source_zip, dest_path)
        return dest_path
    except OSError as e:
        print(f"[پشتیبان دوم] مسیر مقصد در دسترس نیست: {e}")
        return None


def run_secondary_backup_if_needed(force=False):
    """
    پشتیبان دوم هفتگی: کپی آخرین پشتیبان ZIP به مسیر تنظیم‌شده‌ی خارجی.
    قاعده: هفت‌روز یک‌بار — بر اساس تنظیمات:
      secondary_backup_enabled (1/0)
      secondary_backup_path    (مسیر پوشه‌ی مقصد)
      secondary_backup_last    (تاریخ شمسی آخرین کپی موفق — YYYY/MM/DD)
    خروجی: (status, path) — status یکی از:
      'created' | 'skipped-disabled' | 'skipped-no-path' | 'skipped-recent'
      | 'skipped-no-backup' | 'unreachable' | 'error'
    """
    try:
        enabled = _get_setting("secondary_backup_enabled", "0")
        if enabled != "1" and not force:
            return ("skipped-disabled", None)

        dest_dir = (_get_setting("secondary_backup_path", "") or "").strip()
        if not dest_dir and not force:
            return ("skipped-no-path", None)

        # قاعده هفتگی: ۷ روز شمسی از آخرین کپی موفق گذشته باشد
        if not force:
            last = (_get_setting("secondary_backup_last", "") or "").strip()
            if last:
                try:
                    last_d = jdatetime.datetime.strptime(last, "%Y/%m/%d").date()
                    if (jdatetime.date.today() - last_d).days < 7:
                        return ("skipped-recent", None)
                except ValueError:
                    pass  # مقدار خراب → کپی انجام می‌شود و مقدار تازه ثبت می‌شود

        # به تازگیِ روزانه اهمیت ندارد؛ آخرین ZIP موجود کافی است —
        # ولی اگر هیچ پشتیبانی نیست، اول یک پشتیبان روزانه می‌سازیم
        source_zip = _find_latest_daily_backup_zip()
        if not source_zip:
            source_zip = create_backup()
        if not source_zip:
            return ("skipped-no-backup", None)

        copied = _copy_zip_to_secondary(source_zip, dest_dir)
        if not copied:
            return ("unreachable", None)

        _set_setting("secondary_backup_last", jdatetime.date.today().strftime("%Y/%m/%d"))
        print(f"[پشتیبان دوم] کپی شد: {copied}")
        return ("created", copied)
    except Exception as e:
        print(f"[پشتیبان دوم] خطا: {e}")
        return ("error", None)
