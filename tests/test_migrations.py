"""
تست مکانیزم مهاجرت دیتابیس — اجرا: python tests/test_migrations.py
بدون نیاز به pytest؛ همه‌ی سناریوها روی دیتابیس موقت اجرا می‌شوند.
"""
import os
import sys
import sqlite3
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

passed = []


def check(name):
    def deco(fn):
        def wrapper():
            try:
                fn()
            except Exception as e:
                print(f"✗ {name}: {e}")
                raise
            passed.append(name)
            print(f"✓ {name}")
        return wrapper
    return deco


# ── ساخت محیط موقت و پچ config پیش از هر ایمپورتِ وابسته به دیتابیس ──
tmp = tempfile.mkdtemp()
test_db = os.path.join(tmp, "test.db")

import config  # noqa: E402
config.DB_PATH = Path(test_db)
config.BACKUP_DIR = Path(tmp) / "backups"
config.ensure_directories()


def make_old_db(path):
    """دیتابیس قدیمیِ نصب‌شده: بدون user_version، بدون ستون‌های جدید"""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            economic_code TEXT,
            phone TEXT,
            ceo_name TEXT,
            representative_name TEXT,
            created_at TEXT
        );
        CREATE TABLE units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            certificate_number TEXT NOT NULL,
            product_type TEXT NOT NULL,
            total_amount REAL NOT NULL,
            remaining_amount REAL NOT NULL,
            unit_id INTEGER NOT NULL,
            created_at TEXT
        );
        CREATE TABLE exit_permits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            permit_number TEXT NOT NULL UNIQUE,
            company_id INTEGER NOT NULL,
            exit_date TEXT NOT NULL,
            created_at TEXT
        );
        CREATE TABLE exit_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exit_permit_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            amount REAL NOT NULL,
            unit_id INTEGER NOT NULL,
            created_at TEXT
        );
        CREATE TABLE scanned_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exit_permit_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            created_at TEXT
        );
        CREATE TABLE settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT
        );
        CREATE TABLE backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            created_at TEXT
        );
    """)
    conn.execute("INSERT INTO companies (name) VALUES ('شرکت تست')")
    conn.commit()
    conn.close()


# دیتابیس قدیمی باید «قبل از» ایمپورتِ db_manager ساخته شود، چون
# نمونه‌ی سراسری db هنگام ایمپورت ساخته می‌شود.
make_old_db(test_db)

import database.migrations as mig  # noqa: E402
import database.db_manager as dbm  # noqa: E402


@check("سناریو A: مهاجرت دیتابیس قدیمی — ستون‌ها اضافه، داده حفظ، ایندکس ساخته شد")
def scenario_a():
    v = sqlite3.connect(test_db).execute("PRAGMA user_version").fetchone()[0]
    assert v == mig.LATEST_VERSION, f"expected {mig.LATEST_VERSION}, got {v}"

    cols = [r[1] for r in sqlite3.connect(test_db).execute("PRAGMA table_info(exit_items)")]
    for c in ["certificate_id", "is_debt", "debt_settled"]:
        assert c in cols, f"missing column {c}"

    name = sqlite3.connect(test_db).execute("SELECT name FROM companies").fetchone()[0]
    assert name == "شرکت تست", "داده‌های موجود نباید تغییر کنند"

    idx = [r[0] for r in sqlite3.connect(test_db).execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )]
    assert idx, "ایندکس‌ها ساخته نشدند"

    bk = Path(config.BACKUP_DIR) / "pre_migration"
    assert bk.is_dir() and list(bk.iterdir()), "پشتیبان پیش از مهاجرت گرفته نشد"


@check("سناریو B: اجرای دوباره idempotent است (نسخه ثابت، پشتیبان تکراری نمی‌سازد)")
def scenario_b():
    bk = Path(config.BACKUP_DIR) / "pre_migration"
    before = sorted(p.name for p in bk.iterdir())
    dbm.DatabaseManager(db_path=test_db)
    v = sqlite3.connect(test_db).execute("PRAGMA user_version").fetchone()[0]
    assert v == mig.LATEST_VERSION
    after = sorted(p.name for p in bk.iterdir())
    assert before == after, "پشتیبان تکراری ساخته شد"


@check("سناریو C: دیتابیس تازه مستقیم با آخرین نسخه ساخته می‌شود (بدون مهاجرت/پشتیبان)")
def scenario_c():
    fresh = os.path.join(tmp, "fresh.db")
    dbm.DatabaseManager(db_path=fresh)
    v = sqlite3.connect(fresh).execute("PRAGMA user_version").fetchone()[0]
    assert v == mig.LATEST_VERSION, f"fresh DB at v{v}, expected {mig.LATEST_VERSION}"
    tables = [r[0] for r in sqlite3.connect(fresh).execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )]
    expected = {"companies", "units", "certificates", "exit_permits",
                "exit_items", "scanned_documents", "settings", "backups"}
    assert expected <= set(tables), f"missing tables: {expected - set(tables)}"


@check("سناریو D: گارد downgrade — دیتابیس جدیدتر از برنامه، مهاجرت نمی‌شود")
def scenario_d():
    conn = sqlite3.connect(test_db)
    conn.execute(f"PRAGMA user_version = {mig.LATEST_VERSION + 5}")
    conn.commit()
    conn.close()
    try:
        dbm.DatabaseManager(db_path=test_db)
    except mig.MigrationError:
        pass  # رفتار مورد انتظار
    else:
        raise AssertionError("downgrade نباید بی‌صدا رد شود")


@check("سناریو E: مهاجرت ناموفق → rollback اتمیک (ستون و نسخه برمی‌گردند)")
def scenario_e():
    # نسخه را روی ۱ می‌گذاریم تا فقط مهاجرتِ شکست‌خورده اجرا شود
    conn = sqlite3.connect(test_db)
    conn.execute(f"PRAGMA user_version = {mig.LATEST_VERSION}")
    conn.commit()
    conn.close()

    def boom(conn_):
        conn_.execute("ALTER TABLE companies ADD COLUMN will_fail TEXT")
        raise RuntimeError("boom")

    bad_version = mig.LATEST_VERSION + 98
    mig.MIGRATIONS.append((bad_version, "bad", boom))
    old_latest = mig.LATEST_VERSION
    mig.LATEST_VERSION = bad_version  # وگرنه run_migrations زودتر خارج می‌شود
    try:
        mig.run_migrations(test_db)
        raise AssertionError("باید MigrationError پرتاب می‌شد")
    except mig.MigrationError:
        pass
    finally:
        mig.MIGRATIONS.pop()
        mig.LATEST_VERSION = old_latest

    v = sqlite3.connect(test_db).execute("PRAGMA user_version").fetchone()[0]
    assert v == mig.LATEST_VERSION, "نسخه باید روی حالت قبل (rollback) بماند"
    cols = [r[1] for r in sqlite3.connect(test_db).execute("PRAGMA table_info(companies)")]
    assert "will_fail" not in cols, "ALTER TABLE باید rollback شده باشد"


@check("سناریو F: رویدادهای مهاجرت در data/migrations.log ثبت می‌شوند")
def scenario_f():
    log = Path(test_db).parent / "migrations.log"
    assert log.exists(), "فایل لاگ ساخته نشد"
    content = log.read_text(encoding="utf-8")
    assert "مهاجرت 1" in content


for fn in [scenario_a, scenario_b, scenario_c, scenario_d, scenario_e, scenario_f]:
    fn()

shutil.rmtree(tmp, ignore_errors=True)
print(f"\nهمه‌ی {len(passed)} سناریو با موفقیت پاس شد ✓")
