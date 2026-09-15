"""
پنجره تنظیمات و پشتیبان‌گیری
"""
import os
import traceback
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog,
    QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from database.db_manager import db
from services.backup import create_backup, restore_backup, get_backup_list, auto_backup_if_needed
from config import BACKUP_DIR


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
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("تنظیمات عمومی")
        form = QFormLayout(group)
        form.setSpacing(12)

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
        layout.addStretch()

        btn_save = QPushButton("💾 ذخیره تنظیمات")
        btn_save.setStyleSheet(
            "background-color: #2ecc71; color: white; padding: 10px; "
            "font-size: 14px; border-radius: 5px; border: none;"
        )
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save)

        tab.setStyleSheet("""
            QGroupBox { font-size: 14px; font-weight: bold; border: 1px solid #ddd; border-radius: 8px; margin-top: 10px; padding-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; right: 10px; padding: 0 5px; }
        """)

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

    def _save_settings(self):
        try:
            db.execute(
                "UPDATE settings SET value=? WHERE key='auto_backup'",
                ("1" if self.chk_auto_backup.isChecked() else "0",)
            )
            QMessageBox.information(self, "ذخیره شد", "تنظیمات با موفقیت ذخیره شد ✓")
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
            QMessageBox.information(self, "موفق", f"پشتیبان ساخته شد:\n{path}")
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
            QMessageBox.critical(self, "خطا", "بازگردانی ناموفف بود")

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