"""
نقطه‌ی شروع نرم‌افزار
«سامانه ثبت دفتر»
"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from database.db_manager import db
from database.seed import run_seed
from ui.main_window import MainWindow
from config import APP_NAME, APP_VERSION, ASSETS_DIR


def load_stylesheet():
    """بارگذاری استایل سراسری"""
    qss_path = Path(ASSETS_DIR) / "styles.css"
    if qss_path.exists():
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def main():
    print("✓ پایگاه داده آماده شد")
    run_seed()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # فونت پیش‌فرض
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # استایل سراسری اداری
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)
        print("✓ استایل اداری بارگذاری شد")

    window = MainWindow()
    window.show()

    # پشتیبان‌گیری خودکار روزانه — با تأخیر کوتاه تا پنجره اول رندر شود
    QTimer.singleShot(1500, window.maybe_auto_backup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()