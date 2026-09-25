"""
سنجش پیکسلی واقعی عنوان گروه‌ها در همه صفحات — جایگزین subControlRect
اجرا: QT_QPA_PLATFORM=offscreen python tests/diag_clipping.py
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

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QGroupBox, QLabel, QTabWidget, QTabBar,
    QSpinBox, QLineEdit, QComboBox, QWidget
)
from PyQt6.QtCore import Qt  # noqa: E402

app = QApplication([])
app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

# همان استایل برنامه
from main import load_stylesheet  # noqa: E402
app.setStyleSheet(load_stylesheet())

from database.seed import run_seed  # noqa: E402
run_seed()

from ui.main_window import MainWindow  # noqa: E402
win = MainWindow()
win.show()
app.processEvents()

# دو حالت: ماکسیمم (نمایش واقعی کاربر) و اندازه پیش‌فرض
SCREEN_H = app.primaryScreen().availableGeometry().height()
SCREEN_W = app.primaryScreen().availableGeometry().width()
win.showMaximized()
app.processEvents()
print(f"maximized = {win.width()}x{win.height()} (screen {SCREEN_W}x{SCREEN_H})")

win.show()
app.processEvents()
win._settle_layouts()
app.processEvents()


def title_band_overflow(img, grp, win):
    """راست‌ترین پیکسل متن در نوار عنوان گروه نسبت به لبه راست گروه"""
    tl = grp.mapTo(win, grp.rect().topLeft())
    tr = grp.mapTo(win, grp.rect().topRight())
    band_y = tl.y() + 5
    right_most = None
    x_start = max(0, tl.x() - 30)
    x_end = min(img.width(), tr.x() + 45)
    for x in range(x_start, x_end):
        for y in range(band_y, band_y + 16):
            if img.pixelColor(x, y).lightness() < 130:
                right_most = x
                break
        if right_most is not None:
            break  # از چپ شروع کرده‌ایم؛ اولین تیره از چپ نیست... اصلاح: کامل اسکن کن
    # اسکن کامل: راست‌ترین پیکسل تیره
    right_most = None
    for x in range(x_start, x_end):
        for y in range(band_y, band_y + 16):
            if img.pixelColor(x, y).lightness() < 130:
                right_most = x
                break
    if right_most is None:
        return 0
    return right_most - tr.x()


PAGE_NAMES = [
    "dashboard", "companies", "certificates", "new_permit",
    "search", "reports", "settings", "debts", "charts",
]

win_w = win.width()
print(f"window = {win_w}x{win.height()}, RTL = {win.layoutDirection() == Qt.LayoutDirection.RightToLeft}")

total_bad = 0
from PyQt6.QtWidgets import QTabWidget, QScrollArea  # noqa: E402

for idx, name in enumerate(PAGE_NAMES):
    page = win.stack.widget(idx)
    win.stack.setCurrentIndex(idx)
    app.processEvents()
    app.processEvents()
    page.layout().invalidate()
    page.layout().activate()
    app.processEvents()

    # در تنظیمات، تب عمومی (۰) را انتخاب کن و اسکرول را پایین ببر
    if idx == 6:
        for tw in page.findChildren(QTabWidget):
            tw.setCurrentIndex(0)
        for sc in page.findChildren(QScrollArea):
            sc.verticalScrollBar().setValue(sc.verticalScrollBar().maximum())
        app.processEvents()
        app.processEvents()

    img = win.grab().toImage()
    offenders = []

    # فقط گروه‌هایی که الان واقعاً داخل viewport دیده می‌شوند —
    # mapTo برای ویجت داخل ScrollArea مختصات content می‌دهد نه صفحه؛
    # مختصات بیرون viewport روی تصویر بی‌معناست و false positive می‌سازد
    def in_viewport(wdg):
        # نوار عنوان (۲۱px بالای گروه) باید کامل داخل تصویر باشد —
        # گروه نیمه‌دیده از بالا، عنوانش اصلاً رندر نشده و سنجشش بی‌معناست
        tl = wdg.mapTo(win, wdg.rect().topLeft())
        br = wdg.mapTo(win, wdg.rect().bottomRight())
        return (wdg.isVisible() and tl.y() >= 0 and tl.y() + 21 < win.height()
                and br.x() >= 0 and tl.x() < win_w)

    for grp in page.findChildren(QGroupBox):
        if not in_viewport(grp):
            continue
        ov = title_band_overflow(img, grp, win)
        if ov > 2:
            offenders.append(f"TITLE «{grp.title()[:40]}» overflow=+{ov}px")

    for lbl in page.findChildren(QLabel):
        if not lbl.isVisible():
            continue
        r = lbl.mapTo(win, lbl.rect().topRight()).x()
        p = lbl.parentWidget()
        p_right = p.mapTo(win, p.rect().topRight()).x() if p else win_w
        if r > win_w - 1:
            offenders.append(f"LABEL «{lbl.text()[:25]}» right={r} > window={win_w}")
        elif p is not None and r > p_right + 2:
            offenders.append(f"LABEL-OUT «{lbl.text()[:25]}» right={r} > parent.right={p_right}")

    for sb in page.findChildren(QSpinBox) + page.findChildren(QLineEdit) + page.findChildren(QComboBox):
        if not sb.isVisible():
            continue
        r = sb.mapTo(win, sb.rect().topRight()).x()
        p = sb.parentWidget()
        p_right = p.mapTo(win, p.rect().topRight()).x() if p else win_w
        if r > win_w - 1 or (p is not None and r > p_right + 2):
            offenders.append(f"INPUT {type(sb).__name__} right={r} parent.right={p_right}")

    total_bad += len(offenders)
    print(f"\n=== {idx}: {name} — {'OK' if not offenders else str(len(offenders)) + ' مورد'} ===")
    for o in offenders[:12]:
        print("  ", o)

win.close()
print(f"\nTOTAL BAD: {total_bad}")
