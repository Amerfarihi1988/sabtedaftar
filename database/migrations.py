"""
مکانیزم مهاجرت دیتابیس (Schema Migration)

هدف: هر نسخه‌ی جدید برنامه بتواند ساختار دیتابیس را تغییر دهد بدون آنکه
داده‌های نصب‌شده روی سیستم‌های دیگر آسیب ببینند.

اصول طراحی:
- شماره‌ی نسخه‌ی ساختار دیتابیس در PRAGMA user_version نگهداری می‌شود.
- هر مهاجرت یک تابع idempotent است؛ اجرای دوباره‌ی آن بی‌ضرر است
  (ستون فقط اگر نبود اضافه می‌شود، ایندکس‌ها IF NOT EXISTS و ...).
- هر مهاجرت داخل یک تراکنش اتمیک اجرا می‌شود؛ اگر خطا بخورد rollback می‌شود
  و user_version هم بالا نمی‌رود (پس اجرای بعدی دوباره همان را اجرا می‌کند).
- پیش از اولین مهاجرت روی هر دیتابیس، پشتیبان امن (sqlite backup API) از
  خود فایل در backups/pre_migration گرفته می‌شود و ۱۰ نسخه‌ی آخر نگه داشته می‌شود.
- همه‌ی رویدادها در data/migrations.log ثبت می‌شوند.
- اگر نسخه‌ی دیتابیس جدیدتر از نسخه‌ی پشتیبانی‌شده‌ی برنامه باشد (سناریوی
  downgrade)، مهاجرت انجام نمی‌شود و خطا گزارش می‌شود تا برنامه با ساختار
  ناسازگار اجرا نشود و داده‌ها خراب نشوند.

نحوه‌ی افزودن مهاجرت جدید (برای آینده):
    1. یک تابع `_migration_N_xxx(conn)` بنویسید؛ فقط یک آرگومان
       sqlite3.Connection می‌گیرد و باید idempotent باشد (از
       add_column_if_missing و create_index_if_missing استفاده کنید).
    2. در انتهای لیست MIGRATIONS اضافه کنید:
           (N, "توضیح کوتاه", _migration_N_xxx)
    3. اگر ستون/جدول جدیدی می‌آید، همان را در CREATE TABLE داخل
       db_manager هم اضافه کنید (برای دیتابیس‌های تازه)؛ مهاجرت برای
       دیتابیس‌های قدیمیِ نصب‌شده است.
    LATEST_VERSION به‌صورت خودکار از طول لیست محاسبه می‌شود.
"""
import sqlite3
import time
import traceback
from datetime import datetime
from pathlib import Path

from config import DB_PATH, BACKUP_DIR

# تعداد پشتیبان‌های «پیش از مهاجرت» که نگه داشته می‌شود
PRE_MIGRATION_BACKUPS_TO_KEEP = 10


class MigrationError(Exception):
    """خطای اجرای مهاجرت دیتابیس"""


# ─────────────────────────── ابزارهای کمکی idempotent ───────────────────────────

def table_exists(conn, table):
    """آیا جدول در دیتابیس وجود دارد؟"""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()
    return row is not None


def get_columns(conn, table):
    """لیست نام ستون‌های جدول"""
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def add_column_if_missing(conn, table, column, decl):
    """
    افزودن ستون به جدول فقط اگر جدول و ستون وجود داشته باشند/نداشته باشند.
    decl: تعریف ستون مثل "BOOLEAN DEFAULT 0" (باید default ثابت باشد؛
    SQLite اجازه‌ی default غیرثابت مثل datetime('now') در ADD COLUMN را نمی‌دهد).
    """
    if not table_exists(conn, table):
        return
    if column not in get_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def create_index_if_missing(conn, index_name, table, columns, unique=False):
    """ساخت ایندکس فقط اگر جدول وجود داشته باشد (IF NOT EXISTS خودش idempotent است)"""
    if not table_exists(conn, table):
        return
    unique_sql = "UNIQUE " if unique else ""
    conn.execute(
        f"CREATE {unique_sql}INDEX IF NOT EXISTS {index_name} ON {table} ({columns})"
    )


