"""
صفحه مدیریت شرکت‌ها
"""
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFormLayout, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from database.db_manager import db


class CompanyFormDialog(QDialog):
    """دیالوگ افزودن/ویرایش شرکت"""

    def __init__(self, parent=None, company_data=None):
        super().__init__(parent)
        self.company_data = company_data
        self.setWindowTitle("ویرایش شرکت" if company_data else "افزودن شرکت جدید")
        self.setFixedSize(480, 400)
        self._setup_ui()
        if company_data:
            self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("نام شرکت")
        form.addRow("نام شرکت:", self.name_input)

        self.economic_code_input = QLineEdit()
        self.economic_code_input.setPlaceholderText("کد اقتصادی")
        form.addRow("کد اقتصادی:", self.economic_code_input)

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("تلفن")
        form.addRow("تلفن:", self.phone_input)

        self.ceo_name_input = QLineEdit()
        self.ceo_name_input.setPlaceholderText("نام مدیرعامل")
        form.addRow("نام مدیرعامل:", self.ceo_name_input)

        self.representative_input = QLineEdit()
        self.representative_input.setPlaceholderText("نام نماینده شرکت (ثابت)")
        form.addRow("نام نماینده:", self.representative_input)

        self.has_certificate_check = QCheckBox("این شرکت دارای گواهی تولید است")
        form.addRow("", self.has_certificate_check)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("انصراف")
        btn_cancel.setFixedWidth(100)
        btn_cancel.setObjectName("btnDefault")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("💾 ذخیره")
        btn_save.setFixedWidth(100)
        btn_save.setObjectName("btnSuccess")
        btn_save.clicked.connect(self._save)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _load_data(self):
        self.name_input.setText(self.company_data["name"])
        self.economic_code_input.setText(self.company_data["economic_code"] or "")
        self.phone_input.setText(self.company_data["phone"] or "")
        self.ceo_name_input.setText(self.company_data["ceo_name"] or "")
        self.representative_input.setText(self.company_data["representative_name"] or "")
        self.has_certificate_check.setChecked(bool(self.company_data["has_certificate"]))

    def _save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "خطا", "نام شرکت الزامی است")
            return

        data = (
            name,
            self.economic_code_input.text().strip(),
            self.phone_input.text().strip(),
            self.ceo_name_input.text().strip(),
            self.representative_input.text().strip(),
            1 if self.has_certificate_check.isChecked() else 0,
        )

        if self.company_data:
            db.execute(
                """UPDATE companies SET name=?, economic_code=?, phone=?,
                   ceo_name=?, representative_name=?, has_certificate=?
                   WHERE id=?""",
                (*data, self.company_data["id"])
            )
        else:
            db.execute(
                """INSERT INTO companies
                   (name, economic_code, phone, ceo_name, representative_name, has_certificate)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                data
            )
        self.accept()


class CompanyWindow(QWidget):
    """صفحه مدیریت شرکت‌ها"""

    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_companies()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(15)

        # ─── جستجو ───
        search_layout = QHBoxLayout()
        search_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 جستجوی شرکت (نام، کد اقتصادی، مدیرعامل)...")
        self.search_input.setFixedWidth(320)
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # ─── جدول ───
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["شناسه", "نام شرکت", "کد اقتصادی", "تلفن", "مدیرعامل", "نماینده", "گواهی"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._edit_company)  # دابل‌کلیک = ویرایش
        layout.addWidget(self.table)

        # ─── دکمه‌ها ───
        btn_layout = QHBoxLayout()

        btn_add = QPushButton("➕ افزودن شرکت")
        btn_add.setObjectName("btnPrimary")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._add_company)

        btn_edit = QPushButton("✏️ ویرایش")
        btn_edit.setObjectName("btnWarning")
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.clicked.connect(self._edit_company)

        btn_delete = QPushButton("🗑️ حذف")
        btn_delete.setObjectName("btnDanger")
        btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_delete.clicked.connect(self._delete_company)

        btn_back = QPushButton("بازگشت به داشبورد")
        btn_back.setObjectName("btnDefault")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.back_requested.emit)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_back)
        layout.addLayout(btn_layout)

    def _load_companies(self, search_text=""):
        if search_text:
            records = db.fetch_all(
                """SELECT * FROM companies
                   WHERE name LIKE ? OR economic_code LIKE ? OR ceo_name LIKE ?
                   ORDER BY name""",
                (f"%{search_text}%", f"%{search_text}%", f"%{search_text}%")
            )
        else:
            records = db.fetch_all("SELECT * FROM companies ORDER BY name")

        self.table.setRowCount(0)
        for rec in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(rec["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(rec["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(rec["economic_code"] or ""))
            self.table.setItem(row, 3, QTableWidgetItem(rec["phone"] or ""))
            self.table.setItem(row, 4, QTableWidgetItem(rec["ceo_name"] or ""))
            self.table.setItem(row, 5, QTableWidgetItem(rec["representative_name"] or ""))

            cert_item = QTableWidgetItem("✓ دارد" if rec["has_certificate"] else "—")
            if rec["has_certificate"]:
                cert_item.setForeground(QColor("#10B981"))
            self.table.setItem(row, 6, cert_item)

    def _on_search(self, text):
        self._load_companies(text)

    def _add_company(self):
        dialog = CompanyFormDialog(self)
        if dialog.exec():
            self._load_companies(self.search_input.text())

    def _edit_company(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "یک شرکت را انتخاب کنید")
            return

        company_id = int(self.table.item(row, 0).text())
        record = db.fetch_one("SELECT * FROM companies WHERE id=?", (company_id,))
        if record:
            dialog = CompanyFormDialog(self, dict(record))
            if dialog.exec():
                self._load_companies(self.search_input.text())

    def _delete_company(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "یک شرکت را انتخاب کنید")
            return

        company_id = int(self.table.item(row, 0).text())
        company_name = self.table.item(row, 1).text()

        reply = QMessageBox.question(
            self, "تأیید حذف",
            f"آیا از حذف «{company_name}» مطمئن هستید؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            permits = db.fetch_all(
                "SELECT COUNT(*) as cnt FROM exit_permits WHERE company_id=?",
                (company_id,)
            )
            if permits and permits[0]["cnt"] > 0:
                QMessageBox.warning(
                    self, "خطا",
                    "این شرکت دارای مجوز خروج ثبت‌شده است و قابل حذف نیست"
                )
                return

            certificates = db.fetch_all(
                "SELECT COUNT(*) as cnt FROM certificates WHERE company_id=?",
                (company_id,)
            )
            if certificates and certificates[0]["cnt"] > 0:
                QMessageBox.warning(
                    self, "خطا",
                    "این شرکت دارای گواهی تولید ثبت‌شده است و قابل حذف نیست."
                )
                return

            db.execute("DELETE FROM companies WHERE id=?", (company_id,))
            self._load_companies(self.search_input.text())