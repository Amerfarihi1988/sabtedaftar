"""
تقویم شمسی گرافیکی و فیلد تاریخ شمسی
"""
import re
import jdatetime
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator

PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
]
WEEK_DAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"]


def days_in_jalali_month(year, month):
    """تعداد روزهای ماه شمسی"""
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if jdatetime.date(year, 1, 1).isleap() else 29


def is_valid_shamsi_date(text):
    """
    اعتبارسنجی واقعی تاریخ شمسی با jdatetime:
    - فرمت دقیق YYYY/MM/DD
    - بازه‌ی معتبر ماه (۱-۱۲) و روز (بر اساس ماه و سال کبیسه)
    - بازه‌ی سال منطقی (۱۳۰۰ تا ۱۵۰۰)
    """
    if not text:
        return False
    if not re.match(r"^\d{4}/\d{2}/\d{2}$", text):
        return False
    try:
        y, m, d = [int(x) for x in text.split("/")]
        if not (1300 <= y <= 1500):
            return False
        jdatetime.date(y, m, d)  # ماه/روز نامعتبر → Exception
        return True
    except Exception:
        return False


class ShamsiCalendarDialog(QDialog):
    """دیالوگ تقویم شمسی"""

    def __init__(self, parent=None, initial_date=None):
        super().__init__(parent)
        self.setWindowTitle("تقویم شمسی")
        self.setFixedSize(370, 400)
        self.selected_text = None

        # ماه/سال نمایش جاری
        self.view_year = None
        self.view_month = None
        if initial_date:
            try:
                y, m, d = [int(x) for x in initial_date.split("/")]
                self.view_year, self.view_month = y, m
            except Exception:
                pass
        if self.view_year is None:
            today = jdatetime.date.today()
            self.view_year, self.view_month = today.year, today.month

        self._setup_ui()
        self._render_grid()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # ─── ناوبری ماه ───
        nav = QHBoxLayout()
        btn_prev = QPushButton("◀ ماه قبل")
        btn_prev.setObjectName("btnDefault")
        btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_prev.clicked.connect(self._prev_month)

        btn_next = QPushButton("ماه بعد ▶")
        btn_next.setObjectName("btnDefault")
        btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_next.clicked.connect(self._next_month)

        self.lbl_month = QLabel()
        self.lbl_month.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #4F46E5;"
        )
        self.lbl_month.setAlignment(Qt.AlignmentFlag.AlignCenter)

        nav.addWidget(btn_prev)
        nav.addStretch()
        nav.addWidget(self.lbl_month)
        nav.addStretch()
        nav.addWidget(btn_next)
        layout.addLayout(nav)

        # ─── گرید روزها ───
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(4)
        layout.addLayout(self.grid_layout)

        # ─── دکمه‌های پایین ───
        btn_row = QHBoxLayout()
        btn_today = QPushButton("امروز")
        btn_today.setObjectName("btnPrimary")
        btn_today.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_today.clicked.connect(self._go_today)

        btn_clear = QPushButton("پاک کردن تاریخ")
        btn_clear.setObjectName("btnDanger")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self._clear)

        btn_row.addWidget(btn_today)
        btn_row.addWidget(btn_clear)
        layout.addLayout(btn_row)

    def _render_grid(self):
        """رسم روزهای ماه"""
        # پاک کردن گرید قبلی
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.lbl_month.setText(
            f"{PERSIAN_MONTHS[self.view_month - 1]} {self.view_year}"
        )

        # سرستون روزهای هفته
        for col, day_name in enumerate(WEEK_DAYS):
            lbl = QLabel(day_name)
            lbl.setStyleSheet("font-weight: bold; color: #6B7280;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(lbl, 0, col)

        today = jdatetime.date.today()
        # 0 = شنبه در jdatetime
        first_weekday = jdatetime.date(self.view_year, self.view_month, 1).weekday()
        n_days = days_in_jalali_month(self.view_year, self.view_month)

        for day in range(1, n_days + 1):
            pos = first_weekday + day - 1
            row, col = 1 + pos // 7, pos % 7

            btn = QPushButton(str(day))
            btn.setFixedSize(42, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            is_today = (day == today.day and
                        self.view_month == today.month and
                        self.view_year == today.year)
            if is_today:
                btn.setStyleSheet(
                    "background-color: #4F46E5; color: white; "
                    "border-radius: 8px; font-weight: bold;"
                )
            else:
                btn.setStyleSheet(
                    "background-color: white; border: 1px solid #E4E7F2; "
                    "border-radius: 8px;"
                )

            btn.clicked.connect(lambda checked, d=day: self._pick(d))
            self.grid_layout.addWidget(btn, row, col)

    def _pick(self, day):
        """انتخاب روز و بستن"""
        selected = jdatetime.date(self.view_year, self.view_month, day)
        self.selected_text = selected.strftime("%Y/%m/%d")
        self.accept()

    def _prev_month(self):
        self.view_month -= 1
        if self.view_month == 0:
            self.view_month = 12
            self.view_year -= 1
        self._render_grid()

    def _next_month(self):
        self.view_month += 1
        if self.view_month == 13:
            self.view_month = 1
            self.view_year += 1
        self._render_grid()

    def _go_today(self):
        today = jdatetime.date.today()
        self.view_year, self.view_month = today.year, today.month
        self._render_grid()
        self._pick(today.day)

    def _clear(self):
        self.selected_text = ""
        self.accept()


class ShamsiDateEdit(QWidget):
    """فیلد تاریخ شمسی با دکمه‌ی تقویم — سازگار با API خط متنی"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("مثال: 1405/06/16")
        regex = QRegularExpression(r"\d{0,4}/?\d{0,2}/?\d{0,2}")
        self.line_edit.setValidator(QRegularExpressionValidator(regex))

        self.btn_calendar = QPushButton("📅")
        self.btn_calendar.setFixedSize(38, 32)
        self.btn_calendar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_calendar.setToolTip("انتخاب از تقویم شمسی")
        self.btn_calendar.clicked.connect(self._open_calendar)

        layout.addWidget(self.line_edit, stretch=1)
        layout.addWidget(self.btn_calendar)

    # ─── API سازگار با QLineEdit ───
    def text(self):
        return self.line_edit.text()

    def setText(self, value):
        self.line_edit.setText(value or "")

    def clear(self):
        self.line_edit.clear()

    # ─── تقویم ───
    def _open_calendar(self):
        current = self.line_edit.text().strip()
        initial = current if self._is_valid(current) else None
        dialog = ShamsiCalendarDialog(self, initial)
        if dialog.exec():
            if dialog.selected_text:
                self.line_edit.setText(dialog.selected_text)
            else:
                self.line_edit.clear()

    @staticmethod
    def _is_valid(s):
        return is_valid_shamsi_date(s)