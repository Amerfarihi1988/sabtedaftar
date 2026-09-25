"""
استایل‌دهی متمرکز دیالوگ‌های پیام با پالت جدید برنامه

- دکمه‌های استاندارد Qt به فارسی (بله/خیر/تأیید/انصراف/ذخیره/بستن)
- آیکون‌های SVG هماهنگ با نوار ناوبری (به‌جای آیکون‌های خام Qt)
- نصب ترجمه رسمی فارسی Qt برای دیالوگ‌های سیستمی (فایل، چاپ، ...)
- دیالوگ «لطفاً منتظر بمانید» برای عملیات کند (چاپ، اسکن)

استفاده در main.py:  dialog_style.install(app)
بقیه کد هیچ تغییری لازم ندارد — فیلتر سراسری هنگام نمایش هر QMessageBox فعال می‌شود.
"""
import os

from PyQt6.QtCore import Qt, QByteArray, QObject, QEvent
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QApplication, QMessageBox, QDialog, QVBoxLayout, QLabel, QProgressBar,
)

# ─── پالت (هماهنگ با نوار ناوبری) ───
_ACCENT = "#4F46E5"
_GREEN = "#059669"
_AMBER = "#D97706"
_RED = "#DC2626"

_S = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'

_ICON_SVGS = {
    # کلید = QMessageBox.Icon.name()
    "Information": (
        '<svg viewBox="0 0 24 24" {_s}><circle cx="12" cy="12" r="9"/>'
        '<path d="M12 11v5.5"/><path d="M12 7.6v.5"/></svg>'
    ),
    "Warning": (
        '<svg viewBox="0 0 24 24" {_s}><path d="M12 3.5L21.5 20h-19z"/>'
        '<path d="M12 9.5v5"/><path d="M12 17.4v.5"/></svg>'
    ),
    "Critical": (
        '<svg viewBox="0 0 24 24" {_s}><circle cx="12" cy="12" r="9"/>'
        '<path d="M8.5 8.5l7 7M15.5 8.5l-7 7"/></svg>'
    ),
    "Question": (
        '<svg viewBox="0 0 24 24" {_s}><circle cx="12" cy="12" r="9"/>'
        '<path d="M9.3 9.3a2.7 2.7 0 1 1 3.9 2.4c-.8.4-1.2 1-1.2 1.9v.3"/>'
        '<path d="M12 17.1v.5"/></svg>'
    ),
}


def _build_icon(svg, color, size=72):
    """رندر SVG با رنگ مشخص به QIcon"""
    try:
        renderer = QSvgRenderer(QByteArray(svg.replace("{_s}", _S).replace(
            "currentColor", color).encode("utf-8")))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        if pixmap.isNull():
            return None
        return QIcon(pixmap)
    except Exception:
        return None


_ICON_CACHE = {}


def _icon_for(kind: str) -> QIcon:
    """آیکون پالتی برای هر نوع پیام (با کش)"""
    if kind not in _ICON_CACHE:
        color = {
            "Information": _ACCENT,
            "Warning": _AMBER,
            "Critical": _RED,
            "Question": _ACCENT,
        }.get(kind, _ACCENT)
        svg = _ICON_SVGS.get(kind)
        _ICON_CACHE[kind] = _build_icon(svg, color) if svg else QIcon()
    return _ICON_CACHE[kind]


# ─── دکمه‌های استاندارد Qt به فارسی ───
_FA_BUTTONS = {
    QMessageBox.StandardButton.Ok: "تأیید",
    QMessageBox.StandardButton.Yes: "بله",
    QMessageBox.StandardButton.No: "خیر",
    QMessageBox.StandardButton.Cancel: "انصراف",
    QMessageBox.StandardButton.Save: "ذخیره",
    QMessageBox.StandardButton.Close: "بستن",
    QMessageBox.StandardButton.Abort: "لغو عملیات",
    QMessageBox.StandardButton.Retry: "تلاش دوباره",
    QMessageBox.StandardButton.Ignore: "نادیده گرفتن",
    QMessageBox.StandardButton.Open: "باز کردن",
    QMessageBox.StandardButton.Help: "راهنما",
}


