"""
نقطه‌ی شروع نرم‌افزار
«سامانه ثبت دفتر»
"""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
from database.migrations import MigrationError
from services import app_log
from ui import dialog_style
from config import APP_NAME, APP_VERSION, ASSETS_DIR, ICON_PATH, BASE_DIR

# ─── حالت نمایش (روشن/تیره) — از تنظیمات خوانده می‌شود ───
def load_theme_stylesheet():
    """استایل فعال: روشن (پیش‌فرض) یا تیره — بر اساس کلید ui_theme"""
    from database.db_manager import db
    try:
        rec = db.fetch_one("SELECT value FROM settings WHERE key='ui_theme'")
        theme = rec["value"] if rec else "light"
    except Exception:
        theme = "light"
    name = "styles_dark.css" if theme == "dark" else "styles.css"
    qss_path = Path(ASSETS_DIR) / name
    if qss_path.exists():
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read(), theme
    return "", "light"


def apply_app_font(app):
    """بارگذاری فونت وزیرمتن از داخل باندل — اگر نبود Segoe UI"""
    from PyQt6.QtGui import QFontDatabase
    loaded = ""
    for fname in ("Vazirmatn-Regular.ttf", "Vazirmatn-Bold.ttf", "Vazirmatn-Medium.ttf"):
        fpath = Path(ASSETS_DIR) / "fonts" / fname
        if fpath.exists():
            fid = QFontDatabase.addApplicationFont(str(fpath))
            if fid >= 0:
                families = QFontDatabase.applicationFontFamilies(fid)
                if families:
                    loaded = families[0]
    if loaded:
        app.setFont(QFont(loaded, 10))
        return loaded
    app.setFont(QFont("Segoe UI", 10))
    return "Segoe UI"


def _fatal_migration_error(app, error):
    """نمایش خطای مهاجرت دیتابیس به‌صورت دیالوگ (EXE کنسول ندارد) و خروج"""
    QMessageBox.critical(
        None,
        "خطای پایگاه داده",
        f"{error}\n\n"
        f"برنامه اجرا نشد تا داده‌های شما آسیب نببینند.\n"
        f"جزئیات بیشتر در فایل data/migrations.log کنار برنامه ثبت شده است.\n"
        f"در صورت نیاز، از پشتیبان‌های پوشه backups/pre_migration استفاده کنید."
    )
    sys.exit(1)


def _request_password(app) -> bool:
    """
    اگر رمز ورود ثبت شده باشد، دیالوگ ورود رمز نشان می‌دهد.
    خروجی: True = ورود موفق / False = ۵ تلاش ناموفق (خروج از برنامه)
    """
    from services.auth import is_password_set, verify_password
    if not is_password_set():  # رمز اختیاری است — فعال فقط از تنظیمات
        return True

    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
    from PyQt6.QtCore import Qt

    dlg = QDialog()
    dlg.setWindowTitle("ورود — نرم‌افزار دفتر خروج کالا")
    dlg.setModal(True)
    dlg.setFixedWidth(380)

    lay = QVBoxLayout(dlg)
    lay.setSpacing(12)

    icon_lbl = QLabel("🔒")
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_lbl.setStyleSheet("font-size: 34px;")
    lay.addWidget(icon_lbl)

    msg = QLabel("برای ورود، رمز عبور را وارد کنید:")
    msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
    msg.setStyleSheet("font-size: 14px;")
    lay.addWidget(msg)

    txt_password = QLineEdit()
    txt_password.setEchoMode(QLineEdit.EchoMode.Password)
    txt_password.setPlaceholderText("رمز عبور")
    lay.addWidget(txt_password)

    lbl_error = QLabel("")
    lbl_error.setStyleSheet("color: #e74c3c; font-size: 12px;")
    lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl_error.setWordWrap(True)
    lay.addWidget(lbl_error)

    btn_login = QPushButton("ورود")
    btn_login.setObjectName("btnPrimary")
    btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
    lay.addWidget(btn_login)

    # دیالوگ بدون دکمه بستن — تا وقتی رمز درست نشده، بیرون رفتن یعنی خروج از برنامه
    dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint & ~Qt.WindowType.WindowMinMaxButtonsHint)

    MAX_ATTEMPTS = 5
    result = {"ok": False}

    def _try_login():
        if verify_password(txt_password.text()):
            result["ok"] = True
            dlg.accept()
            return
        MAX_ATTEMPTS_LEFT = dlg.property("attempts_left")
        if MAX_ATTEMPTS_LEFT is None:
            MAX_ATTEMPTS_LEFT = MAX_ATTEMPTS
        MAX_ATTEMPTS_LEFT -= 1
        dlg.setProperty("attempts_left", MAX_ATTEMPTS_LEFT)
        if MAX_ATTEMPTS_LEFT <= 0:
            dlg.reject()
            return
        lbl_error.setText(f"رمز نادرست است — {MAX_ATTEMPTS_LEFT} تلاش باقی مانده")
        txt_password.selectAll()
        txt_password.setFocus()

    btn_login.clicked.connect(_try_login)
    txt_password.returnPressed.connect(_try_login)

    dlg.exec()
    return result["ok"]