# ─────────────────────────── مهاجرت‌ها ───────────────────────────

def _migration_1_baseline(conn):
    """
    نسخه ۰ → ۱: هم‌ترازسازی دیتابیس‌های نصب‌شده‌ی قدیمی با ساختار برنامه ۱.۰.x
    - افزودن ستون‌هایی که کد فعلی انتظار دارد در صورت نبود
      (نصب‌های قدیمی‌تر ممکن است این ستون‌ها را نداشته باشند)
    - ساخت ایندکس‌های پرکاربرد جستجو/گزارش‌ها/داشبورد
    همه‌ی عملیات idempotent است و به داده‌های موجود دست نمی‌زند.
    """
    # ── ستون‌های احتمالاً فاقد در نصب‌های قدیمی‌تر ──
    add_column_if_missing(conn, "companies", "has_certificate", "BOOLEAN DEFAULT 0")
    add_column_if_missing(conn, "exit_items", "certificate_id", "INTEGER")
    add_column_if_missing(conn, "exit_items", "is_debt", "BOOLEAN DEFAULT 0")
    add_column_if_missing(conn, "exit_items", "debt_settled", "BOOLEAN DEFAULT 0")
    add_column_if_missing(conn, "exit_permits", "destination", "TEXT")
    add_column_if_missing(conn, "exit_permits", "customs_representative", "TEXT")
    add_column_if_missing(conn, "exit_permits", "notes", "TEXT")
    add_column_if_missing(conn, "certificates", "issue_date", "TEXT")
    add_column_if_missing(conn, "certificates", "status", "TEXT DEFAULT 'active'")
    add_column_if_missing(conn, "scanned_documents", "page_number", "INTEGER DEFAULT 1")
    add_column_if_missing(conn, "backups", "file_path", "TEXT")
    add_column_if_missing(conn, "backups", "status", "TEXT DEFAULT 'success'")

    # ── ایندکس‌ها (سرعت بخشیدن به جستجو، گزارش‌ها و داشبورد) ──
    create_index_if_missing(conn, "idx_exit_permits_company", "exit_permits", "company_id")
    create_index_if_missing(conn, "idx_exit_permits_exit_date", "exit_permits", "exit_date")
    create_index_if_missing(conn, "idx_exit_items_permit", "exit_items", "exit_permit_id")
    create_index_if_missing(conn, "idx_exit_items_certificate", "exit_items", "certificate_id")
    create_index_if_missing(conn, "idx_exit_items_debt", "exit_items", "is_debt, debt_settled")
    create_index_if_missing(conn, "idx_certificates_company_status", "certificates", "company_id, status")
    create_index_if_missing(conn, "idx_scanned_documents_permit", "scanned_documents", "exit_permit_id")


def _migration_2_uniqueness(conn):
    """
    نسخه ۱ → ۲: قید یکتایی در سطح دیتابیس
    - نام شرکت یکتا (قبلاً UNIQUE نبود؛ فقط چک UI داشت)
    - شماره گواهی یکتا به‌ازای شرکت
    اگر داده‌ی تکراری موجود باشد، مهاجرت شکست می‌خورد و rollback می‌شود؛
    کاربر باید تکراری‌ها را اول ادغام کند (پیام خطا نام رکورد را نشان می‌دهد).
    """
    if table_exists(conn, "companies"):
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_name ON companies(name)"
        )
    if table_exists(conn, "certificates"):
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_certificates_number "
            "ON certificates(company_id, certificate_number)"
        )
    # بهبود همروندی (پایه‌ی چند-کاربره آینده): حالت WAL
    # WAL خارج از تراکنش اعمال می‌شود و idempotent است.
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        pass  # روی برخی فایل‌سیستم‌های شبکه‌ای WAL پشتیبانی نمی‌شود — ignor


