"""
ابزارهای ظاهری مشترک — Toast، جداکننده هزارگان، حالت خالی، نشان وضعیت، fade

- show_toast: پیام سبز/قرمز شناور که خودش محو می‌شود (جای QMessageBox برای موفقیت‌ها)
- format_thousands: جداکننده هزارگان فارسی «۳٬۵۰۰٬۰۰۰»
- set_table_empty_state: پیام دوستانه روی جدول خالی
- status_pill: HTML نشان رنگی برای سلول جدول
- fade_page: ترنزیشن نرم هنگام تعویض صفحات
"""
from PyQt6.QtWidgets import QLabel, QTableWidget, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor

# ─── جداکننده هزارگان ───

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def format_thousands(value, persian_digits=True):
    """«3500000» → «۳٬۵۰۰٬۰۰۰» — اعداد اعشاری و منفی را هم درست نگه می‌دارد
    اعشار هم با ممیز فارسی (٫) جدا می‌شود"""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num == int(num):
        s = f"{int(num):,}"
    else:
        s = f"{num:,.2f}"
    s = s.replace(",", "٬").replace(".", "٫")
    if persian_digits:
        s = s.translate(_FA_DIGITS)
    return s


# ─── Toast ───

class Toast(QLabel):
    """پیام شناور گوشه بالا-چپ صفحه — خودش محو می‌شود؛ نیازی به کلیک ندارد"""

    _active = None  # فقط یک Toast هم‌زمان

    def __init__(self, parent, text, kind="success", duration=2600):
        super().__init__(parent)
        colors = {
            "success": ("#ECFDF5", "#065F46", "#059669", "✓"),
            "error": ("#FEF2F2", "#7F1D1D", "#DC2626", "✕"),
            "info": ("#EEF2FF", "#312E81", "#4F46E5", "ℹ"),
        }
        bg, fg, border, icon = colors.get(kind, colors["success"])
        self.setText(f"  {icon}  {text}  ")
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border: 2px solid {border};"
            "border-radius: 10px; padding: 10px 18px; font-size: 13px; font-weight: bold;"
        )
        self.adjustSize()
        # گوشه بالا-چپ (در RTL یعنی انتهای بصری) با فاصله از هدر
        self.move(18, parent.height() - self.height() - 46)
        self.show()
        self.raise_()

        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)
        self._eff.setOpacity(1.0)

        self._anim = QPropertyAnimation(self._eff, b"opacity", self)
        self._anim.setDuration(500)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self.deleteLater)

        QTimer.singleShot(duration, self._anim.start)

        if Toast._active is not None and Toast._active is not self:
            Toast._active._dismiss_now()
        Toast._active = self

    def _dismiss_now(self):
        try:
            self._anim.stop()
            self.deleteLater()
        except RuntimeError:
            pass


def show_toast(parent, text, kind="success", duration=2600):
    """نمایش Toast روی پنجره والد — برای پیام‌های موفقیت/اطلاع"""
    try:
        return Toast(parent, text, kind, duration)
    except Exception:
        pass


# ─── حالت خالی جداول ───

def set_table_empty_state(table: QTableWidget, empty: bool,
                          title="هنوز چیزی ثبت نشده است",
                          subtitle=""):
    """پیام دوستانه وقتی جدول خالی است — overlay شفاف روی جدول"""
    overlay = getattr(table, "_empty_overlay", None)
    if not empty:
        if overlay is not None:
            overlay.hide()
        return

    if overlay is None:
        overlay = QLabel(table)
        overlay.setObjectName("emptyState")
        overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay.setWordWrap(True)
        table._empty_overlay = overlay
        # هم‌گام‌سازی هندسه overlay با viewport در تغییر اندازه جدول —
        # بدون این، بعد از ماکسیمم/مینیمم جابجا و بیرون کادر می‌افتد
        original_resize = table.resizeEvent

        def _resize_event(ev, t=table, orig=original_resize):
            orig(ev)
            ov = getattr(t, "_empty_overlay", None)
            if ov is not None and ov.isVisible():
                ov.setMaximumWidth(max(120, t.viewport().width()))
                _place_overlay(ov, t)

        table.resizeEvent = _resize_event

    overlay.setMaximumWidth(max(120, table.viewport().width()))
    overlay.setText(
        f"<div style='font-size: 30px;'>📋</div>"
        f"<div style='font-size: 14px; font-weight: bold; color: #9CA3AF;'>{title}</div>"
        + (f"<div style='font-size: 12px; color: #B9BEC9;'>{subtitle}</div>" if subtitle else "")
    )
    overlay.setStyleSheet("background: transparent;")
    _place_overlay(overlay, table)
    overlay.show()
    overlay.raise_()


def _place_overlay(overlay, table):
    overlay.setGeometry(0, 0, table.viewport().width(), table.viewport().height())


# ─── نشان رنگی وضعیت ───

_PILL_STYLES = {
    "green": ("#ECFDF5", "#065F46"),
    "red": ("#FEF2F2", "#B91C1C"),
    "amber": ("#FFFBEB", "#92400E"),
    "blue": ("#EEF2FF", "#3730A3"),
    "gray": ("#F3F4F6", "#4B5563"),
}


def status_pill(text, color="gray"):
    """HTML نشان رنگی گرد برای سلول جدول"""
    bg, fg = _PILL_STYLES.get(color, _PILL_STYLES["gray"])
    return (
        f"<span style='background-color:{bg}; color:{fg};"
        "border-radius:9px; padding:2px 10px; font-size:11px; font-weight:bold;'>&nbsp;"
        f"{text}&nbsp;</span>"
    )


def set_cell_pill(table: QTableWidget, row, col, text, color="gray"):
    """نشان رنگی در سلول جدول — QTableWidgetItem قید HTML ندارد؛
    پس‌زمینه ملایم + متن رنگیِ همان خانواده = ظاهر pill بدون ویجت اضافه"""
    from PyQt6.QtWidgets import QTableWidgetItem
    from PyQt6.QtGui import QColor
    bg, fg = _PILL_STYLES.get(color, _PILL_STYLES["gray"])
    item = QTableWidgetItem(text or "—")
    item.setBackground(QColor(bg))
    item.setForeground(QColor(fg))
    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    table.setItem(row, col, item)
    return item


# ─── ترنزیشن fade بین صفحات ───

def fade_in(widget, duration=180):
    """محو شدن نرم ویجت هنگام نمایش — ارزان و بدون ریسک"""
    try:
        eff = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        # بعد از پایان، افکت حذف شود تا رندر سنگین جدول‌ها کند نشود
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        return anim
    except Exception:
        return None
