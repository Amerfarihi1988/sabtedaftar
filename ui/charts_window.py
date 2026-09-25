"""
صفحه نمودارها — تحلیل بصری خروج کالا

سه نمودار با PyQt6-Charts:
- میله‌ای: خروج ماهانه (مجموع مقدار کالاها به تفکیک ماه شمسی)
- دایره‌ای: سهم شرکت‌ها از کل خروج
- خطی: روند شکل‌گیری بدهی‌ها در طول زمان

فیلتر بازه‌ی تاریخ شمسی + خروجی PNG از نمودار فعال.
اگر PyQt6-Charts نصب نباشد، صفحه پیام مناسب می‌دهد (بدون کرش).
"""
import jdatetime
import traceback
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QMessageBox, QTabWidget, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter

# ایمپورت نرم — اگر PyQt6-Charts نصب نبود، برنامه کرش نمی‌کند
try:
    from PyQt6.QtCharts import (
        QChartView, QChart, QBarSet, QBarSeries, QBarCategoryAxis,
        QValueAxis, QPieSeries, QLineSeries
    )
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

from database.db_manager import db
from ui.shamsi_calendar import ShamsiDateEdit, is_valid_shamsi_date

# پالت رنگی هماهنگ با برنامه
PALETTE = [
    "#4F46E5", "#059669", "#D97706", "#DC2626", "#7C3AED",
    "#0891B2", "#DB2777", "#65A30D", "#EA580C", "#0D9488",
]

FA_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
             "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def _month_label(key):
    """«1405/07» → «مهر 1405»"""
    try:
        y, mo = key.split("/")
        return f"{FA_MONTHS[int(mo) - 1]} {y}"
    except (ValueError, IndexError):
        return key