def _migration_3_certificate_expiry(conn):
    """
    نسخه ۲ → ۳: تاریخ انقضای گواهی تولید
    - ستون expiry_date (شمسی، اختیاری) به جدول certificates
    - گواهی منقض‌شده در سرویس سهمیه (quota) به‌عنوان گواهی فعال پذیرفته نمی‌شود
      و در داشبورد نزدیک انقضا هشدار می‌دهد.
    idempotent: ستون فقط اگر نبود اضافه می‌شود.
    """
    add_column_if_missing(conn, "certificates", "expiry_date", "TEXT")
    create_index_if_missing(conn, "idx_certificates_expiry", "certificates", "expiry_date")


# لیست مهاجرت‌ها — فقط در انتها اضافه کنید؛ شماره‌ها باید پشت‌سرهم باشند
MIGRATIONS = [
    (1, "هم‌ترازسازی پایه: ستون‌های لازم + ایندکس‌ها", _migration_1_baseline),
    (2, "قید یکتایی نام شرکت/شماره گواهی + حالت WAL", _migration_2_uniqueness),
    (3, "تاریخ انقضای گواهی تولید", _migration_3_certificate_expiry),
]

# بالاترین نسخه‌ی ساختاری که این نسخه از برنامه می‌شناسد
LATEST_VERSION = MIGRATIONS[-1][0] if MIGRATIONS else 0


# ─────────────────────────── موتور اجرا ───────────────────────────

def get_schema_version(conn):
    """خواندن نسخه‌ی فعلی دیتابیس از PRAGMA user_version"""
    return conn.execute("PRAGMA user_version").fetchone()[0]


def is_fresh_database(db_path):
    """
    آیا این یک دیتابیس تازه‌ساخت (بدون هیچ جدولی) است؟
    دیتابیس تازه با CREATE TABLE کاملِ همین نسخه ساخته می‌شود و نیازی
    به اجرای مهاجرت‌ها و گرفتن پشتیبان ندارد.
    """
    if not Path(db_path).exists():
        return True
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone()
        return row is None
    finally:
        conn.close()


def mark_schema_version(db_path, version):
    """ثبت دستی شماره‌ی نسخه (برای دیتابیس تازه که با آخرین ساختار ساخته شده)"""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(f"PRAGMA user_version = {int(version)}")
        conn.commit()
    finally:
        conn.close()


def get_current_schema_version(db_path=None):
    """نسخه‌ی فعلی ساختار دیتابیس (برای نمایش در UI و ابزارهای جانبی)"""
    path = str(db_path) if db_path else str(DB_PATH)
    conn = sqlite3.connect(path)
    try:
        return get_schema_version(conn)
    finally:
        conn.close()


def get_last_migration_info():
    """
    آخرین رویداد موفق مهاجرت از data/migrations.log — برای نمایش در UI.
    خروجی: رشته‌ی توضیحی یا None اگر هنوز مهاجرتی اجرا نشده باشد.
    """
    log_file = _log_path()
    try:
        if not log_file.exists():
            return None
        with open(log_file, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if "✓ مهاجرت" in ln]
        return lines[-1] if lines else None
    except OSError:
        return None


def _log_path():
    return DB_PATH.parent / "migrations.log"


