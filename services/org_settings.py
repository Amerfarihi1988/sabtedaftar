"""
تنظیمات سازمان برای سربرگ چاپ — منبع واحد خواندن از جدول settings

عنوان سازمان و لوگو در تب تنظیمات عمومی ثبت می‌شود و در روبرگه
«خروج بلامانع» و همه‌ی گزارش‌های PDF به‌صورت سربرگ رسمی می‌آید.
"""
from database.db_manager import db

_cache = {}


def get_org_title():
    """عنوان سازمان ثبت‌شده — یا نام پیش‌فرض برنامه اگر ثبت نشده باشد"""
    if "title" not in _cache:
        try:
            rec = db.fetch_one("SELECT value FROM settings WHERE key='org_title'")
            title = (rec["value"] or "").strip() if rec else ""
            _cache["title"] = title
        except Exception:
            _cache["title"] = ""
    return _cache["title"] or None


def get_org_logo_path():
    """مسیر لوگو — فقط اگر فایل واقعاً موجود باشد"""
    if "logo" not in _cache:
        import os
        try:
            rec = db.fetch_one("SELECT value FROM settings WHERE key='org_logo_path'")
            path = (rec["value"] or "").strip() if rec else ""
            _cache["logo"] = path if path and os.path.exists(path) else None
        except Exception:
            _cache["logo"] = None
    return _cache["logo"]


def clear_cache():
    """پس از ذخیره تنظیمات کش خالی می‌شود تا چاپ بعدی مقادیر جدید بگیرد"""
    _cache.clear()
