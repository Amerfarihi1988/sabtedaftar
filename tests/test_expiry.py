"""
تست انقضای گواهی و پیش‌بینی اتمام — اجرا: python tests/test_expiry.py
همه‌ی سناریوها روی دیتابیس موقت اجرا می‌شوند.
"""
import os
import sys
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
                print(f"FAIL {name}: {e}")
                raise
            passed.append(name)
            print(f"OK {name}")
        return wrapper
    return deco


# ── محیط موقت قبل از ایمپورت ماژول‌های وابسته به دیتابیس ──
tmp = tempfile.mkdtemp()
test_db = os.path.join(tmp, "test.db")

import config  # noqa: E402
config.DB_PATH = Path(test_db)
config.BACKUP_DIR = Path(tmp) / "backups"
config.ensure_directories()

import jdatetime  # noqa: E402
from database.db_manager import db  # noqa: E402
from services.quota import (  # noqa: E402
    cert_expiry_status, is_cert_expired, is_expiring_soon,
    forecast_certificate_exhaustion, get_active_certificate,
    get_expiring_certificates,
)

# داده‌ی پایه
db.execute("INSERT INTO companies (name, has_certificate) VALUES ('شرکت الف', 1)")
db.execute("INSERT INTO companies (name, has_certificate) VALUES ('شرکت ب', 1)")
company_a = db.fetch_one("SELECT id FROM companies WHERE name='شرکت الف'")["id"]
company_b = db.fetch_one("SELECT id FROM companies WHERE name='شرکت ب'")["id"]
db.execute("INSERT INTO units (name) VALUES ('لیتر')")
unit = db.fetch_one("SELECT id FROM units WHERE name='لیتر'")["id"]

today = jdatetime.date.today()


def dstr(d):
    return d.strftime("%Y/%m/%d")


@check("T1: گواهی بدون انقضا — هرگز منقض نمی‌شود")
def t1():
    cert = {"expiry_date": None}
    expired, days = cert_expiry_status(cert)
    assert not expired and days is None
    assert not is_cert_expired(cert)
    assert not is_expiring_soon(cert)


@check("T2: گواهی منقض‌شده شناسایی می‌شود")
def t2():
    from jdatetime import date as jdate
    past_date = jdate.fromordinal(today.toordinal() - 15)
    cert = {"expiry_date": dstr(past_date)}
    expired, days = cert_expiry_status(cert)
    assert expired, "باید منقض تشخیص داده شود"
    assert days < 0
    assert is_cert_expired(cert)


@check("T3: گواهی نزدیک به انقضا (۱۵ روز) — expiring_soon اما نه منقض")
def t3():
    from jdatetime import date as jdate
    near = jdate.fromordinal(today.toordinal() + 15)
    cert = {"expiry_date": dstr(near)}
    assert not is_cert_expired(cert)
    assert is_expiring_soon(cert, days=30)
    assert not is_expiring_soon(cert, days=7)  # خارج از آستانه‌ی ۷ روزه


@check("T4: get_active_certificate گواهی منقض را نمی‌پذیرد")
def t4():
    past = today.toordinal() - 10
    from jdatetime import date as jdate
    past_date = jdate.fromordinal(past)
    db.execute(
        """INSERT INTO certificates
           (company_id, certificate_number, product_type, total_amount,
            remaining_amount, unit_id, status, expiry_date)
           VALUES (?, 'EXP-1', 'پریمیم', 100, 100, ?, 'active', ?)""",
        (company_a, unit, dstr(past_date))
    )
    assert get_active_certificate(company_a) is None, \
        "گواهی منقض نباید به‌عنوان فعال برگردد"


@check("T5: اولویت مصرف — گواهی با انقضای نزدیک‌تر قبل از بدون‌انقضا")
def t5():
    # شرکت ب: یک گواهی بدون انقضا (قدیمی) و یکی با انقضای ۶۰ روزه
    from jdatetime import date as jdate
    near = jdate.fromordinal(today.toordinal() + 60)
    db.execute(
        """INSERT INTO certificates
           (company_id, certificate_number, product_type, total_amount,
            remaining_amount, unit_id, status)
           VALUES (?, 'NOEXP-1', 'پریمیم', 100, 100, ?, 'active')""",
        (company_b, unit)
    )
    noexp_id = db.fetch_one("SELECT id FROM certificates WHERE certificate_number='NOEXP-1'")["id"]
    db.execute(
        """INSERT INTO certificates
           (company_id, certificate_number, product_type, total_amount,
            remaining_amount, unit_id, status, expiry_date)
           VALUES (?, 'EXP-2', 'پریمیم', 100, 100, ?, 'active', ?)""",
        (company_b, unit, dstr(near))
    )
    active = get_active_certificate(company_b)
    assert active["certificate_number"] == "EXP-2", \
        f"گواهی با انقضای نزدیک‌تر باید اول مصرف شود، برگشت: {active['certificate_number']}"
    # اگر EXP-2 منقض شود، NOEXP-1 (بدون انقضا) برمی‌گردد
    db.execute("UPDATE certificates SET expiry_date='1370/01/01' WHERE certificate_number='EXP-2'")
    active2 = get_active_certificate(company_b)
    assert active2["certificate_number"] == "NOEXP-1", \
        "بعد از انقضای EXP-2، گواهی بدون انقضا باید برگردد"


