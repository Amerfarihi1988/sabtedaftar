"""
تست پیکسلی با استایل کامل برنامه — بازتولد ۱۹px و یافتن قانون مقصر
اجرا: QT_QPA_PLATFORM=offscreen python tests/diag_title_fullcss.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QGroupBox, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

app = QApplication([])
app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

css_path = Path(__file__).parent.parent / "assets" / "styles.css"
full_qss = css_path.read_text(encoding="utf-8")
app.setStyleSheet(full_qss)

TEXT = "✨ خروج‌های ثبت‌شده امروز"


def pixel_measure(tag, extra_qss=""):
    w = QWidget()
    w.resize(500, 120)
    lay = QVBoxLayout(w)
    grp = QGroupBox(TEXT)
    lay.addWidget(grp)
    if extra_qss:
        grp.setStyleSheet(extra_qss)
    w.show()
    app.processEvents()

    img = w.grab().toImage()
    grp_topleft = grp.mapTo(w, grp.rect().topLeft())
    grp_topright = grp.mapTo(w, grp.rect().topRight())

    band_y = grp_topleft.y() + 6
    dark_cols = []
    for x in range(max(0, grp_topleft.x() - 30), min(img.width(), grp_topright.x() + 40)):
        for y in range(band_y, band_y + 14):
            c = img.pixelColor(x, y)
            if c.lightness() < 120:
                dark_cols.append(x)
                break

    if not dark_cols:
        print(f"[{tag}] هیچ متن تیره‌ای پیدا نشد!")
        w.hide()
        return

    right_most = max(dark_cols)
    group_right = grp_topright.x()
    overflow = right_most - group_right
    status = "OK " if overflow <= 0 else "FAIL"
    print(f"{status} {tag}: overflow={overflow:+d}px")
    w.hide()


print("=== استایل کامل برنامه (app-level) ===")
pixel_measure("full app css")

print("\n=== + override محلی روی گروه ===")
pixel_measure("full + local override", """
QGroupBox {
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #E4E7F2;
    border-radius: 14px;
    margin-top: 10px;
    padding-top: 16px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    right: 14px;
    padding: 0 8px;
    background-color: white;
}
""")

print("\n=== استایل کامل اما روی widget (نه app) ===")
app.setStyleSheet("")
w = QWidget()
w.resize(500, 120)
lay = QVBoxLayout(w)
grp = QGroupBox(TEXT)
lay.addWidget(grp)
w.setStyleSheet(full_qss)
w.show()
app.processEvents()
img = w.grab().toImage()
grp_topleft = grp.mapTo(w, grp.rect().topLeft())
grp_topright = grp.mapTo(w, grp.rect().topRight())
band_y = grp_topleft.y() + 6
dark_cols = []
for x in range(max(0, grp_topleft.x() - 30), min(img.width(), grp_topright.x() + 40)):
    for y in range(band_y, band_y + 14):
        c = img.pixelColor(x, y)
        if c.lightness() < 120:
            dark_cols.append(x)
            break
right_most = max(dark_cols)
overflow = right_most - grp_topright.x()
print(f"{'OK ' if overflow <= 0 else 'FAIL'} widget-level full css: overflow={overflow:+d}px")
w.hide()
