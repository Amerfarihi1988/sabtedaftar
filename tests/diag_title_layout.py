"""
هندسه واقعی عنوان گروه در layout — کدام ترکیب واقعاً بیرون می‌زند؟
اجرا: QT_QPA_PLATFORM=offscreen python tests/diag_title_layout.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QGroupBox, QVBoxLayout, QLabel, QWidget
from PyQt6.QtCore import Qt

app = QApplication([])
app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

QSS_RIGHT = """
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
"""

QSS_LEFT = """
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
    left: 14px;
    padding: 0 8px;
    background-color: white;
}
"""


def build_and_measure(qss, tag):
    w = QWidget()
    w.resize(1900, 300)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(20, 16, 20, 16)
    grp = QGroupBox("✨ خروج‌های ثبت‌شده امروز")
    gl = QVBoxLayout(grp)
    gl.addWidget(QLabel("محتوای آزمایشی"))
    lay.addWidget(grp)
    w.setStyleSheet(qss)
    w.show()
    app.processEvents()

    # برچسب داخلی کجاست؟
    lbl = grp.findChild(QLabel)
    lbl_right = lbl.mapTo(w, lbl.rect().topRight()).x()
    grp_right = grp.mapTo(w, grp.rect().topRight()).x()
    grp_left = grp.mapTo(w, grp.rect().topLeft()).x()

    # عنوان: از childRegions؟ پیکسل‌بازی نکنیم — خواندن title rect از style با
    # هندسه واقعی widget (بعد از layout):
    from PyQt6.QtWidgets import QStyle, QStyleOptionGroupBox
    opt = QStyleOptionGroupBox()
    opt.initFrom(grp)
    opt.text = grp.title()
    opt.lineWidth = 1
    sr = grp.style().subControlRect(
        QStyle.ComplexControl.CC_GroupBox, opt,
        QStyle.SubControl.SC_GroupBoxLabel, grp
    )
    sr_in_w = grp.mapTo(w, sr.topLeft())
    title_right_in_w = sr_in_w.x() + sr.width()

    print(f"[{tag}]")
    print(f"  group rect in window: left={grp_left} right={grp_right}")
    print(f"  content label: right={lbl_right} (فاصله از راست گروه: {grp_right - lbl_right}px)")
    print(f"  title rect (style): {sr} → در window: right={title_right_in_w}")
    print(f"  title بیرون از گروه؟ {'بله ' + str(title_right_in_w - grp_right) + 'px' if title_right_in_w > grp_right else 'خیر'}")
    w.hide()
    return title_right_in_w - grp_right


print("=== QSS با right: 14px ===")
o1 = build_and_measure(QSS_RIGHT, "right:14px")

print("\n=== QSS با left: 14px ===")
o2 = build_and_measure(QSS_LEFT, "left:14px")

print("\n=== تفاوت ===")
print(f"right:14px → overflow={o1}px | left:14px → overflow={o2}px")
