"""
تست ابزارهای ظاهری — جداکننده هزارگان، pill، empty state، toast، fade
اجرا: QT_QPA_PLATFORM=offscreen python tests/test_ui_helpers.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QTableWidget, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

app = QApplication([])
app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

failures = []


def check(label, cond, detail=""):
    mark = "OK " if cond else "FAIL"
    print(f"{mark} {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(label)


from ui.ui_helpers import (
    format_thousands, set_table_empty_state, status_pill, set_cell_pill,
    show_toast, fade_in, Toast,
)

# ── جداکننده هزارگان ──
check("T1: عدد صحیح", format_thousands(3500000) == "۳٬۵۰۰٬۰۰۰", format_thousands(3500000))
check("T1: اعشاری", format_thousands(1234.5) == "۱٬۲۳۴٫۵۰", format_thousands(1234.5))
check("T1: صفر", format_thousands(0) == "۰")
check("T1: منفی", format_thousands(-2500) == "-۲٬۵۰۰", format_thousands(-2500))
check("T1: رشته نامعتبر", format_thousands("abc") == "abc")
check("T1: بدون ارقام فارسی", format_thousands(3500000, persian_digits=False) == "3٬500٬000",
      format_thousands(3500000, persian_digits=False))

# ── pill ──
pill = status_pill("بدهی", "red")
check("T2: pill قرمز", "بدهی" in pill and "#FEF2F2" in pill)
check("T2: pill رنگ نامعتبر → خاکستری", "#F3F4F6" in status_pill("x", "unknown"))

# ── جدول + pill + empty state ──
w = QWidget()
w.resize(600, 400)
lay = QVBoxLayout(w)
tbl = QTableWidget(0, 3)
tbl.setHorizontalHeaderLabels(["الف", "ب", "ج"])
lay.addWidget(tbl)
w.show()
app.processEvents()

tbl.insertRow(0)  # سلول باید ردیف داشته باشد
set_cell_pill(tbl, 0, 0, "بدهی: ۲۰ تن", "red")
check("T3: سلول pill ساخته شد", tbl.item(0, 0) is not None and tbl.item(0, 0).text() == "بدهی: ۲۰ تن",
      tbl.item(0, 0).text() if tbl.item(0, 0) else "None")

set_table_empty_state(tbl, True, title="موردی نیست", subtitle="تست")
app.processEvents()
overlay = getattr(tbl, "_empty_overlay", None)
check("T3: overlay ساخته شد", overlay is not None and overlay.isVisible())

set_table_empty_state(tbl, False)
app.processEvents()
check("T3: overlay بعد از داده مخفی شد", not overlay.isVisible())

tbl.setRowCount(5)
set_table_empty_state(tbl, False)
app.processEvents()

# ── Toast ──
toast = show_toast(w, "ذخیره شد", "success")
check("T4: toast نمایش داده شد", toast is not None and toast.isVisible())
check("T4: فقط یک toast فعال", Toast._active is toast)
toast2 = show_toast(w, "دومی", "info")
app.processEvents()
check("T4: toast دوم جایگزین اول شد", Toast._active is toast2)

# ── fade ──
anim = fade_in(w, 100)
check("T5: fade animation ساخته شد", anim is not None)
app.processEvents()

w.close()

if failures:
    print(f"\n{len(failures)} مورد شکست خورد:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nUI HELPERS PASSED")