class ChartsWindow(QWidget):
    """صفحه نمودارها"""
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_group = None
        self._setup_ui()

    # ═══════════ UI ═══════════

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        if not CHARTS_AVAILABLE:
            warn = QLabel(
                "⚠️ کتابخانه نمودار (PyQt6-Charts) در این نصب موجود نیست.\n"
                "برای فعال‌شدن این صفحه، برنامه را با نسخه‌ی کامل نصب کنید."
            )
            warn.setStyleSheet("font-size: 14px; color: #B45309; padding: 20px;")
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(warn)

            btn_back = QPushButton("بازگشت به داشبورد")
            btn_back.setObjectName("btnDefault")
            btn_back.clicked.connect(self.back_requested.emit)
            layout.addWidget(btn_back)
            return

        # فیلتر بازه تاریخ مشترک — بالای تب‌ها تا در هر ۳ تب دیده بماند
        # (قرار دادن آن داخل تب‌ها باعث می‌شد فقط در تب آخر رندر شود)
        layout.addWidget(self._shared_filter_group())

        tabs = QTabWidget()
        tabs.addTab(self._create_bar_tab(), "📈 خروج ماهانه")
        tabs.addTab(self._create_pie_tab(), "🥧 سهم شرکت‌ها")
        tabs.addTab(self._create_line_tab(), "📉 روند بدهی")
        layout.addWidget(tabs)

        btn_row = QHBoxLayout()
        btn_back = QPushButton("بازگشت به داشبورد")
        btn_back.setObjectName("btnDefault")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.back_requested.emit)
        btn_row.addStretch()
        btn_row.addWidget(btn_back)
        layout.addLayout(btn_row)

    def _shared_filter_group(self):
        """فیلتر مشترک بازه تاریخ — یک‌بار ساخته می‌شود و در هر سه تب فیلترها را می‌بیند"""
        if self._filter_group is None:
            group = QGroupBox("بازه زمانی (شمسی) — خالی = کل تاریخچه")
            form = QFormLayout(group)
            form.setSpacing(6)
            self.f_date_from = ShamsiDateEdit()
            self.f_date_to = ShamsiDateEdit()
            form.addRow("از:", self.f_date_from)
            form.addRow("تا:", self.f_date_to)
            self._filter_group = group
        return self._filter_group

    def _validate_dates(self):
        """اعتبارسنجی بازه؛ خروجی (از، تا) یا None در صورت خطا"""
        date_from = self.f_date_from.text().strip()
        date_to = self.f_date_to.text().strip()
        if date_from and not is_valid_shamsi_date(date_from):
            QMessageBox.warning(self, "خطا", f"«از تاریخ» نامعتبر است: {date_from}\nمثال: 1405/01/01")
            return None
        if date_to and not is_valid_shamsi_date(date_to):
            QMessageBox.warning(self, "خطا", f"«تا تاریخ» نامعتبر است: {date_to}\nمثال: 1405/12/29")
            return None
        return (date_from or None, date_to or None)

    def _empty_chart(self, message):
        chart = QChart()
        chart.setTitle(message)
        return chart

    # ═══════════ تب ۱: میله‌ای خروج ماهانه ═══════════

    def _create_bar_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        # فیلتر بازه تاریخ مشترک، بالای تب‌هاست — اینجا فقط دکمه‌ها
        btn_row = QHBoxLayout()
        btn_render = QPushButton("🔄 رسم نمودار")
        btn_render.setObjectName("btnPrimary")
        btn_render.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_render.clicked.connect(self._render_bar)
        btn_png = QPushButton("🖼️ ذخیره PNG")
        btn_png.setObjectName("btnNeutral")
        btn_png.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_png.clicked.connect(lambda: self._save_png(self.bar_view))
        btn_row.addWidget(btn_render)
        btn_row.addWidget(btn_png)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.bar_view = QChartView()
        self.bar_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.bar_view.setMinimumHeight(380)
        layout.addWidget(self.bar_view, stretch=1)
        return tab

    def _render_bar(self):
        dates = self._validate_dates()
        if dates is None:
            return
        date_from, date_to = dates

        try:
            conditions, params = [], []
            if date_from:
                conditions.append("ep.exit_date >= ?")
                params.append(date_from)
            if date_to:
                conditions.append("ep.exit_date <= ?")
                params.append(date_to)
            where = " WHERE " + " AND ".join(conditions) if conditions else ""

            rows = db.fetch_all(
                f"""SELECT ep.exit_date, SUM(ei.amount) as total
                    FROM exit_items ei
                    JOIN exit_permits ep ON ei.exit_permit_id = ep.id
                    {where}
                    GROUP BY ep.exit_date
                    ORDER BY ep.exit_date""",
                tuple(params)
            )

            # گروه‌بندی ماهانه با مرتب‌سازی درست (پایتون؛ نه ترتیب رشته‌ای SQL)
            monthly = {}
            for r in rows:
                key = str(r["exit_date"])[:7]
                monthly[key] = monthly.get(key, 0.0) + (r["total"] or 0)

            if not monthly:
                self.bar_view.setChart(self._empty_chart("داده‌ای در این بازه ثبت نشده"))
                return

            months = sorted(monthly.keys(), key=_month_sort_key)
            categories = [_month_label(m) for m in months]

            bar_set = QBarSet("مجموع خروج")
            bar_set.setColor(QColor(PALETTE[0]))
            for m in months:
                bar_set.append(monthly[m])

            series = QBarSeries()
            series.setBarWidth(0.7)
            series.append(bar_set)

            chart = QChart()
            chart.addSeries(series)
            chart.setTitle("خروج ماهانه کالا")
            chart.legend().hide()
            chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

            axis_x = QBarCategoryAxis()
            axis_x.append(categories)
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)

            axis_y = QValueAxis()
            axis_y.setLabelFormat("%.0f")
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_y)

            self.bar_view.setChart(chart)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در رسم نمودار: {e}")

    # ═══════════ تب ۲: دایره‌ای سهم شرکت‌ها ═══════════

    def _create_pie_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        btn_row = QHBoxLayout()
        btn_render = QPushButton("🔄 رسم نمودار")
        btn_render.setObjectName("btnPrimary")
        btn_render.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_render.clicked.connect(self._render_pie)
        btn_png = QPushButton("🖼️ ذخیره PNG")
        btn_png.setObjectName("btnNeutral")
        btn_png.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_png.clicked.connect(lambda: self._save_png(self.pie_view))
        btn_row.addWidget(btn_render)
        btn_row.addWidget(btn_png)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.pie_view = QChartView()
        self.pie_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.pie_view.setMinimumHeight(380)
        layout.addWidget(self.pie_view, stretch=1)
        return tab

    def _render_pie(self):
        dates = self._validate_dates()
        if dates is None:
            return
        date_from, date_to = dates

        try:
            conditions, params = [], []
            if date_from:
                conditions.append("ep.exit_date >= ?")
                params.append(date_from)
            if date_to:
                conditions.append("ep.exit_date <= ?")
                params.append(date_to)
            where = " WHERE " + " AND ".join(conditions) if conditions else ""

            rows = db.fetch_all(
                f"""SELECT c.name as company_name, SUM(ei.amount) as total
                    FROM exit_items ei
                    JOIN exit_permits ep ON ei.exit_permit_id = ep.id
                    JOIN companies c ON ep.company_id = c.id
                    {where}
                    GROUP BY c.id
                    ORDER BY total DESC""",
                tuple(params)
            )

            if not rows:
                self.pie_view.setChart(self._empty_chart("داده‌ای در این بازه ثبت نشده"))
                return

            series = QPieSeries()
            for i, r in enumerate(rows):
                slice_ = series.append(str(r["company_name"]), float(r["total"] or 0))
                slice_.setBrush(QColor(PALETTE[i % len(PALETTE)]))
                slice_.setLabelVisible(True)
                pct = slice_.percentage() * 100
                slice_.setLabel(f"{r['company_name']} — {pct:.0f}%")
                slice_.setLabelColor(QColor("#1F2937"))

            chart = QChart()
            chart.addSeries(series)
            chart.setTitle("سهم شرکت‌ها از کل خروج")
            chart.legend().hide()

            self.pie_view.setChart(chart)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در رسم نمودار: {e}")

    # ═══════════ تب ۳: خطی روند بدهی ═══════════

    def _create_line_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        btn_row = QHBoxLayout()
        btn_render = QPushButton("🔄 رسم نمودار")
        btn_render.setObjectName("btnPrimary")
        btn_render.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_render.clicked.connect(self._render_line)
        btn_png = QPushButton("🖼️ ذخیره PNG")
        btn_png.setObjectName("btnNeutral")
        btn_png.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_png.clicked.connect(lambda: self._save_png(self.line_view))
        btn_row.addWidget(btn_render)
        btn_row.addWidget(btn_png)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.line_view = QChartView()
        self.line_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.line_view.setMinimumHeight(380)
        layout.addWidget(self.line_view, stretch=1)
        return tab

    def _render_line(self):
        dates = self._validate_dates()
        if dates is None:
            return
        date_from, date_to = dates

        try:
            conditions = ["ei.is_debt = 1"]
            params = []
            if date_from:
                conditions.append("ep.exit_date >= ?")
                params.append(date_from)
            if date_to:
                conditions.append("ep.exit_date <= ?")
                params.append(date_to)
            where = " WHERE " + " AND ".join(conditions)

            rows = db.fetch_all(
                f"""SELECT ep.exit_date, SUM(ei.amount) as total
                    FROM exit_items ei
                    JOIN exit_permits ep ON ei.exit_permit_id = ep.id
                    {where}
                    GROUP BY ep.exit_date
                    ORDER BY ep.exit_date""",
                tuple(params)
            )

            monthly = {}
            for r in rows:
                key = str(r["exit_date"])[:7]
                monthly[key] = monthly.get(key, 0.0) + (r["total"] or 0)

            if not monthly:
                self.line_view.setChart(
                    self._empty_chart("بدهی‌ای در این بازه ثبت نشده ✓")
                )
                return

            months = sorted(monthly.keys(), key=_month_sort_key)
            categories = [_month_label(m) for m in months]

            series = QLineSeries()
            series.setName("بدهی ماهانه")
            pen = series.pen()
            pen.setColor(QColor(PALETTE[3]))
            pen.setWidth(2)
            series.setPen(pen)
            for i, m in enumerate(months):
                series.append(i, monthly[m])
            series.setPointsVisible(True)

            chart = QChart()
            chart.addSeries(series)
            chart.setTitle("روند شکل‌گیری بدهی‌ها (ماهانه)")
            chart.legend().hide()

            axis_x = QBarCategoryAxis()
            axis_x.append(categories)
            chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(axis_x)

            axis_y = QValueAxis()
            axis_y.setLabelFormat("%.0f")
            chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(axis_y)

            self.line_view.setChart(chart)
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در رسم نمودار: {e}")

    # ═══════════ خروجی PNG ═══════════

    def _save_png(self, view):
        if view is None or view.chart() is None:
            QMessageBox.warning(self, "خطا", "ابتدا نمودار را رسم کنید")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "ذخیره نمودار", "نمودار.png", "PNG (*.png)"
        )
        if not filepath:
            return
        try:
            pixmap = view.grab()
            if pixmap.save(filepath, "PNG"):
                from ui.ui_helpers import show_toast
                show_toast(self, f"نمودار ذخیره شد: {Path(filepath).name}", "success", 3200)
            else:
                QMessageBox.critical(self, "خطا", "ذخیره تصویر ناموفق بود")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در ذخیره: {e}")

    # ═══════════ رفرش ═══════════

    def refresh_page(self):
        """پیش‌فرض‌سازی بازه: ۶ ماه اخیر — فقط بار اول"""
        if CHARTS_AVAILABLE and self._filter_group is not None:
            if not self.f_date_from.text().strip() and not self.f_date_to.text().strip():
                today = jdatetime.date.today()
                six_ago_month = today.month - 6
                year = today.year
                if six_ago_month <= 0:
                    six_ago_month += 12
                    year -= 1
                self.f_date_from.setText(f"{year}/{six_ago_month:02d}/01")
                self.f_date_to.setText(today.strftime("%Y/%m/%d"))


def _month_sort_key(key):
    """کلید مرتب‌سازی «1405/07» — صفرنپر هم درست سورت می‌شود"""
    try:
        y, m = key.split("/")
        return (int(y), int(m))
    except (ValueError, IndexError):
        return (0, 0)
