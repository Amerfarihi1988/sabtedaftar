"""
داده‌های اولیه (واحدها و تنظیمات پیش‌فرض)
"""
from database.db_manager import db
from services.numbering import seed_year_state


def seed_units():
    """ثبت واحدهای پرکاربرد"""
    units = [
        "لیتر",
        "کیلوگرم",
        "تن",
        "دستگاه",
        "متر",
        "متر مربع",
        "متر مکعب",
        "عدد",
        "جعبه",
        "کارتن",
        "پالت",
        "گالن",
    ]
    for unit in units:
        db.execute(
            "INSERT OR IGNORE INTO units (name) VALUES (?)",
            (unit,)
        )


def seed_settings():
    """ثبت تنظیمات پیش‌فرض"""
    defaults = {
        "last_permit_number": "0",
        "auto_backup": "1",  # پشتیبان‌گیری خودکار روزانه به‌صورت پیش‌فرض فعال
        "printer_name": "",
    }
    for key, value in defaults.items():
        db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )


def run_seed():
    """اجرای تمام داده‌های اولیه"""
    seed_units()
    seed_settings()
    seed_year_state()
    print("✓ داده‌های اولیه ثبت شدند")


if __name__ == "__main__":
    run_seed()