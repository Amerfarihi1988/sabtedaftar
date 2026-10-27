"""
ضریب تبدیل واحدها به «واحد پایه» — مبنای جمع ناهم‌واحد در نمودارها

چرا لازم است؟
    جدول exit_items مقدار را با واحدهای مختلف ثبت می‌کند (تن، کیلوگرم، عدد، ...).
    جمع مستقیم SUM(ei.amount) در نمودارها مقدارهای ناهم‌واحد را با هم جمع می‌کند
    که معنی فیزیکی ندارد (۵ تن + ۳ کیلوگرم ≠ ۸). برای تحلیل نموداری، مقدارها به
    «واحد پایه‌ی خانواده‌ی خودشان» تبدیل و فقط هم‌خانواده‌ها با هم جمع می‌شوند.

خانواده‌ها:
    وزن  → واحد پایه: کیلوگرم
    حجم  → واحد پایه: لیتر
    طول  → واحد پایه: متر
    شمارش → واحد پایه: عدد (بسته/جعبه/کارتن/پالت بدون فکتور قطعی — بی‌فکتور)

منبع واحد حقیقت: جدول units فقط «نام» دارد؛ فکتورها قرارداد همین ماژول‌اند.
نام‌های ناشناخته بی‌فکتور می‌مانند (is_mass/null) و در نمودارها جداگانه می‌آیند.
"""
import sqlite3

from database.db_manager import db

# ── خانواده‌ی وزن: پایه = کیلوگرم ──
WEIGHT = {
    "کیلوگرم": 1.0,
    "گرم": 0.001,
    "تن": 1000.0,
}

# ── خانواده‌ی حجم: پایه = لیتر ──
VOLUME = {
    "لیتر": 1.0,
    "گالن": 3.785,
    "متر مکعب": 1000.0,
}

# ── خانواده‌ی طول: پایه = متر ──
LENGTH = {
    "متر": 1.0,
    "سانتی‌متر": 0.01,
    "کیلومتر": 1000.0,
}

# ── واحدهای شمارشی: بدون فکتور قطعی (هر «جعبه» محتوای متفاوتی دارد) ──
COUNT_UNITS = {"عدد", "دستگاه", "جعبه", "کارتن", "پالت", "بسته"}

# واحد نمایش برای هر خانواده
DISPLAY_UNIT = {
    "weight": "کیلوگرم",
    "volume": "لیتر",
    "length": "متر",
    "count": "عدد",
}

ALL_FACTORS = {**WEIGHT, **VOLUME, **LENGTH}

_cache = None  # {name: (family, factor)} — factor=None یعنی بی‌فکتور


def _load_factors():
    """کش نام واحد → (خانواده، فکتور) از جدول units"""
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    try:
        rows = db.fetch_all("SELECT id, name FROM units")
    except sqlite3.Error:
        rows = []
    for r in rows:
        name = str(r["name"] or "").strip()
        if not name:
            continue
        if name in WEIGHT:
            _cache[name] = ("weight", WEIGHT[name])
        elif name in VOLUME:
            _cache[name] = ("volume", VOLUME[name])
        elif name in LENGTH:
            _cache[name] = ("length", LENGTH[name])
        elif name in COUNT_UNITS:
            _cache[name] = ("count", None)  # شمارش = بی‌فکتور
        else:
            _cache[name] = (None, None)     # ناشناخته = بی‌فکتور
    return _cache


def clear_cache():
    """پس از افزودن واحد جدید کش خالی می‌شود"""
    global _cache
    _cache = None


def unit_info(unit_name):
    """(خانواده، فکتور) برای نام واحد — ناشناخته = (None, None)"""
    return _load_factors().get(str(unit_name or "").strip(), (None, None))


def unit_family_names(family):
    """نام‌های واحد ثبت‌شده در جدول units که به این خانواده تعلق دارند"""
    family = str(family or "").strip()
    if not family:
        return []
    return [name for name, (fam, _) in _load_factors().items()
            if fam == family]


def to_base(amount, unit_name):
    """مقدار به واحد پایه‌ی خانواده؛ بی‌فکتور = None (نمی‌توان تبدیل کرد)"""
    family, factor = unit_info(unit_name)
    if factor is None:
        return None
    return float(amount or 0) * factor


def classify_units(unit_names):
    """
    دسته‌بندی نام‌های واحد مصرف‌شده در یک کوئری:
    {family: {"names": set, "factor": float, "display": str}}
    خانواده‌های بی‌فکتور (count/unknown) با factor=None می‌آیند.
    """
    groups = {}
    for name in unit_names:
        family, factor = unit_info(name)
        if family is None:
            continue
        g = groups.setdefault(family, {"names": set(), "factor": factor,
                                       "display": DISPLAY_UNIT[family]})
        g["names"].add(name)
    return groups