def load_stylesheet():
    """(سازگاری قدیمی) استایل روشن — جایگزین: load_theme_stylesheet"""
    qss_path = Path(ASSETS_DIR) / "styles.css"
    if qss_path.exists():
        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def main():
    # ایمن‌سازی چاپ کاراکترهای یونیکد (✓ و فارسی) در کنسول ویندوز —
    # codepage پیش‌فرض (مثلاً cp1256) این کاراکترها را ندارد و بدون این
    # گارد، اجرای برنامه از کنسول کرش می‌دهد
    for _name in ("stdout", "stderr"):
        _stream = getattr(sys, _name, None)
        if _stream is not None and hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    # لاگ فایل سراسری — پیش از هر چیز دیگری (خطای مهاجرت هم ثبت می‌شود)
    app_log.setup_logging()
    log = app_log.get_logger()
    log.info(f"شروع برنامه — نسخه {APP_VERSION}")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # ── گارد تک‌نمونه: اجرای دوباره EXE مجاز نیست (خرابی شمارنده شماره‌ها) ──
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
    lock_socket = QLocalSocket()
    lock_socket.connectToServer("sabtedaftar_single_instance")
    if lock_socket.waitForConnected(300):
        lock_socket.disconnectFromServer()
        QMessageBox.warning(
            None, "برنامه در حال اجراست",
            "نرم‌افزار دفتر خروج کالا همین حالا باز است.\n"
            "اجرای هم‌زمان دو نسخه مجاز نیست (خطر خرابی شماره‌گذاری)."
        )
        log.warning("اجرای دوباره برنامه رد شد (نمونه فعال موجود)")
        sys.exit(0)

    # سرور تک‌نمونه — تا وقتی برنامه باز است، نمونه دوم connect نمی‌شود
    QLocalServer.removeServer("sabtedaftar_single_instance")  # پاک‌سازی نام یتیم پس از crash
    _single_instance_server = QLocalServer()
    _single_instance_server.listen("sabtedaftar_single_instance")
    app._single_instance_server = _single_instance_server  # جلوگیری از garbage collection

    # ── راه‌اندازی دیتابیس + مهاجرت‌های نسخه‌دار ──
    # اگر مهاجرت ناموفق شود، پیام واضح نمایش داده می‌شود و برنامه
    # با ساختار ناسازگار اجرا نمی‌شود (دیتابیس rollback شده است).
    try:
        from database.db_manager import db  # noqa: F401 — ساخت جداول + مهاجرت
        from database.seed import run_seed
        run_seed()
    except MigrationError as e:
        log.critical(f"مهاجرت دیتابیس ناموفق: {e}")
        _fatal_migration_error(app, e)
        return

    log.info("پایگاه داده آماده شد")
    print("✓ پایگاه داده آماده شد")

    # آیکون برنامه (پنجره + تسک‌بار ویندوز) — داخل باندل EXE هم کار می‌کند
    if Path(ICON_PATH).exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    # فونت فارسی وزیرمتن (باندل‌شده) — اگر نبود Segoe UI
    family = apply_app_font(app)
    print(f"✓ فونت: {family}")

    # استایل سراسری — روشن یا تیره (از تنظیمات)
    stylesheet, theme = load_theme_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)
        print(f"✓ استایل بارگذاری شد (تم: {'تیره' if theme == 'dark' else 'روشن'})")
    app._current_theme = theme

    # دیالوگ‌های پیام با پالت برنامه (دکمه‌های فارسی + آیکون‌های هماهنگ)
    dialog_style.install(app)

    # ── رمز ورود اختیاری — قبل از نمایش پنجره اصلی ──
    # رمز هرگز به‌صورت خام ذخیره نمی‌شود (PBKDF2-SHA256 با salt تصادفی)
    if not _request_password(app):
        log.warning("۵ تلاش ناموفق رمز ورود — برنامه بسته شد")
        sys.exit(0)

    # ── اسپلش‌اسکرین — EXE تک‌فایلی چند ثانیه باز می‌شود؛ حس سرعت ──
    from PyQt6.QtWidgets import QSplashScreen
    splash_pix = QPixmap(420, 260)
    splash_pix.fill(QColor("#4F46E5"))
    sp = QPainter(splash_pix)
    sp.setRenderHint(QPainter.RenderHint.Antialiasing)
    sp.setPen(QColor("white"))
    f_big = QFont(app.font().family(), 17)
    f_big.setBold(True)
    sp.setFont(f_big)
    sp.drawText(splash_pix.rect().adjusted(0, -30, 0, -30), Qt.AlignmentFlag.AlignCenter, APP_NAME)
    f_small = QFont(app.font().family(), 10)
    sp.setFont(f_small)
    sp.setPen(QColor(255, 255, 255, 200))
    sp.drawText(splash_pix.rect().adjusted(0, 34, 0, 34), Qt.AlignmentFlag.AlignCenter, "در حال بارگذاری…")
    sp.end()
    splash = QSplashScreen(splash_pix)
    splash.show()
    app.processEvents()

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    splash.finish(window)

    # یادآوری چیدمان: موقعیت/اندازه پنجره و تب آخر از اجرای قبل
    window.restore_layout()

    # پشتیبان‌گیری خودکار روزانه — با تأخیر کوتاه تا پنجره اول رندر شود
    QTimer.singleShot(1500, window.maybe_auto_backup)

    rc = app.exec()
    window.save_layout()
    sys.exit(rc)


if __name__ == "__main__":
    main()
