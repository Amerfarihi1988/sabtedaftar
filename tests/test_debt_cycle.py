"""
تست چرخه کامل بدهی — اجرا: python tests/test_debt_cycle.py
سناریو: شرکت گواهی‌دار با سهمیه کم → مجوز با بدهی → گواهی جدید تسویه‌کننده
        → ویرایش همان مجوز → راستی‌آزمایی باقیمانده گواهی و پرچم‌های بدهی.
همه‌ی عملیات روی دیتابیس موقت انجام می‌شود؛ دیتابیس واقعی دست نمی‌خورد.
"""
import os
import sys
import sqlite3
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

tmp = tempfile.mkdtemp()

# ── پچ config پیش از ایمپورت ماژول‌های دیتابیس ──
import config  # noqa: E402
config.DB_PATH = Path(tmp) / "test.db"
config.BACKUP_DIR = Path(tmp) / "backups"
config.ensure_directories()

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402
app = QApplication(sys.argv)

from database.db_manager import db  # noqa: E402  (singleton: ساخت جداول + علامت نسخه)
from database.seed import run_seed  # noqa: E402
from ui.company_window import CompanyFormDialog  # noqa: E402
from ui.certificate_window import CertificateFormDialog, _settle_company_debts_tx  # noqa: E402

run_seed()

failures = []


