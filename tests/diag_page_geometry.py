"""
هندسه صفحه‌ها داخل stack — آیا ویجت صفحه داخل viewport جا می‌شود؟
اجرا: QT_QPA_PLATFORM=offscreen python tests/diag_page_geometry.py
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

from ui.main_window import MainWindow  # noqa: E402
win = MainWindow()
win.resize(1920, 1010)
win.show()
app.processEvents()
win._settle_layouts()
app.processEvents()

vp = win.stack.contentsRect()
print(f"stack contentsRect (viewport): {vp}")
print(f"stack widget rect: {win.stack.rect()}")

PAGE_NAMES = [
    "dashboard", "companies", "certificates", "new_permit",
    "search", "reports", "settings", "debts", "charts",
]

for idx, name in enumerate(PAGE_NAMES):
    page = win.stack.widget(idx)
    win.stack.setCurrentIndex(idx)
    app.processEvents()

    pr = page.geometry()
    # در مختصات window
    page_left = page.mapTo(win, page.rect().topLeft()).x()
    page_right = page.mapTo(win, page.rect().topRight()).x()
    win_w = win.width()

    # فاصله لبه راست صفحه از لبه راست stack
    stack_right = win.stack.mapTo(win, win.stack.rect().topRight()).x()
    stack_left = win.stack.mapTo(win, win.stack.rect().topLeft()).x()

    # عمق درخت: page مستقیم در stack است یا داخل container
    depth = 0
    p = page.parentWidget()
    chain = []
    while p is not None and p is not win:
        chain.append(type(p).__name__)
        p = p.parentWidget()
        depth += 1

    status = "OK"
    if page_right > stack_right + 1 or page_left < stack_left - 1:
        status = f"!! صفحه بیرون viewport (left={page_left}, right={page_right}, stack=[{stack_left},{stack_right}])"

    print(f"[{idx}] {name}: page.rect={pr.width()}x{pr.height()} parentChain={chain} → {status}")

win.close()
print("DONE")
