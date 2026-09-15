"""
شماره‌گذاری خودکار مجوز خروج — با ریست سالانه

منطق:
- شمارنده `last_permit_number` و سال `current_year` در جدول settings نگهداری می‌شوند.
- با ورود سال شمسی جدید، اولین مجوز سال دوباره از ۰۰۱ شروع می‌شود.
- شمارنده فقط داخل تراکنشِ ثبت مجوز افزایش می‌یابد؛ اگر ثبت rollback شود،
  شمارنده هم rollback می‌شود و شماره‌ای نمی‌سوزد.
"""
import jdatetime
from config import PERMIT_NUMBER_FORMAT
from database.db_manager import db


def _read_state(tx_or_db):
    """خواندن (سال ذخیره‌شده، شمارنده فعلی)"""
    row_year = tx_or_db.fetch_one("SELECT value FROM settings WHERE key='current_year'")
    row_num = tx_or_db.fetch_one("SELECT value FROM settings WHERE key='last_permit_number'")
    saved_year = int(row_year["value"]) if row_year and row_year["value"] else None
    last_num = int(row_num["value"]) if row_num and row_num["value"] else 0
    return saved_year, last_num


def _write_state_tx(tx, year, num):
    """نوشتن (سال، شمارنده) داخل تراکنشِ باز"""
    tx.execute(
        "INSERT INTO settings (key, value) VALUES ('current_year', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(year),)
    )
    tx.execute(
        "INSERT INTO settings (key, value) VALUES ('last_permit_number', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(num),)
    )


def _format(year, num):
    return PERMIT_NUMBER_FORMAT.format(year=year, number=num)


def generate_permit_number_in_tx(tx):
    """
    تولید شماره جدید — فقط داخل تراکنشِ بازِ ثبت مجوز.
    این تنها نقطه‌ی افزایش شمارنده در کل برنامه است.
    با ورود سال جدید، شمارنده ریست و سال ذخیره‌شده به‌روزرسانی می‌شود
    (همه در همان تراکنش؛ در صورت rollback هیچ‌چیز تغییر نمی‌کند).
    """
    year = jdatetime.date.today().year
    saved_year, last_num = _read_state(tx)

    if saved_year != year:
        # سال جدید → شروع از ۰۰۱
        new_num = 1
    else:
        new_num = last_num + 1

    _write_state_tx(tx, year, new_num)
    return _format(year, new_num)


def get_next_number_preview():
    """پیش‌نمایش شماره بعدی بدون هیچ نوشتنی در دیتابیس"""
    year = jdatetime.date.today().year
    saved_year, last_num = _read_state(db)

    if saved_year != year:
        new_num = 1
    else:
        new_num = last_num + 1

    return _format(year, new_num)


def seed_year_state():
    """
    مقداردهی اولیه‌ی `current_year` هنگام اجرای برنامه (seed).
    اگر تنظیم نباشد، سال فعلی ثبت می‌شود بدون دست‌زدن به شمارنده.
    """
    year = jdatetime.date.today().year
    saved_year, _ = _read_state(db)
    if saved_year is None:
        db.execute(
            "INSERT INTO settings (key, value) VALUES ('current_year', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(year),)
        )
