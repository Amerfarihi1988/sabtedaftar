"""
تست پیکسلی: کدام ترکیب QSS واقعاً عنوان را داخل کادر نگه می‌دارد؟
عنوان گروه به‌صورت پیکسل رندر و لبه راست محتوای آن سنجیده می‌شود.
اجرا: QT_QPA_PLATFORM=offscreen python tests/diag_title_pixels.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QGroupBox, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

app = QApplication([])
app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

BASE = """
QGroupBox {
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #E4E7F2;
    border-radius: 14px;
    margin-top: 10px;
    padding-top: 16px;
}
"""

VARIANTS = {
    "right:14px (فعلی)": BASE + """
QGroupBox::title {
    subcontrol-origin: margin;
    right: 14px;
    padding: 0 8px;
    background-color: white;
}
""",
    "left:14px": BASE + """
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    background-color: white;
}
""",
    "right:30px": BASE + """
QGroupBox::title {
    subcontrol-origin: margin;
    right: 30px;
    padding: 0 8px;
    background-color: white;
}
""",
    "بدون right/left (پیش‌فرض)": BASE + """
QGroupBox::title {
    subcontrol-origin: margin;
    padding: 0 8px;
    background-color: white;
}
""",
    "subcontrol-position + right:14px": BASE + """
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top right;
    right: 14px;
    padding: 0 8px;
    background-color: white;
}
""",
}

TEXT = "✨ خروج‌های ثبت‌شده امروز"


def pixel_measure(qss, tag):
    w = QWidget()
    w.resize(500, 120)
    lay = QVBoxLayout(w)
    grp = QGroupBox(TEXT)
    lay.addWidget(grp)
    w.setStyleSheet(qss)
    w.show()
    app.processEvents()

    img = w.grab().toImage()
    grp_topleft = grp.mapTo(w, grp.rect().topLeft())
    grp_topright = grp.mapTo(w, grp.rect().topRight())

    # عنوان در نوار بالا (اولین ~20 پیکسل از گروه) رندر می‌شود
    band_y = grp_topleft.y() + 6
    # متن سفید روی پس‌زمینه سفید گروه است؛ متن تیره (#1E1B4B)
    # اسکن افقی نوار عنوان: اولین و آخرین پیکسل تیره
    dark_cols = []
    for x in range(max(0, grp_topleft.x() - 30), min(img.width(), grp_topright.x() + 40)):
        col_has_dark = False
        for y in range(band_y, band_y + 14):
            c = img.pixelColor(x, y)
            if c.lightness() < 120:
                col_has_dark = True
                break
        if col_has_dark:
            dark_cols.append(x)

    if not dark_cols:
        print(f"[{tag}] هیچ متن تیره‌ای پیدا نشد!")
        w.hide()
        return

    right_most = max(dark_cols)
    group_right = grp_topright.x()
    overflow = right_most - group_right
    status = "OK " if overflow <= 0 else "FAIL"
    print(f"{status} {tag}: متن تا {overflow:+d}px نسبت به لبه راست گروه (right_text={right_most}, group_right={group_right})")
    w.hide()


for tag, qss in VARIANTS.items():
    pixel_measure(qss, tag)
