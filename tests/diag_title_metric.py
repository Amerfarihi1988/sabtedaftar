"""
ریشه‌یابی: چرا عنوان QGroupBox در حالت QSS از راست بیرون می‌زند؟
اجرا: QT_QPA_PLATFORM=offscreen python tests/diag_title_metric.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).root) if False else str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication, QGroupBox, QStyle, QStyleOptionGroupBox, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics

app = QApplication([])
app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

QSS = """
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


def measure(label_qss=""):
    w = QGroupBox("تست عنوان گروه")
    w.setStyleSheet(QSS + label_qss)
    w.ensurePolished()
    fm = w.fontMetrics()
    text_w = fm.horizontalAdvance("تست عنوان گروه")
    opt = QStyleOptionGroupBox()
    opt.initFrom(w)
    opt.text = "تست عنوان گروه"
    opt.lineWidth = 1
    sr = w.style().subControlRect(
        QStyle.ComplexControl.CC_GroupBox, opt,
        QStyle.SubControl.SC_GroupBoxLabel, w
    )
    print(f"text_width={text_w}, label_rect.width={sr.width()}, "
          f"label_rect.right={sr.right()}, margins L={w.contentsMargins().left()} "
          f"R={w.contentsMargins().right()}")
    return text_w, sr


print("--- without QSS ---")
measure()

print("--- with QSS (bold) ---")
measure()

# بررسی رنگ/فونت واقعی — آیا فونت bold از QSS اعمال شده؟
w = QGroupBox("تست")
w.setStyleSheet(QSS)
w.ensurePolished()
f = w.font()
print(f"\nafter QSS: font.bold={f.bold()}, pointSize={f.pointSize()}, family={f.family()}")

# همین تست با لایه‌بندی واقعی: گروه داخل پنجره RTL
box = QGroupBox("✨ خروج‌های ثبت‌شده امروز")
box.setStyleSheet(QSS)
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
print(f"\nreal widget: title rect = {sr}, group rect = {box.rect().width()}")
print(f"title.right = {sr.right()}, title.left = {sr.left()}, text_adv = {QFontMetrics(box.font()).horizontalAdvance(box.title())}")

# آیا عبارت «✨» مشکلساز است؟ عرض emoji را جدا بسنج
fm2 = QFontMetrics(box.font())
print(f"emoji '✨' advance = {fm2.horizontalAdvance('✨')}")
print(f"'✨' char at right in RTL? title starts with emoji: {box.title().startswith('✨')}")

app.processEvents()
