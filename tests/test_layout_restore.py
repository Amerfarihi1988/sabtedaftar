"""
تست چرخه واقعی چیدمان با MainWindow خود برنامه
اجرا: QT_QPA_PLATFORM=offscreen python tests/test_layout_restore.py
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
from PyQt6.QtCore import QSettings  # noqa: E402

app = QApplication([])

from database.seed import run_seed  # noqa: E402
run_seed()

from ui.main_window import MainWindow  # noqa: E402

TEST_ORG = "SabteDaftarTest"
TEST_APP = "LayoutRoundTrip"
MainWindow._settings_obj = lambda self: QSettings(TEST_ORG, TEST_APP)

# ── اجرای اول: ذخیره ──
w1 = MainWindow()
w1.resize(1150, 700)
w1.move(60, 40)
w1.show()
app.processEvents()
w1._current_nav = "search"
w1.save_layout()
w1.close()
app.processEvents()

s = QSettings(TEST_ORG, TEST_APP)
print("saved nav =", s.value("window/last_nav"))
print("saved size =", s.value("window/width", 0, type=int), "x",
      s.value("window/height", 0, type=int))

# ── اجرای دوم: بازیابی ──
w2 = MainWindow()
w2.restore_layout()
app.processEvents()
print(f"\nrestored size = {w2.width()}x{w2.height()}")
print(f"restored nav = {w2._current_nav}")

failures = []

# عرض باید دقیق برگشت (بدون قید عمودی) — صفحه تنظیمات و ارتفاع صفحه
# فشار minimumSize دارد ولی fallback عرض را درست می‌گذارد
if abs(w2.width() - 1150) > 10:
    failures.append(f"عرض برگشت: {w2.width()} (انتظار ~1150)")
if w2.height() < 600:
    failures.append(f"ارتفاع خیلی کوچک: {w2.height()}")
if w2._current_nav != "search":
    failures.append(f"تب برگشت: {w2._current_nav}")

QSettings(TEST_ORG, TEST_APP).clear()

if failures:
    print("\nFAIL:", failures)
    sys.exit(1)
print("\nLAYOUT ROUND-TRIP PASSED")
