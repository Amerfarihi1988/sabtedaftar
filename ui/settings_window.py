"""
پنجره تنظیمات و پشتیبان‌گیری
"""
import os
import traceback
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog,
    QTabWidget, QSpinBox, QPlainTextEdit, QLineEdit, QInputDialog,
    QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from database.db_manager import db
from database.migrations import get_current_schema_version, get_last_migration_info, LATEST_VERSION
from services.backup import create_backup, restore_backup, get_backup_list, auto_backup_if_needed
from services import auth
from services.org_settings import clear_cache as clear_org_cache
from services import app_log
from ui.ui_helpers import show_toast
from config import BACKUP_DIR, APP_NAME, APP_VERSION


class SettingsWindow(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # setWindowTitle و resize حذف
        try:
            self._setup_ui()
            self._load_backups()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در بارگذاری: {e}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._create_general_tab(), "تنظیمات عمومی")
        tabs.addTab(self._create_backup_tab(), "پشتیبان‌گیری")
        layout.addWidget(tabs)

        btn_close = QPushButton("بستن")
        btn_close.setStyleSheet(
            "padding: 8px 20px; font-size: 14px; border-radius: 5px; border: 1px solid #ccc;"
        )
        btn_close.clicked.connect(self.back_requested.emit)
        layout.addWidget(btn_close)

    def _create_general_tab(self):
        # محتوای تب داخل QScrollArea است — با گروه‌های جدید (پشتیبان دوم، امنیت)
        # صفحه از ارتفاع پنجره بلندتر می‌شود؛ بدون اسکرول، Qt ویجت‌ها را له می‌کند
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("scrollContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)

        tab_layout.addWidget(scroll)
        scroll.setWidget(content)

        group = QGroupBox("تنظیمات عمومی")
        form = QFormLayout(group)
        form.setSpacing(12)

        # ─── سربرگ سازمانی (چاپ و گزارش‌ها) ───
        self.org_title_input = QLineEdit()
        self.org_title_input.setPlaceholderText("مثال: اداره کل گمرکات استان...")
        self.org_title_input.setText(self._load_setting_value("org_title", ""))
        form.addRow("عنوان سازمان (سربرگ چاپ):", self.org_title_input)

        self.org_logo_input = QLineEdit()
        self.org_logo_input.setPlaceholderText("مسیر فایل لوگو (PNG/JPG) — اختیاری")
        self.org_logo_input.setText(self._load_setting_value("org_logo_path", ""))
        form.addRow("لوگو:", self.org_logo_input)

        btn_browse_logo = QPushButton("انتخاب فایل لوگو...")
        btn_browse_logo.setObjectName("btnNeutral")
        btn_browse_logo.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse_logo.clicked.connect(self._browse_logo)
        form.addRow("", btn_browse_logo)

        self.chk_auto_backup = QCheckBox("پشتیبان‌گیری خودکار هر روز هنگام باز شدن برنامه")
        self._load_setting("chk_auto_backup", "auto_backup")
        form.addRow("", self.chk_auto_backup)

        # اجرای دستی همان منطق روزانه (اگر امروز گرفته نشده باشد، همین حالا می‌گیرد)
        btn_run_now = QPushButton("🚀 اجرای پشتیبان‌گیری خودکار همین حالا")
        btn_run_now.setObjectName("btnPrimary")
        btn_run_now.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_run_now.clicked.connect(self._run_auto_backup_now)
        form.addRow("", btn_run_now)

        layout.addWidget(group)

        # ─── نگهداری پشتیبان‌ها ───
        retention_group = QGroupBox("نگهداری پشتیبان‌ها")
        retention_form = QFormLayout(retention_group)
        retention_form.setSpacing(10)

        self.spin_backup_keep = QSpinBox()
        self.spin_backup_keep.setRange(3, 365)
        self.spin_backup_keep.setSuffix(" عدد آخر")
        self.spin_backup_keep.setValue(self._load_backup_keep())
        self.spin_backup_keep.setToolTip(
            "فقط آخرین پشتیبان‌های ZIP نگه داشته می‌شوند؛ بقیه خودکار حذف می‌شوند"
        )
        retention_form.addRow("نگهداری:", self.spin_backup_keep)

        layout.addWidget(retention_group)

        # ─── پشتیبان دوم هفتگی (خارج از سیستم) ───
        secondary_group = QGroupBox("پشتیبان دوم هفتگی (خارج از سیستم)")
        secondary_form = QFormLayout(secondary_group)
        secondary_form.setSpacing(10)

        self.chk_secondary = QCheckBox(
            "هفت‌روز یک‌بار، آخرین پشتیبان ZIP به مسیر زیر کپی شود"
        )
        self.chk_secondary.setChecked(self._load_setting_value("secondary_backup_enabled") == "1")
        secondary_form.addRow("", self.chk_secondary)

        self.secondary_path_input = QLineEdit()
        self.secondary_path_input.setPlaceholderText(
            "مثال: E:\\BackupDafter یا \\\\server\\shared\\backup"
        )
        self.secondary_path_input.setText(self._load_setting_value("secondary_backup_path"))
        secondary_form.addRow("مسیر مقصد:", self.secondary_path_input)

        btn_browse_secondary = QPushButton("📂 انتخاب پوشه مقصد...")
        btn_browse_secondary.setObjectName("btnNeutral")
        btn_browse_secondary.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse_secondary.clicked.connect(self._browse_secondary_path)
        secondary_form.addRow("", btn_browse_secondary)

        btn_run_secondary = QPushButton("🛡 اجرای پشتیبان دوم همین حالا")
        btn_run_secondary.setObjectName("btnPrimary")
        btn_run_secondary.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_run_secondary.clicked.connect(self._run_secondary_backup_now)
        secondary_form.addRow("", btn_run_secondary)

        lbl_secondary_hint = QLabel(
            "💡 مسیر را روی فلش USB، درایو شبکه یا دیسک دیگری بگذارید تا در صورت "
            "خرابی دیسک یا حمله‌ی ویروس، نسخه‌ی دوم داده‌ها از دست نرود.\n"
            "کپی هنگام باز شدن برنامه انجام می‌شود (اگر هفت روز از آخرین کپی گذشته باشد)."
        )
        lbl_secondary_hint.setWordWrap(True)
        lbl_secondary_hint.setStyleSheet("color: #666; font-size: 12px;")
        secondary_form.addRow("", lbl_secondary_hint)

        layout.addWidget(secondary_group)

        # ─── حالت نمایش (روشن/تیره) ───
        theme_group = QGroupBox("حالت نمایش")
        theme_form = QFormLayout(theme_group)
        theme_form.setSpacing(10)

        self.chk_dark_mode = QCheckBox("🌙 حالت تیره — مناسب شیفت‌های طولانی")
        self.chk_dark_mode.setChecked(self._load_setting_value("ui_theme", "light") == "dark")
        theme_form.addRow("", self.chk_dark_mode)

        lbl_theme_hint = QLabel(
            "پس از ذخیره، تم فوراً اعمال می‌شود؛ در اجرای بعدی هم حفظ می‌شود."
        )
        lbl_theme_hint.setWordWrap(True)
        lbl_theme_hint.setStyleSheet("color: #666; font-size: 12px;")
        theme_form.addRow("", lbl_theme_hint)

        layout.addWidget(theme_group)

        # ─── امنیت: رمز ورود اختیاری ───
        security_group = QGroupBox("امنیت — رمز ورود")
        security_form = QFormLayout(security_group)
        security_form.setSpacing(10)

        self.lbl_password_status = QLabel()
        self._refresh_password_status()
        security_form.addRow("وضعیت:", self.lbl_password_status)

        btn_set_password = QPushButton("🔑 تعیین / تغییر رمز ورود")
        btn_set_password.setObjectName("btnPrimary")
        btn_set_password.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_set_password.clicked.connect(self._change_password)
        security_form.addRow("", btn_set_password)

        btn_remove_password = QPushButton("🔓 حذف رمز ورود")
        btn_remove_password.setObjectName("btnNeutral")
        btn_remove_password.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove_password.clicked.connect(self._remove_password)
        security_form.addRow("", btn_remove_password)

        lbl_security_hint = QLabel(
            "رمز در دیتابیس به‌صورت هش (PBKDF2-SHA256) ذخیره می‌شود — قابل بازیابی نیست؛ "
            "اگر رمز را فراموش کردید، از پشتیبانی بخواهید رکورد password_hash را از جدول settings حذف کند."
        )
        lbl_security_hint.setWordWrap(True)
        lbl_security_hint.setStyleSheet("color: #666; font-size: 12px;")
        security_form.addRow("", lbl_security_hint)

        layout.addWidget(security_group)

        # ─── اطلاعات نسخه و مهاجرت‌های دیتابیس ───
        info_group = QGroupBox("اطلاعات نسخه")
        info_layout = QFormLayout(info_group)
        info_layout.setSpacing(10)

        schema_v = get_current_schema_version()
        migration_note = (
            "به‌روز ✓" if schema_v == LATEST_VERSION
            else f"نیاز به به‌روزرسانی (در اجرای بعدی انجام می‌شود)"
        )
        lbl_schema = QLabel(f"نسخه {schema_v} — {migration_note}")
        lbl_schema.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addRow("نسخه ساختار دیتابیس:", lbl_schema)

        lbl_app = QLabel(f"{APP_NAME} — نسخه {APP_VERSION}")
        lbl_app.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addRow("نسخه نرم‌افزار:", lbl_app)

        last_migration = get_last_migration_info()
        lbl_last = QLabel(last_migration if last_migration else "مهاجرتی اجرا نشده است")
        lbl_last.setWordWrap(True)
        lbl_last.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_layout.addRow("آخرین مهاجرت:", lbl_last)

        layout.addWidget(info_group)

        # ─── لاگ و ابزارها ───
        tools_row = QHBoxLayout()
        btn_view_log = QPushButton("📄 مشاهده لاگ خطاها")
        btn_view_log.setObjectName("btnNeutral")
        btn_view_log.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_view_log.clicked.connect(self._view_app_log)
        tools_row.addWidget(btn_view_log)
        tools_row.addStretch()
        layout.addLayout(tools_row)

        btn_save = QPushButton("💾 ذخیره تنظیمات")
        btn_save.setStyleSheet(
            "background-color: #2ecc71; color: white; padding: 10px; "
            "font-size: 14px; border-radius: 5px; border: none;"
        )
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        # توجه: استایل محلی برای QGroupBox حذف شد — قاعده معیوب «right» در RTL
        # عنوان گروه‌ها را می‌شکست؛ استایل سالم کلی برنامه (assets/styles.css) اعمال می‌شود

        return tab

    def _create_backup_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        btn_layout = QHBoxLayout()

        btn_backup = QPushButton("📦 ساخت پشتیبان")
        btn_backup.setStyleSheet(
            "background-color: #3498db; color: white; padding: 8px 20px; "
            "font-size: 14px; border-radius: 5px; border: none;"
        )
        btn_backup.clicked.connect(self._create_backup)

        btn_restore = QPushButton("♻️ بازگردانی")
        btn_restore.setStyleSheet(
            "background-color: #f39c12; color: white; padding: 8px 20px; "
            "font-size: 14px; border-radius: 5px; border: none;"
        )
        btn_restore.clicked.connect(self._restore_backup)

        btn_open = QPushButton("📂 باز کردن پوشه")
        btn_open.setStyleSheet(
            "background-color: #95a5a6; color: white; padding: 8px 20px; "
            "font-size: 14px; border-radius: 5px; border: none;"
        )
        btn_open.clicked.connect(self._open_backup_folder)

        btn_layout.addWidget(btn_backup)
        btn_layout.addWidget(btn_restore)
        btn_layout.addWidget(btn_open)
        layout.addLayout(btn_layout)

        group = QGroupBox("تاریخچه پشتیبان‌ها")
        group_layout = QVBoxLayout(group)

        self.backup_table = QTableWidget(0, 4)
        self.backup_table.setHorizontalHeaderLabels(["نام فایل", "تاریخ", "وضعیت", "مسیر"])
        self.backup_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.backup_table.setColumnHidden(3, True)
        self.backup_table.setAlternatingRowColors(True)
        self.backup_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.backup_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        group_layout.addWidget(self.backup_table)

        layout.addWidget(group)

        tab.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; border: 1px solid #ddd; border-radius: 8px; margin-top: 10px; padding-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; right: 10px; padding: 0 5px; }
            QTableWidget { border: 1px solid #ddd; border-radius: 5px; font-size: 13px; }
            QTableWidget::item { padding: 4px; }
            QHeaderView::section { background-color: #1a1a2e; color: white; font-weight: bold; padding: 5px; border: none; }
        """)

        return tab

    def _load_setting(self, widget_name, setting_key):
        record = db.fetch_one("SELECT value FROM settings WHERE key=?", (setting_key,))
        checkbox = getattr(self, widget_name)
        if record and record["value"] == "1":
            checkbox.setChecked(True)

    def _load_setting_value(self, setting_key, default=""):
        record = db.fetch_one("SELECT value FROM settings WHERE key=?", (setting_key,))
        return record["value"] if record and record["value"] is not None else default

    def _browse_logo(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "انتخاب لوگو", "", "تصاویر (*.png *.jpg *.jpeg *.bmp)"
        )
        if filepath:
            self.org_logo_input.setText(filepath)

    def _browse_secondary_path(self):
        filepath = QFileDialog.getExistingDirectory(
            self, "انتخاب پوشه مقصد پشتیبان دوم"
        )
        if filepath:
            self.secondary_path_input.setText(filepath)

    def _refresh_password_status(self):
        try:
            if auth.is_password_set():
                self.lbl_password_status.setText("🟢 رمز ورود فعال است — باز شدن برنامه با رمز")
                self.lbl_password_status.setStyleSheet("color: #27ae60; font-weight: bold;")
            else:
                self.lbl_password_status.setText("⚪ رمزی ثبت نشده — برنامه بدون رمز باز می‌شود")
                self.lbl_password_status.setStyleSheet("color: #7f8c8d;")
        except Exception:
            self.lbl_password_status.setText("—")

    def _run_auto_backup_now(self):
        """اجرای دستی مکانیزم پشتیبان‌گیری روزانه (با احترام به قاعده یک‌بار در روز)"""
        reply = QMessageBox.question(
            self, "پشتیبان‌گیری خودکار",
            "اگر امروز پشتیبان خودکار گرفته نشده باشد، همین حالا گرفته می‌شود.\n"
            "ادامه می‌دهید؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            path = auto_backup_if_needed()
            if path:
                QMessageBox.information(
                    self, "موفق",
                    f"پشتیبان خودکار ساخته شد:\n{path}"
                )
            else:
                QMessageBox.information(
                    self, "انجام نشد",
                    "پشتیبان‌گیری خودکار انجام نشد.\n"
                    "دلایل ممکن: گزینه‌ی پشتیبان‌گیری خودکار غیرفعال است\n"
                    "(آن را بالا تیک بزنید و ذخیره کنید) یا امروز قبلاً پشتیبان گرفته شده است."
                )
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در پشتیبان‌گیری: {e}")

    def _run_secondary_backup_now(self):
        """اجرای فوری پشتیبان دوم (بدون انتظار برای قاعده هفتگی)"""
        path = self.secondary_path_input.text().strip()
        if not path:
            QMessageBox.warning(
                self, "مسیر مشخص نیست",
                "اول مسیر مقصد را انتخاب کنید (مسیر مقصد در همین گروه)."
            )
            return
        # مسیر فرم ذخیره می‌شود تا تابع سرویس آن را بخواند
        try:
            db.execute(
                """INSERT INTO settings (key, value) VALUES ('secondary_backup_path', ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (path,)
            )
            from services.backup import run_secondary_backup_if_needed
            status, copied = run_secondary_backup_if_needed(force=True)
            if status == "created":
                QMessageBox.information(
                    self, "موفق",
                    f"پشتیبان دوم کپی شد:\n{copied}\n\n"
                    "مهم: در پایان کار فلش/دیسک مقصد را جدا نکنید تا کپی کامل بماند."
                )
            elif status == "unreachable":
                QMessageBox.warning(
                    self, "مسیر در دسترس نیست",
                    "کپی انجام نشد — مسیر مقصد در دسترس نیست.\n"
                    "فلش/درایو شبکه را بررسی کنید و دوباره تلاش کنید."
                )
            else:
                QMessageBox.warning(
                    self, "انجام نشد",
                    f"کپی انجام نشد ({status}). جزئیات در لاگ برنامه."
                )
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در پشتیبان دوم: {e}")

    def _apply_theme_now(self, dark: bool):
        """سوییچ فوری تم روشن/تیره — کل برنامه همان لحظه عوض می‌شود"""
        try:
            from PyQt6.QtWidgets import QApplication
            import config
            name = "styles_dark.css" if dark else "styles.css"
            qss_path = config.ASSETS_DIR / name
            if qss_path.exists():
                qss = qss_path.read_text(encoding="utf-8")
                app = QApplication.instance()
                if app:
                    app.setStyleSheet(qss)
                    app._current_theme = "dark" if dark else "light"
        except Exception as e:
            QMessageBox.warning(self, "—", f"اعمال فوری تم ناموفق بود: {e}\nدر اجرای بعدی اعمال می‌شود.")

    def _load_backup_keep(self):
        rec = db.fetch_one("SELECT value FROM settings WHERE key='backup_keep_count'")
        try:
            return max(3, min(365, int(rec["value"]))) if rec else 30
        except (ValueError, TypeError):
            return 30

    def _change_password(self):
        """تعیین/تغییر رمز ورود — با تأیید رمز فعلی (اگر فعال باشد) و تکرار رمز جدید"""
        try:
            if auth.is_password_set():
                current, ok = QInputDialog.getText(
                    self, "رمز فعلی", "رمز فعلی را وارد کنید:",
                    QLineEdit.EchoMode.Password
                )
                if not ok:
                    return
                if not auth.verify_password(current):
                    QMessageBox.warning(self, "خطا", "رمز فعلی نادرست است.")
                    return

            new1, ok = QInputDialog.getText(
                self, "رمز جدید", "رمز جدید را وارد کنید (حداقل ۴ کاراکتر):",
                QLineEdit.EchoMode.Password
            )
            if not ok:
                return
            new1 = new1.strip()
            if len(new1) < 4:
                QMessageBox.warning(self, "خطا", "رمز باید حداقل ۴ کاراکتر باشد.")
                return

            new2, ok = QInputDialog.getText(
                self, "تکرار رمز", "رمز جدید را مجدداً وارد کنید:",
                QLineEdit.EchoMode.Password
            )
            if not ok:
                return
            if new2.strip() != new1:
                QMessageBox.warning(self, "خطا", "دو رمز یکسان نیستند.")
                return

            auth.set_password(new1)
            self._refresh_password_status()
            QMessageBox.information(
                self, "موفق",
                "رمز ورود ثبت شد ✓\nاز اجرای بعدی، باز شدن برنامه با رمز انجام می‌شود."
            )
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ثبت رمز: {e}")

    def _remove_password(self):
        """حذف رمز ورود — فقط با تأیید رمز فعلی"""
        try:
            if not auth.is_password_set():
                QMessageBox.information(self, "—", "در حال حاضر رمزی ثبت نشده است.")
                return
            current, ok = QInputDialog.getText(
                self, "حذف رمز", "برای حذف رمز، رمز فعلی را وارد کنید:",
                QLineEdit.EchoMode.Password
            )
            if not ok:
                return
            if not auth.verify_password(current):
                QMessageBox.warning(self, "خطا", "رمز نادرست است.")
                return
            reply = QMessageBox.question(
                self, "تأیید حذف",
                "رمز ورود حذف شود؟ برنامه بدون رمز باز خواهد شد.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            auth.clear_password()
            self._refresh_password_status()
            QMessageBox.information(self, "موفق", "رمز ورود حذف شد ✓")
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در حذف رمز: {e}")

    def _view_app_log(self):
        """نمایش آخرین خطوط لاگ برنامه در دیالوگ خوانا"""
        from PyQt6.QtWidgets import QDialog, QPlainTextEdit
        dlg = QDialog(self)
        dlg.setWindowTitle("لاگ برنامه — data/app.log (آخرین ۵۰۰ خط)")
        dlg.resize(760, 520)
        lay = QVBoxLayout(dlg)
        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(app_log.read_recent_lines(500))
        lay.addWidget(txt)
        btn_close = QPushButton("بستن")
        btn_close.clicked.connect(dlg.accept)
        lay.addWidget(btn_close)
        dlg.exec()

    def _save_settings(self):
        try:
            # UPSERT: اگر کلید هنوز seed نشده باشد (نصب قدیمی)، رکورد جدید می‌سازد؛
            # اگر باشد، به‌روزرسانی می‌کند — هیچ‌وقت بی‌صدا شکست نمی‌خورد
            db.execute(
                """INSERT INTO settings (key, value) VALUES ('auto_backup', ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                ("1" if self.chk_auto_backup.isChecked() else "0",)
            )
            db.execute(
                """INSERT INTO settings (key, value) VALUES ('backup_keep_count', ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (str(self.spin_backup_keep.value()),)
            )
            db.execute(
                """INSERT INTO settings (key, value) VALUES ('secondary_backup_enabled', ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                ("1" if self.chk_secondary.isChecked() else "0",)
            )
            db.execute(
                """INSERT INTO settings (key, value) VALUES ('secondary_backup_path', ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (self.secondary_path_input.text().strip(),)
            )
            db.execute(
                """INSERT INTO settings (key, value) VALUES ('ui_theme', ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                ("dark" if self.chk_dark_mode.isChecked() else "light",)
            )
            # اعمال فوری تم بدون نیاز به اجرای دوباره
            self._apply_theme_now(self.chk_dark_mode.isChecked())
            db.execute(
                """INSERT INTO settings (key, value) VALUES ('org_title', ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (self.org_title_input.text().strip(),)
            )
            db.execute(
                """INSERT INTO settings (key, value) VALUES ('org_logo_path', ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (self.org_logo_input.text().strip(),)
            )
            clear_org_cache()  # چاپ بعدی سربرگ جدید را می‌گیرد
            show_toast(self, "تنظیمات ذخیره شد ✓", "success")
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"خطا در ذخیره: {e}")

    def _load_backups(self):
        try:
            records = get_backup_list()
            self.backup_table.setRowCount(0)
            for rec in records:
                row = self.backup_table.rowCount()
                self.backup_table.insertRow(row)
                self.backup_table.setItem(row, 0, QTableWidgetItem(rec["filename"] or ""))
                self.backup_table.setItem(row, 1, QTableWidgetItem(rec["created_at"] or ""))

                status = "✅ موفق" if rec["status"] == "success" else f"❌ {rec['status']}"
                status_item = QTableWidgetItem(status)
                if rec["status"] == "success":
                    status_item.setForeground(QColor("#2ecc71"))
                else:
                    status_item.setForeground(QColor("#e74c3c"))
                self.backup_table.setItem(row, 2, status_item)
                self.backup_table.setItem(row, 3, QTableWidgetItem(rec["file_path"] or ""))
        except Exception as e:
            traceback.print_exc()

    def _create_backup(self):
        reply = QMessageBox.question(
            self, "پشتیبان‌گیری",
            "آیا می‌خواهید هم‌اکنون فایل پشتیبان ساخته شود؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        path = create_backup()
        if path:
            import os as _os
            show_toast(self, f"پشتیبان ساخته شد: {_os.path.basename(path)}", "success", 3200)
            self._load_backups()
        else:
            QMessageBox.critical(self, "خطا", "پشتیبان‌گیری ناموفق بود")

    def _restore_backup(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "انتخاب فایل پشتیبان", str(BACKUP_DIR), "ZIP (*.zip)"
        )
        if not filepath:
            return

        reply = QMessageBox.question(
            self, "بازگردانی",
            "⚠️ هشدار: بازگردانی، داده‌های فعلی را جایگزین می‌کند.\n"
            "آیا مطمئن هستید؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if restore_backup(filepath):
            QMessageBox.information(self, "موفق", "بازگردانی با موفقیت انجام شد ✓\nبرنامه را مجدداً اجرا کنید.")
        else:
            QMessageBox.critical(self, "خطا", "بازگردانی ناموفق بود")

    def _open_backup_folder(self):
        import subprocess
        path = str(BACKUP_DIR)
        os.makedirs(path, exist_ok=True)
        try:
            if os.name == 'nt':
                subprocess.Popen(f'explorer "{path}"')
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"باز کردن پوشه ناموفق بود: {e}")