def _log(message):
    """ثبت رویداد در کنسول و فایل data/migrations.log"""
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    try:
        print(line)
    except Exception:
        pass  # در حالت EXE بدون کنسول، stdout ممکن است None باشد
    try:
        _log_path().parent.mkdir(parents=True, exist_ok=True)
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _pre_migration_backup(db_path, from_version):
    """
    پشتیبان امن از خود فایل دیتابیس، پیش از هر مهاجرت (sqlite backup API
    سازگار با اتصال‌های باز و WAL). در backups/pre_migration نگهداری و
    فقط PRE_MIGRATION_BACKUPS_TO_KEEP نسخه‌ی آخر حفظ می‌شود.
    """
    backup_dir = Path(BACKUP_DIR) / "pre_migration"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"pre_migration_v{from_version}_{stamp}.db"

    src = sqlite3.connect(str(db_path))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    # نگهداری فقط آخرین نسخه‌ها
    backups = sorted(backup_dir.glob("pre_migration_v*_*.db"))
    for old in backups[:-PRE_MIGRATION_BACKUPS_TO_KEEP]:
        try:
            old.unlink()
        except OSError:
            pass

    return dest


def run_migrations(db_path=None):
    """
    اجرای همه‌ی مهاجرت‌های در انتظار روی دیتابیس.

    خروجی: (نسخه‌ی قبلی، نسخه‌ی فعلی، تعداد مهاجرت‌های اجراشده)
    در صورت هر خطا MigrationError پرتاب می‌شود و دیتابیس دست‌نخورده
    (rollback شده) باقی می‌ماند.
    """
    path = str(db_path) if db_path else str(DB_PATH)
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, timeout=10)
    conn.isolation_level = None  # کنترل دستی تراکنش‌ها (BEGIN/COMMIT صریح)
    try:
        try:
            current = get_schema_version(conn)
        except sqlite3.DatabaseError as e:
            raise MigrationError(
                f"خواندن نسخه‌ی دیتابیس ممکن نشد؛ فایل ممکن است خراب باشد: {e}"
            ) from e

        if current == LATEST_VERSION:
            return current, current, 0

        if current > LATEST_VERSION:
            # downgrade: دیتابیس متعلق به نسخه‌ی جدیدتری از برنامه است؛
            # اجرای کد قدیمی روی ساختار جدید خطر خرابی داده دارد.
            msg = (
                f"نسخه‌ی دیتابیس ({current}) جدیدتر از نسخه‌ی پشتیبانی‌شده‌ی "
                f"این برنامه ({LATEST_VERSION}) است. لطفاً نسخه‌ی جدیدتر "
                f"برنامه را اجرا کنید. دیتابیس تغییر نکرد."
            )
            _log(f"✗ مهاجرت انجام نشد: {msg}")
            raise MigrationError(msg)

        # ── پشتیبان امن پیش از مهاجرت — بدون پشتیبان مهاجرت نمی‌کنیم ──
        try:
            backup_file = _pre_migration_backup(path, current)
        except Exception as e:
            raise MigrationError(
                f"ساخت پشتیبان پیش از مهاجرت ناموفق بود: {e}\n"
                f"دیتابیس تغییر نکرد."
            ) from e

        _log(
            f"شروع مهاجرت: نسخه {current} → {LATEST_VERSION} "
            f"(پشتیبان: {backup_file.name})"
        )

        applied = 0
        for version, description, func in MIGRATIONS:
            if version <= current:
                continue

            started = time.perf_counter()
            try:
                conn.execute("BEGIN IMMEDIATE")
                func(conn)
                # user_version داخل همان تراکنش ثبت می‌شود (اتمیک با مهاجرت)
                conn.execute(f"PRAGMA user_version = {version}")
                conn.execute("COMMIT")
            except Exception as e:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                _log(f"✗ مهاجرت {version} ناموفق بود: {e}")
                _log(traceback.format_exc())
                raise MigrationError(
                    f"مهاجرت نسخه {version} ({description}) ناموفق بود: {e}\n"
                    f"دیتابیس به حالت قبل برگشت. پشتیبان: {backup_file}"
                ) from e

            duration = (time.perf_counter() - started) * 1000
            _log(f"✓ مهاجرت {version} اجرا شد: {description} ({duration:.0f}ms)")
            applied += 1

        final = get_schema_version(conn)
        return current, final, applied
    finally:
        conn.close()
