"""
Smoke-test سراسری برنامه — اجرا: python tests/smoke_app.py
همه‌ی صفحات را باز می‌کند، ویرایش مجوز را بارگذاری می‌کند و فیلترها را می‌آزماید.
دیتابیس واقعی پروژه فقط خوانده می‌شود (هیچ نوشتنی ندارد).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

from ui.main_window import MainWindow  # noqa: E402
from database.db_manager import db  # noqa: E402

w = MainWindow()
w.show()
app.processEvents()

# ── همه صفحات را باز کن (refresh path هر صفحه) ──
for key in ["companies", "certificates", "new_permit", "search", "charts", "reports", "settings", "dashboard"]:
    w._on_nav_click(key)
    app.processEvents()
print("SMOKE: nav + refresh all pages OK")

# ── نمودارها: رسم هر سه و گرفتن PNG ──
w._on_nav_click("charts")
app.processEvents()
w.charts_page._render_bar()
w.charts_page._render_pie()
w.charts_page._render_line()
app.processEvents()
pm = w.charts_page.bar_view.grab()
assert not pm.isNull(), "PNG نمودار خالی است"
print("SMOKE: charts render + PNG grab OK")

# ── ویرایش یک مجوز واقعی ──
row = db.fetch_one("SELECT id FROM exit_permits ORDER BY id LIMIT 1")
if row:
    w._open_edit_permit(row["id"])
    app.processEvents()
    items = w.permit_page._collect_items()
    print(f"SMOKE: load_for_edit OK (permit {row['id']}), items={len(items)}")
    w.permit_page._reset_form()

# ── جستجو با فیلتر بدهی ──
w.search_page.chk_debt_only.setChecked(True)
w.search_page._load_results()
print("SMOKE: debt-filter search OK, rows:", w.search_page.table.rowCount())
w.search_page.chk_debt_only.setChecked(False)
w.search_page._load_results()

# ── پنجره تنظیمات: پنل نسخه ──
w._on_nav_click("settings")
app.processEvents()
print("SMOKE: settings version panel OK")

# ── داشبورد ──
w._on_nav_click("dashboard")
app.processEvents()
print("SMOKE: dashboard data OK")

w.close()
print("SMOKE PASSED")