def check(label, cond, detail=""):
    mark = "✓" if cond else "✗"
    print(f"{mark} {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(label)


# ═══ گام ۰: شرکت + گواهی اولیه با سهمیه کم ═══
dlg = CompanyFormDialog()
dlg.name_input.setText("شرکت چرخه بدهی")
dlg.has_certificate_check.setChecked(True)
dlg._save()
company_id = db.fetch_one("SELECT id FROM companies ORDER BY id DESC LIMIT 1")["id"]

dlg = CertificateFormDialog()
dlg.company_combo.setCurrentIndex(dlg.company_combo.findData(company_id))
dlg.cert_number_input.setText("CERT-001")
dlg.product_type_input.setText("روغن موتور")
dlg.total_amount_input.setValue(100.0)
idx_u = dlg.unit_combo.findData(
    db.fetch_one("SELECT id FROM units WHERE name='لیتر'")["id"]
)
dlg.unit_combo.setCurrentIndex(idx_u)
dlg.issue_date_input.setText("1405/01/01")
dlg._save()

cert1 = db.fetch_one(
    "SELECT * FROM certificates WHERE company_id=? ORDER BY id DESC LIMIT 1",
    (company_id,)
)
unit_id = cert1["unit_id"]
check("گواهی اولیه ثبت شد", cert1 is not None)
check("باقیمانده اولیه = ۱۰۰", cert1["remaining_amount"] == 100.0,
      str(cert1["remaining_amount"]))

# ═══ گام ۱: مجوز با خروجِ بیشتر از سهمیه → بدهی ═══
with db.transaction() as tx:
    permit_id = tx.insert(
        """INSERT INTO exit_permits
           (permit_number, company_id, exit_date, destination, customs_representative, notes)
           VALUES ('1405/999', ?, '1405/02/01', 'مقصد تست', 'نماینده تست', '')""",
        (company_id,)
    )
    # خروج ۱۵۰ لیتر — از سهمیه ۱۰۰ فقط ۱۰۰ کسر و ۵۰ بدهی می‌شود
    tx.insert(
        """INSERT INTO exit_items
           (exit_permit_id, product_name, amount, unit_id, certificate_id, is_debt, debt_settled)
           VALUES (?, 'روغن موتور', 150.0, ?, ?, 1, 0)""",
        (permit_id, unit_id, cert1["id"])
    )
    tx.execute(
        "UPDATE certificates SET remaining_amount=0, status='exhausted' WHERE id=?",
        (cert1["id"],)
    )

debt_before = db.fetch_one(
    "SELECT amount, debt_settled, certificate_id FROM exit_items WHERE exit_permit_id=?",
    (permit_id,)
)
check("مجوز بدهی‌دار ثبت شد (۱۵۰ لیتر، بدهی ۵۰)", debt_before["amount"] == 150.0)

# ═══ گام ۲: گواهی جدید ۵۰ لیتری برای تسویه بدهی (مسیر واقعی UI) ═══
dlg = CertificateFormDialog()
dlg.company_combo.setCurrentIndex(dlg.company_combo.findData(company_id))
dlg.cert_number_input.setText("CERT-002")
dlg.product_type_input.setText("روغن موتور")
dlg.total_amount_input.setValue(50.0)
dlg.unit_combo.setCurrentIndex(dlg.unit_combo.findData(unit_id))
dlg.issue_date_input.setText("1405/02/10")

debt_shown = dlg._get_debt_amount()
# معناشناسی برنامه: بدهی = کل خروجِ بدون پوششِ گواهی فعال (۱۵۰)، نه فقط مازاد بر ۱۰۰
check("دیالوگ بدهی ۱۵۰ لیتری را تشخیص داد", debt_shown == 150.0, str(debt_shown))

# مقدار گواهی جدید باید >= بدهی باشد — ۵۰ کافی نیست، پس با ۱۵۰ ادامه می‌دهیم
dlg.total_amount_input.setValue(150.0)

# تأیید مودال «کسر بدهی» را به‌صورت خودکار به «بله» تبدیل می‌کنیم
# (در تست headless کسی کلیک نمی‌کند)
from unittest.mock import patch  # noqa: E402
with patch("ui.certificate_window.QMessageBox.question",
           return_value=QMessageBox.StandardButton.Yes):
    dlg._save()

cert2 = db.fetch_one(
    "SELECT * FROM certificates WHERE company_id=? ORDER BY id DESC LIMIT 1",
    (company_id,)
)
check("گواهی دوم ثبت شد", cert2 is not None)
check("باقیمانده گواهی دوم = ۰ (کل ۱۵۰ لیتری بدهی کسر شد)",
      cert2["remaining_amount"] == 0.0, str(cert2["remaining_amount"]))

item_after = db.fetch_one("SELECT * FROM exit_items WHERE exit_permit_id=?", (permit_id,))
check("ردیف بدهی به گواهی دوم وصل شد (باگ ۲)",
      item_after["certificate_id"] == cert2["id"],
      f"certificate_id={item_after['certificate_id']}")
check("ردیف بدهی تسویه‌شده علامت خورد", item_after["debt_settled"] == 1)

# ═══ گام ۳: ویرایش همان مجوز — بدهیِ تسویه‌شده به گواهی درست برمی‌گردد ═══
# شبیه‌سازی مسیر ویرایش UI: بازگردانی سهمیه → حذف آیتم‌ها → ثبت آیتم کمتر
from services.quota import restore_permit_quota_tx, apply_quota_plan  # noqa: E402

with db.transaction() as tx:
    restore_permit_quota_tx(tx, permit_id)
    tx.execute("DELETE FROM exit_items WHERE exit_permit_id=?", (permit_id,))
    tx.insert(
        """INSERT INTO exit_items
           (exit_permit_id, product_name, amount, unit_id, certificate_id, is_debt, debt_settled)
           VALUES (?, 'روغن موتور', 40.0, ?, ?, 0, 0)""",
        (permit_id, unit_id, cert2["id"])
    )
    apply_quota_plan(tx, [{
        "certificate_id": cert2["id"], "amount": 40.0,
        "is_debt": False, "product_name": "روغن موتور", "unit_id": unit_id,
    }])

cert2_after = db.fetch_one("SELECT * FROM certificates WHERE id=?", (cert2["id"],))
check("بدهیِ تسویه‌شده (۱۵۰) به گواهی دوم برگشت و خروج ۴۰ کسر شد → ۱۱۰",
      cert2_after["remaining_amount"] == 110.0, str(cert2_after["remaining_amount"]))
check("وضعیت گواهی دوم فعال شد", cert2_after["status"] == "active")

debt_count = db.fetch_one(
    "SELECT COUNT(*) as c FROM exit_items WHERE is_debt=1 AND debt_settled=0"
)["c"]
check("بدهیِ تسویه‌شده‌ی قدیمی به‌عنوان بدهی باز نگشته", debt_count == 0, str(debt_count))

# ═══ گام ۴: بدهیِ تسویه‌نشده نباید به گواهی بچسبد (رفع تورم سهمیه) ═══
before = db.fetch_one("SELECT remaining_amount FROM certificates WHERE id=?", (cert1["id"],))["remaining_amount"]
with db.transaction() as tx:
    p2 = tx.insert(
        """INSERT INTO exit_permits
           (permit_number, company_id, exit_date, destination, customs_representative, notes)
           VALUES ('1405/998', ?, '1405/03/01', 'مقصد تست ۲', 'نماینده تست', '')""",
        (company_id,)
    )
    tx.insert(
        """INSERT INTO exit_items
           (exit_permit_id, product_name, amount, unit_id, certificate_id, is_debt, debt_settled)
           VALUES (?, 'روغن موتور', 60.0, ?, NULL, 1, 0)""",
        (p2, unit_id)
    )
    restore_permit_quota_tx(tx, p2)
after = db.fetch_one("SELECT remaining_amount FROM certificates WHERE id=?", (cert1["id"],))["remaining_amount"]
check("بدهیِ تسویه‌نشده در ویرایش، باقیمانده گواهی را تورم نمی‌دهد",
      before == after, f"{before} -> {after}")
undealt = db.fetch_one(
    "SELECT COUNT(*) as c FROM exit_items WHERE is_debt=1 AND debt_settled=0"
)["c"]
check("بدهیِ جدیدِ گام ۴ همچنان تسویه‌نشده و قابل تسویه باقی است", undealt == 1, str(undealt))

# ═══ گام ۵: سلامت کلی دیتابیس ═══
ic = sqlite3.connect(str(config.DB_PATH)).execute("PRAGMA integrity_check").fetchone()[0]
check("integrity_check = ok", ic == "ok")

shutil.rmtree(tmp, ignore_errors=True)

if failures:
    print(f"\n{len(failures)} مورد شکست خورد:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("\nDEBT CYCLE PASSED — چرخه کامل بدهی سالم است")
