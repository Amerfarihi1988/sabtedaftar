"""
تست ویژه صفحه تنظیمات — چرا عنوان «اطلاعات نسخه» overflow می‌دهد؟
اجرا: QT_QPA_PLATFORM=offscreen python tests/diag_settings_overflow.py
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

from PyQt6.QtWidgets import (
    QApplication, QGroupBox, QLabel, QScrollArea, QWidget, QVBoxLayout
)
from PyQt6.QtCore import Qt

app = QApplication([])
app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

from main import load_stylesheet  # noqa: E402
app.setStyleSheet(load_stylesheet())

from database.seed import run_seed  # noqa: E402
run_seed()

from ui.main_window import MainWindow  # noqa: E402
win = MainWindow()
win.resize(796, 796)
win.show()
app.processEvents()
win._settle_layouts()
app.processEvents()

win.stack.setCurrentIndex(6)  # settings
app.processEvents()
app.processEvents()

page = win.stack.widget(6)

# رفتن به تب عمومی (ایندکس ۰) — QTabWidget از جابه‌جایی تب ذخیره می‌کند
from PyQt6.QtWidgets import QTabWidget  # noqa: E402
tabs = page.findChildren(QTabWidget)
if tabs:
    tabs[0].setCurrentIndex(0)
    app.processEvents()
    app.processEvents()

# آیا ScrollArea هست و اسکرول لازم است؟
scrolls = page.findChildren(QScrollArea)
for sc in scrolls:
    cw = sc.widget()
    print(f"ScrollArea: viewport={sc.viewport().width()}x{sc.viewport().height()}, "
          f"content={cw.size().width()}x{cw.size().height()}, "
          f"widgetResizable={sc.widgetResizable()}, "
          f"vbar_max={sc.verticalScrollBar().maximum()}")

# اسکرول به پایین تا «اطلاعات نسخه» هم دیده شود — دیالوگ واقعی کاربر همین است
sc0 = scrolls[0] if scrolls else None
if sc0:
    sc0.verticalScrollBar().setValue(sc0.verticalScrollBar().maximum())
    app.processEvents()
    app.processEvents()

img = win.grab().toImage()
for grp in page.findChildren(QGroupBox):
    tl = grp.mapTo(win, grp.rect().topLeft())
    tr = grp.mapTo(win, grp.rect().topRight())
    # مختصات mapTo برای ویجت داخل ScrollArea مختصات content است؛
    # فقط گروه‌هایی را می‌سنجیم که الان داخل viewport دیده می‌شوند
    in_viewport = grp.isVisible() and 0 <= tl.y() and tr.y() < win.height() and tl.x() >= 0 and tr.x() <= win.width()
    if not in_viewport:
        print(f"SKIP (بیرون viewport) «{grp.title()[:45]}» y={tl.y()}")
        continue
    right_most = None
    x_end = min(img.width(), tr.x() + 45)
    for x in range(max(0, tl.x() - 30), x_end):
        for y in range(tl.y() + 5, tl.y() + 21):
            if 0 <= y < img.height() and img.pixelColor(x, y).lightness() < 130:
                right_most = x
                break
    if right_most is not None:
        ov = right_most - tr.x()
        mark = "OK " if ov <= 2 else "FAIL"
        print(f"{mark} «{grp.title()[:45]}» band_y={tl.y()} overflow={ov:+d}px "
              f"(group x=[{tl.x()},{tr.x()}], text_right={right_most})")

win.close()
print("DONE")
