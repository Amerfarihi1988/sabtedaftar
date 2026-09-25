"""
تست headless پنجره تنظیمات — اجرا: python tests/test_settings_version_ui.py
نمایش نسخه ساختار دیتابیس و آخرین مهاجرت را در تب «تنظیمات عمومی» راستی‌آزمایی می‌کند.
بدون نمایش پنجره (offscreen platform).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import config  # noqa: E402

# دیتابیس واقعی پروژه استفاده می‌شود (فقط خواندنی برای این تست)
from PyQt6.QtWidgets import QApplication  # noqa: E402
from database.db_manager import db  # noqa: E402 — singleton: مهاجرت را در صورت نیاز اجرا می‌کند
from database.migrations import get_current_schema_version, get_last_migration_info, LATEST_VERSION  # noqa: E402
from ui.settings_window import SettingsWindow  # noqa: E402

app = QApplication(sys.argv)

window = SettingsWindow()

failures = []

# ── ۱) برچسب نسخه ساختار دیتابیس با مقدار واقعی هم‌خوان است ──
schema_v = get_current_schema_version()
expected = f"نسخه {schema_v} — به‌روز ✓" if schema_v == LATEST_VERSION else None
found_schema = False
for lbl in window.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel):
    if lbl.text().startswith("نسخه ") and ("به‌روز" in lbl.text() or "نیاز" in lbl.text()):
        found_schema = True
        if expected and lbl.text() != expected:
            failures.append(f"متن نسخه دیتابیس ناهم‌خوان: {lbl.text()!r} != {expected!r}")
if not found_schema:
    failures.append("برچسب نسخه ساختار دیتابیس پیدا نشد")

# ── ۲) برچسب نسخه نرم‌افزار ──
from config import APP_NAME, APP_VERSION  # noqa: E402

found_app = any(
    f"{APP_NAME} — نسخه {APP_VERSION}" in lbl.text()
    for lbl in window.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel)
)
if not found_app:
    failures.append("برچسب نسخه نرم‌افزار پیدا نشد")

# ── ۳) برچسب آخرین مهاجرت ──
last = get_last_migration_info()
found_last = any(
    (last and last in lbl.text()) or (not last and "مهاجرتی اجرا نشده" in lbl.text())
    for lbl in window.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel)
)
if not found_last:
    failures.append("برچسب آخرین مهاجرت پیدا نشد")

# ── ۴) تابع کمکی لاگ هم درست کار می‌کند ──
if last is not None and "✓ مهاجرت" not in last:
    failures.append(f"خروجی get_last_migration_info ناهم‌خوان: {last!r}")

if failures:
    print("FAILURES:")
    for f_ in failures:
        print(" -", f_)
    sys.exit(1)

print(f"✓ نسخه ساختار دیتابیس نمایش داده شد: v{schema_v} (آخرین: {LATEST_VERSION})")
print(f"✓ نسخه نرم‌افزار نمایش داده شد: {APP_VERSION}")
print(f"✓ آخرین مهاجرت نمایش داده شد: {last}")
print("SETTINGS VERSION UI PASSED")
