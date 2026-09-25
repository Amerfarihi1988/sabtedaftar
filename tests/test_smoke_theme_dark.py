"""
تست smoke در تم تیره — سوییچ تم و رندر همه صفحات
اجرا: QT_QPA_PLATFORM=offscreen python tests/test_smoke_theme_dark.py
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

# تم تیره را در settings ثبت کن
from database.db_manager import db  # noqa: E402
db.execute(
    """INSERT INTO settings (key, value) VALUES ('ui_theme', 'dark')
       ON CONFLICT(key) DO UPDATE SET value=excluded.value"""
)

# بارگذاری تم — همان مسیر main()
from main import load_theme_stylesheet, apply_app_font  # noqa: E402
qss, theme = load_theme_stylesheet()
assert theme == "dark", f"theme = {theme}"
app.setStyleSheet(qss)
family = apply_app_font(app)

from ui.main_window import MainWindow  # noqa: E402
win = MainWindow()
win.showMaximized()
app.processEvents()
win._settle_layouts()
app.processEvents()

print(f"theme={theme}, font={family}, size={win.width()}x{win.height()}")

PAGE_NAMES = [
    "dashboard", "companies", "certificates", "new_permit",
    "search", "reports", "settings", "debts", "charts",
]
errors = []
for idx, name in enumerate(PAGE_NAMES):
    try:
        win._on_nav_click(name)
        app.processEvents()
        app.processEvents()
        # grab بدون کرش
        pm = win.grab()
        if pm.isNull():
            errors.append(f"{name}: grab null")
    except Exception as e:
        errors.append(f"{name}: {e}")

# سوییچ برگشت به روشن
db.execute(
    """INSERT INTO settings (key, value) VALUES ('ui_theme', 'light')
       ON CONFLICT(key) DO UPDATE SET value=excluded.value"""
)
qss2, theme2 = load_theme_stylesheet()
assert theme2 == "light"

win.close()

if errors:
    print("FAIL:", errors)
    sys.exit(1)
print("DARK THEME SMOKE PASSED — هر ۹ صفحه در تم تیره رندر شد")
