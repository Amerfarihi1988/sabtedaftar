"""
تست مانیفست روزانه PDF — اجرا: python tests/test_manifest.py
ساخت PDF از داده‌ی نمونه و بررسی فایل خروجی.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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


tmp = tempfile.mkdtemp()

import config  # noqa: E402
config.DB_PATH = Path(tmp) / "data" / "test.db"
config.BACKUP_DIR = Path(tmp) / "backups"
config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
config.ensure_directories()

from database.db_manager import db  # noqa: E402

# QPrinter/QTextDocument به QApplication نیاز دارند (وگرنه کرش native)
from PyQt6.QtWidgets import QApplication  # noqa: E402
_app = QApplication.instance() or QApplication([])

from services.report_pdf import generate_daily_manifest_pdf  # noqa: E402


@check("مانیفست PDF ساخته شد و فایل معتبر است")
def t1():
    records = [
        {"permit_number": "1405/001", "company_name": "شرکت الف",
         "destination": "بندر عباس", "items_text": "گازوئیل — 500 لیتر"},
        {"permit_number": "1405/002", "company_name": "شرکت ب",
         "destination": "تهران", "items_text": "بنزین — 200 لیتر | نفت — 100 لیتر"},
    ]
    filepath = os.path.join(tmp, "manifest.pdf")
    ok = generate_daily_manifest_pdf(
        filepath, "1405/06/16", records,
        {"permits": 2, "items": 3, "total_amount": 800}
    )
    assert ok, "تولید PDF باید True برگرداند"
    assert os.path.exists(filepath), "فایل ساخته نشد"
    size = os.path.getsize(filepath)
    assert size > 1000, f"فایل PDF خیلی کوچک است: {size} bytes"
    with open(filepath, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-", f"امضای PDF نامعتبر: {header}"


@check("مانیفست خالی — جدول placeholder، بدون کرش")
def t2():
    filepath = os.path.join(tmp, "manifest_empty.pdf")
    ok = generate_daily_manifest_pdf(
        filepath, "1405/06/17", [],
        {"permits": 0, "items": 0, "total_amount": 0}
    )
    assert ok and os.path.exists(filepath)


for fn in [t1, t2]:
    fn()

shutil.rmtree(tmp, ignore_errors=True)
print(f"\nAll {len(passed)} manifest tests passed")
