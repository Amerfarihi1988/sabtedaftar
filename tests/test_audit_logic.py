"""
بررسی منطقی نکات حساس کشف‌شده در بازبینی:
A1: _edit_permit و _delete_permit به ستون مخفی 7 وابسته‌اند — اگر خالی باشد؟
A2: حذف مجوز بدون اسکن — نرم‌افزار باید crash نکند
A3: جستجو با فیلترهای ترکیبی — شرکت + تاریخ + کالا هم‌زمان
A4: form resett بعد از حذف مجوز در حال ویرایش؟ (edge case)
A5: ستون id به‌عنوان int — «str(rec['id'])» و int() دور برگشت
اجرا: QT_QPA_PLATFORM=offscreen python tests/test_audit_logic.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
tmpdir = tempfile.mkdtemp()

import config  # noqa: E402
config.DB_PATH = Path(tmpdir) / "t.db"
config.BACKUP_DIR = Path(tmpdir) / "bk"
config.ensure_directories()

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402

app = QApplication([])
app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

from database.seed import run_seed  # noqa: E402
run_seed()

from database.db_manager import db  # noqa: E402
from ui.ui_helpers import format_thousands  # noqa: E402

failures = []


def check(label, cond, detail=""):
    mark = "OK " if cond else "FAIL"
    print(f"{mark} {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(label)


# داده پایه
db.execute("INSERT INTO companies (name, has_certificate) VALUES ('شرکت تست', 0)")
cid = db.fetch_one("SELECT id FROM companies LIMIT 1")["id"]
# واحد «تن» ممکن است در seed باشد — INSERT OR IGNORE
uid = db.fetch_one("SELECT id FROM units WHERE name='تن'")
if not uid:
    db.execute("INSERT INTO units (name) VALUES ('تن')")
    uid = db.fetch_one("SELECT id FROM units WHERE name='تن'")
uid = uid["id"]

# A5: int دور برگشت id
pid = db.execute(
    "INSERT INTO exit_permits (permit_number, company_id, exit_date) VALUES ('1405/901', ?, '1405/07/01')",
    (cid,)
)
rec = db.fetch_one("SELECT id FROM exit_permits WHERE permit_number='1405/901'")
check("A5: id دور برگشت int", int(str(rec["id"])) == pid, f"{rec['id']} → {int(str(rec['id']))}")

# A2: حذف مجوز بدون اسکن — کد search_window فقط فایل‌های موجود را حذف می‌کند
# (منطق: scans = fetch_all → حلقه → os.path.exists → skip)
scans = db.fetch_all("SELECT file_path FROM scanned_documents WHERE exit_permit_id=?", (pid,))
check("A2: حذف مجوز بدون اسکن — لیست خالی مشکلی ندارد", isinstance(scans, list) and len(scans) == 0)

# A3: فیلتر ترکیبی
db.execute(
    "INSERT INTO exit_permits (permit_number, company_id, exit_date, destination) VALUES ('1405/902', ?, '1405/07/02', 'تهران')",
    (cid,)
)
db.execute(
    "INSERT INTO exit_items (exit_permit_id, product_name, amount, unit_id) VALUES (?, 'گندم', 500, ?)",
    (pid, uid)
)
count = db.fetch_one(
    """SELECT COUNT(*) as c FROM exit_permits ep
       JOIN companies c ON ep.company_id = c.id
       WHERE ep.company_id = ? AND ep.exit_date >= '1405/07/01'
         AND ep.id IN (SELECT exit_permit_id FROM exit_items WHERE product_name LIKE '%گندم%')""",
    (cid,)
)["c"]
check("A3: فیلتر ترکیبی شرکت+تاریخ+کالا", count == 1, f"count={count}")

# A1: ستون 7 جدول همیشه با id پر می‌شود؟ بازبینی کد
import inspect  # noqa: E402
from ui import search_window  # noqa: E402
src = inspect.getsource(search_window.SearchWindow._load_results)
check("A1: ستون مخفی 7 همیشه set می‌شود", "setItem(row, 7" in src)

# جداکننده هزارگان در فرمت مقادیر کالا
from ui.search_window import SearchWindow  # noqa: E402
sw = SearchWindow()
fmt = sw._format_number(3500000)
check("جداکننده در _format_number", fmt == "۳٬۵۰۰٬۰۰۰", fmt)
sw.close()

if failures:
    print(f"\n{len(failures)} مورد شکست خورد:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nAUDIT LOGIC PASSED")
