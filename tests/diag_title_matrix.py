"""
ماتریس ترکیب‌های QSS عنوان QGroupBox در RTL — کدام سالم است؟
اجرا: QT_QPA_PLATFORM=offscreen python tests/diag_title_matrix.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QGroupBox, QStyle, QStyleOptionGroupBox
from PyQt6.QtCore import Qt

app = QApplication([])
app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

TITLE_QSS = """
QGroupBox::title {
    subcontrol-origin: margin;
    right: 14px;
    padding: 0 8px;
    background-color: white;
}
"""


def measure(tag, qss):
    box = QGroupBox("✨ خروج‌های ثبت‌شده امروز")
    box.setStyleSheet(qss)
    box.resize(400, 100)
    box.show()
    app.processEvents()
    opt = QStyleOptionGroupBox()
    opt.initFrom(box)
    opt.text = box.title()
    opt.lineWidth = 1
    sr = box.style().subControlRect(
        QStyle.ComplexControl.CC_GroupBox, opt,
        QStyle.SubControl.SC_GroupBoxLabel, box
    )
    ok = sr.right() <= box.width()
    print(f"{'OK ' if ok else 'FAIL'} {tag}: rect={sr} right={sr.right()} width={box.width()}")
    box.hide()
    return ok


print("=== without any QSS ===")
measure("no QSS", "")

print("=== title only ===")
measure("title QSS", TITLE_QSS)

print("=== box QSS without font props ===")
measure(
    "box no font",
    """
QGroupBox {
    border: 1px solid #E4E7F2;
    border-radius: 14px;
    margin-top: 10px;
    padding-top: 16px;
}
""" + TITLE_QSS,
)

print("=== box with font-size only ===")
measure(
    "font-size only",
    """
QGroupBox {
    font-size: 13px;
    border: 1px solid #E4E7F2;
    border-radius: 14px;
    margin-top: 10px;
    padding-top: 16px;
}
""" + TITLE_QSS,
)

print("=== box with font-size+bold ===")
measure(
    "font-size+bold",
    """
QGroupBox {
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #E4E7F2;
    border-radius: 14px;
    margin-top: 10px;
    padding-top: 16px;
}
""" + TITLE_QSS,
)

print("=== box with margin-top 20 ===")
measure(
    "margin-top 20",
    """
QGroupBox {
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #E4E7F2;
    border-radius: 14px;
    margin-top: 20px;
    padding-top: 16px;
}
""" + TITLE_QSS,
)

print("=== title without padding ===")
measure(
    "title no padding",
    """
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
    background-color: white;
}
""",
)

print("=== left: 14px instead of right ===")
measure(
    "left:14px",
    """
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
""",
)

print("=== full app-like QSS on app ===")
app.setStyleSheet(
    """
QGroupBox {
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #E4E7F2;
    border-radius: 14px;
    margin-top: 10px;
    padding-top: 16px;
}
"""
    + TITLE_QSS
)
measure("app-level QSS", "")