@check("T6: forecast با مصرف ماهانه — months_left و تاریخ تخمینی")
def t6():
    # شرکت الف: گواهی جدید ۲۰۰ لیتری بدون انقضا
    db.execute(
        """INSERT INTO certificates
           (company_id, certificate_number, product_type, total_amount,
            remaining_amount, unit_id, status)
           VALUES (?, 'FC-1', 'پریمیم', 200, 200, ?, 'active')""",
        (company_a, unit)
    )
    cert = get_active_certificate(company_a)
    # مصرف ماهانه: ۱۰ لیتر در ماه جاری
    m = today.strftime("%Y/%m")
    ep1 = db.execute(
        "INSERT INTO exit_permits (permit_number, company_id, exit_date) VALUES ('1405/901', ?, ?)",
        (company_a, f"{m}/05")
    )
    db.execute(
        "INSERT INTO exit_items (exit_permit_id, product_name, amount, unit_id, certificate_id) VALUES (?, 'کالا', 10, ?, ?)",
        (ep1, unit, cert["id"])
    )
    # یک ماه قبل هم ۱۰ لیتر
    prev_year, prev_month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    ep2 = db.execute(
        "INSERT INTO exit_permits (permit_number, company_id, exit_date) VALUES ('1405/902', ?, ?)",
        (company_a, f"{prev_year}/{prev_month:02d}/10")
    )
    db.execute(
        "INSERT INTO exit_items (exit_permit_id, product_name, amount, unit_id, certificate_id) VALUES (?, 'کالا', 10, ?, ?)",
        (ep2, unit, cert["id"])
    )

    fc = forecast_certificate_exhaustion(cert)
    assert fc["monthly_avg"] == 10.0, f"میانگین باید ۱۰ باشد، شد {fc['monthly_avg']}"
    # باقیمانده 190 → 19 ماه
    assert fc["months_left"] is not None and 18 <= fc["months_left"] <= 20, \
        f"months_left غلط: {fc['months_left']}"
    assert fc["exhaustion_date"], "تاریخ تخمینی نباید None باشد"


@check("T7: get_expiring_certificates — فقط منقض/نزدیک‌ها، منقض اول")
def t7():
    result = get_expiring_certificates(days=30)
    # باید شامل EXP-1 و EXP-2 (هر دو منقض) باشد — نه FC-1/NOEXP-1 (بدون انقضا)
    numbers = [c["certificate_number"] for c in result]
    assert "EXP-1" in numbers and "EXP-2" in numbers, f"گواهی‌های منقض باید باشند: {numbers}"
    assert all(c["expiry_date"] is not None for c in result)
    # منقض‌شده‌ها اول
    if len(result) >= 2:
        assert result[0]["days_to_expiry"] <= result[-1]["days_to_expiry"]


@check("T8: مهاجرت ۳ روی دیتابیس قدیمیِ فاقد expiry_date — idempotent")
def t8():
    import sqlite3
    # دیتابیس قدیمی بدون ستون expiry_date
    old_db = os.path.join(tmp, "old_v2.db")
    conn = sqlite3.connect(old_db)
    conn.executescript("""
        CREATE TABLE companies (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE certificates (
            id INTEGER PRIMARY KEY,
            company_id INTEGER NOT NULL,
            certificate_number TEXT NOT NULL,
            product_type TEXT NOT NULL,
            total_amount REAL NOT NULL,
            remaining_amount REAL NOT NULL,
            unit_id INTEGER NOT NULL,
            issue_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT
        );
        PRAGMA user_version = 2;
    """)
    conn.commit()
    conn.close()

    import database.migrations as mig
    mig.run_migrations(old_db)

    cols = [r[1] for r in sqlite3.connect(old_db).execute("PRAGMA table_info(certificates)")]
    assert "expiry_date" in cols, "ستون expiry_date اضافه نشد"
    v = sqlite3.connect(old_db).execute("PRAGMA user_version").fetchone()[0]
    assert v == mig.LATEST_VERSION, f"نسخه باید {mig.LATEST_VERSION} باشد، شد {v}"

    # idempotent: اجرای دوباره
    mig.run_migrations(old_db)
    v2 = sqlite3.connect(old_db).execute("PRAGMA user_version").fetchone()[0]
    assert v2 == mig.LATEST_VERSION


for fn in [t1, t2, t3, t4, t5, t6, t7, t8]:
    fn()

shutil.rmtree(tmp, ignore_errors=True)
print(f"\nAll {len(passed)} expiry tests passed")
