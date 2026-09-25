"""
هندسه واقعی عنوان گروه — خواندن مستقیم از renderer/children
اجرا: QT_QPA_PLATFORM=offscreen python tests/diag_title_geometry.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QGroupBox, QVBoxLayout, QWidget, QLabel
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


def dump_children(grp, tag):
    print(f"[{tag}] children of QGroupBox:")
    for c in grp.findChildren(QObject) if False else []:
        pass
    # children شامل QLabel عنوان؟
    from PyQt6.QtCore import QObject as _QO
    for c in grp.children():
        if isinstance(c, QLabel):
            print(f"   QLabel child: geometry={c.geometry()} text={c.text()!r}")
        elif not isinstance(c, QVBoxLayout) and not isinstance(c, QWidget):
            print(f"   other child: {type(c).__name__} geometry={getattr(c, 'geometry', lambda: None)()}")
    if not any(isinstance(c, QLabel) for c in grp.children()):
        print("   (no QLabel child — title is rendered directly by the style)")


from PyQt6.QtCore import QObject  # noqa: E402

w = QWidget()
w.resize(600, 200)
lay = QVBoxLayout(w)
grp = QGroupBox("تست عنوان")
lay.addWidget(grp)
w.setStyleSheet(QSS_RIGHT)
w.show()
app.processEvents()
dump_children(grp, "QSS right:14px")

# مقایسه بدون QSS
w2 = QWidget()
w2.resize(600, 200)
lay2 = QVBoxLayout(w2)
grp2 = QGroupBox("تست عنوان")
lay2.addWidget(grp2)
w2.show()
app.processEvents()
dump_children(grp2, "no QSS")

# آیا صحفه RTL خوده groupbox رو جابجا می‌کنه؟ geometry گروه رو در هر دو حالت ببین
print(f"\nQSS: group geometry={grp.geometry()}, parent={type(grp.parentWidget()).__name__}")
print(f"no QSS: group geometry={grp2.geometry()}")

# نکته: عنوان با QSS «subcontrol-origin: margin» - آیا margin-top=10px داریم؟
# پس عنوان باید y=-1... نه. ببین title rect در هر دو با subcontrol-origin: padding چطور می‌شود
QSS_PADDING_ORIGIN = """
QGroupBox {
    font-size: 13px;
    font-weight: bold;
    border: 1px solid #E4E7F2;
    border-radius: 14px;
    margin-top: 10px;
    padding-top: 16px;
}
QGroupBox::title {
    subcontrol-origin: padding;
    right: 14px;
    padding: 0 8px;
    background-color: white;
}
"""
w3 = QWidget()
w3.resize(600, 200)
lay3 = QVBoxLayout(w3)
grp3 = QGroupBox("تست عنوان")
lay3.addWidget(grp3)
w3.setStyleSheet(QSS_PADDING_ORIGIN)
w3.show()
app.processEvents()

from PyQt6.QtWidgets import QStyle, QStyleOptionGroupBox  # noqa: E402
opt = QStyleOptionGroupBox()
opt.initFrom(grp3)
opt.text = grp3.title()
opt.lineWidth = 1
sr = grp3.style().subControlRect(
    QStyle.ComplexControl.CC_GroupBox, opt,
    QStyle.SubControl.SC_GroupBoxLabel, grp3
)
print(f"\nsubcontrol-origin: padding → title rect = {sr} (group width={grp3.width()})")

# و با positionBy
QSS_ABS = """
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top right;
    right: 14px;
    padding: 0 8px;
    background-color: white;
}
"""
w4 = QWidget()
w4.resize(600, 200)
lay4 = QVBoxLayout(w4)
grp4 = QGroupBox("تست عنوان")
lay4.addWidget(grp4)
w4.setStyleSheet(QSS_ABS)
w4.show()
app.processEvents()
opt = QStyleOptionGroupBox()
opt.initFrom(grp4)
opt.text = grp4.title()
opt.lineWidth = 1
sr4 = grp4.style().subControlRect(
    QStyle.ComplexControl.CC_GroupBox, opt,
    QStyle.SubControl.SC_GroupBoxLabel, grp4
)
print(f"subcontrol-position: top right → title rect = {sr4} (group width={grp4.width()})")