class _MessageBoxStyler(QObject):
    """فیلتر سراسری: هر QMessageBox هنگام نمایش، استایل و دکمه فارسی می‌گیرد"""

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Polish, QEvent.Type.ShowToParent):
            if isinstance(obj, QMessageBox):
                self._style(obj)
        return False

    def _style(self, box: QMessageBox):
        try:
            # ۱. متن فارسی دکمه‌های استاندارد
            for btn in box.buttons():
                std = box.standardButton(btn)
                fa_text = _FA_BUTTONS.get(std)
                if fa_text:
                    btn.setText(fa_text)

            # ۲. دکمه پیش‌فرض: روی «بله» برای سوال، «تأیید» برای اطلاع
            if box.icon() in (
                QMessageBox.Icon.Question,
                QMessageBox.Icon.Information,
            ):
                for btn in box.buttons():
                    std = box.standardButton(btn)
                    if std in (
                        QMessageBox.StandardButton.Yes,
                        QMessageBox.StandardButton.Ok,
                    ):
                        box.setDefaultButton(btn)
                        break

            # ۳. حداقل عرض خوانا + دکمه‌های هم‌عرض
            if box.minimumWidth() < 420:
                box.setMinimumWidth(420)

            # ۴. آیکون SVG پالتی جایگزین آیکون Qt (فقط اگر رندر موفق بود)
            kind = box.icon().name
            if kind:
                icon = _icon_for(kind)
                if icon is not None and not icon.isNull():
                    box.setIconPixmap(icon.pixmap(64, 64))
        except Exception:
            # استایل‌دهی هرگز نباید نمایش پیام را مختل کند
            pass


_styler = _MessageBoxStyler()
_translator_holder = []


def install(app: QApplication):
    """نصب استایل دیالوگ‌ها روی QApplication — از main.py صدا زده می‌شود"""
    app.installEventFilter(_styler)

    # ترجمه رسمی فارسی Qt برای دیالوگ‌های غیر-QMessageBox (فایل، چاپ، ...)
    try:
        from PyQt6.QtCore import QTranslator, QLibraryInfo
        tr = QTranslator(app)
        trans_dir = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if tr.load("qtbase_fa", trans_dir):
            app.installTranslator(tr)
            _translator_holder.append(tr)  # جلوگیری از garbage collection
    except Exception:
        pass


def wait_dialog(parent, text="لطفاً منتظر بمانید..."):
    """
    دیالوگ انتظار بدون دکمه برای عملیات کند.
    استفاده:
        dlg = wait_dialog(self, "در حال چاپ...")
        dlg.show()
        try:
            ... عملیات کند ...
        finally:
            dlg.close()
    """
    dlg = QDialog(parent)
    dlg.setModal(True)
    dlg.setFixedSize(340, 130)
    dlg.setWindowTitle("")
    dlg.setWindowFlags(
        dlg.windowFlags()
        & ~Qt.WindowType.WindowCloseButtonHint
        & ~Qt.WindowType.WindowContextHelpButtonHint
    )

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(24, 22, 24, 22)
    lay.setSpacing(14)

    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("font-size: 13.5px; color: #2D3142; border: none; background: transparent;")
    lay.addWidget(lbl)

    bar = QProgressBar()
    bar.setRange(0, 0)  # نامعین (بی‌نهایت)
    bar.setTextVisible(False)
    bar.setFixedHeight(8)
    bar.setStyleSheet(
        "QProgressBar { border: none; background: #EEF0F8; border-radius: 4px; }"
        "QProgressBar::chunk { background-color: " + _ACCENT + "; border-radius: 4px; }"
    )
    lay.addWidget(bar)

    return dlg
