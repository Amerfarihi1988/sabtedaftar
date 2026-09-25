"""
پنجره مدیریت گواهی‌های تولید
"""
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFormLayout, QComboBox, QDoubleSpinBox
)
from PyQt6.QtGui import QColor
from database.db_manager import db
from services.quota import is_cert_expired, is_expiring_soon, _parse_shamsi
from ui.shamsi_calendar import is_valid_shamsi_date
import jdatetime


def _settle_company_debts_tx(tx, cert_id, company_id, unit_id, total_amount):
    """
    تسویه بدهی‌های تسویه‌نشده‌ی شرکت/واحد از گواهی تازه‌ساخت (داخل تراکنش باز).

    ترتیب درست:
    1. مبلغ کل گواهی به باقیمانده تبدیل می‌شود (کسر بدهی از سهمیه)
    2. ردیف‌های بدهیِ همان شرکت/واحد به گواهی جدید وصل و تسویه می‌شوند
       (certificate_id واقعی ثبت می‌شود تا restore_permit_quota_tx بعداً
       روی گواهی درست کار کند — نه ساب‌کوئری شرکتی که ردیف‌های
       مجوزهای حذف‌شده را هم می‌گرفت)
    """
    debt_rows = tx.fetch_all(
        """SELECT ei.id, ei.amount FROM exit_items ei
           JOIN exit_permits ep ON ei.exit_permit_id = ep.id
           WHERE ep.company_id = ? AND ei.is_debt = 1
           AND ei.debt_settled = 0 AND ei.unit_id = ?
           ORDER BY ei.id""",
        (company_id, unit_id)
    )
    debt_total = sum(r["amount"] for r in debt_rows)

    # گواهی تازه با کلِ سهمیه ثبت شده؛ بدهی از آن کسر می‌شود
    remaining = max(0.0, total_amount - debt_total)
    status = 'active' if remaining > 0 else 'exhausted'
    tx.execute(
        "UPDATE certificates SET remaining_amount=?, status=? WHERE id=?",
        (remaining, status, cert_id)
    )

    # وصل‌کردن واقعی ردیف‌های بدهی به گواهی جدید + تسویه
    if debt_rows:
        tx.execute(
            """UPDATE exit_items SET debt_settled = 1, certificate_id = ?
               WHERE id IN (SELECT ei.id FROM exit_items ei
                            JOIN exit_permits ep ON ei.exit_permit_id = ep.id
                            WHERE ep.company_id = ? AND ei.is_debt = 1
                            AND ei.debt_settled = 0 AND ei.unit_id = ?)""",
            (cert_id, company_id, unit_id)
        )
    return debt_total


class CertificateFormDialog(QDialog):
    """دیالوگ افزودن/ویرایش گواهی تولید"""

    def __init__(self, parent=None, cert_data=None):
        super().__init__(parent)
        self.cert_data = cert_data
        self.setWindowTitle("ویرایش گواهی" if cert_data else "افزودن گواهی تولید")
        self.setFixedSize(500, 580)
        self._setup_ui()
        if cert_data:
            self._load_data()
        else:
            self._prefill_date()
            self._check_debt()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(10)

        # انتخاب شرکت
        self.company_combo = QComboBox()
        self._load_companies()
        form.addRow("شرکت:", self.company_combo)

        # شماره گواهی
        self.cert_number_input = QLineEdit()
        self.cert_number_input.setPlaceholderText("شماره گواهی")
        form.addRow("شماره گواهی:", self.cert_number_input)

        # نوع کالا
        self.product_type_input = QLineEdit()
        self.product_type_input.setPlaceholderText("نوع کالای گواهی")
        form.addRow("نوع کالا:", self.product_type_input)

        # مقدار کل مجاز
        self.total_amount_input = QDoubleSpinBox()
        self.total_amount_input.setRange(0, 9999999999)
        self.total_amount_input.setDecimals(2)
        self.total_amount_input.setSingleStep(1)
        form.addRow("مقدار کل مجاز:", self.total_amount_input)

        # واحد
        self.unit_combo = QComboBox()
        self._load_units()
        form.addRow("واحد:", self.unit_combo)

        # تاریخ گواهی
        self.issue_date_input = QLineEdit()
        self.issue_date_input.setPlaceholderText("مثال: 1405/03/15")
        form.addRow("تاریخ گواهی:", self.issue_date_input)

        # تاریخ انقضا (اختیاری — گواهی بدون انقضا معتبر است)
        self.expiry_date_input = QLineEdit()
        self.expiry_date_input.setPlaceholderText("مثال: 1406/03/15 — خالی = بدون انقضا")
        form.addRow("تاریخ انقضا:", self.expiry_date_input)

        layout.addLayout(form)

        # برچسب اطلاعات بدهی
        self.debt_info_label = QLabel()
        self.debt_info_label.setStyleSheet(
            "color: #e74c3c; font-size: 12px; padding: 5px; "
            "background-color: #fadbd8; border-radius: 5px;"
        )
        self.debt_info_label.setWordWrap(True)
        self.debt_info_label.hide()
        layout.addWidget(self.debt_info_label)

        # دکمه‌ها
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("انصراف")
        btn_cancel.setFixedWidth(100)
        btn_cancel.setStyleSheet(
            "padding: 8px; font-size: 13px; border-radius: 5px; border: 1px solid #ccc;"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("💾 ذخیره")
        btn_save.setFixedWidth(100)
        btn_save.setStyleSheet(
            "background-color: #2ecc71; color: white; padding: 8px; "
            "font-size: 13px; border-radius: 5px; border: none;"
        )
        btn_save.clicked.connect(self._save)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        # اتصال سیگنال‌ها
        self.company_combo.currentIndexChanged.connect(self._check_debt)
        self.unit_combo.currentIndexChanged.connect(self._check_debt)

        self.setStyleSheet("""
            QLineEdit { padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
            QComboBox { padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
            QDoubleSpinBox { padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
        """)

    def _load_companies(self):
        records = db.fetch_all(
            "SELECT id, name FROM companies WHERE has_certificate = 1 ORDER BY name"
        )
        self.company_combo.clear()
        for rec in records:
            self.company_combo.addItem(rec["name"], rec["id"])

    def _load_units(self):
        records = db.fetch_all("SELECT id, name FROM units ORDER BY name")
        self.unit_combo.clear()
        for rec in records:
            self.unit_combo.addItem(rec["name"], rec["id"])

    def _prefill_date(self):
        today = jdatetime.date.today().strftime("%Y/%m/%d")
        self.issue_date_input.setText(today)

    def _load_data(self):
        idx = self.company_combo.findData(self.cert_data["company_id"])
        if idx >= 0:
            self.company_combo.setCurrentIndex(idx)
        self.cert_number_input.setText(self.cert_data["certificate_number"])
        self.product_type_input.setText(self.cert_data["product_type"])
        self.total_amount_input.setValue(self.cert_data["total_amount"])
        idx_u = self.unit_combo.findData(self.cert_data["unit_id"])
        if idx_u >= 0:
            self.unit_combo.setCurrentIndex(idx_u)
        self.issue_date_input.setText(self.cert_data["issue_date"] or "")
        self.expiry_date_input.setText(self.cert_data.get("expiry_date") or "")

        # در حالت ویرایش، تغییر شرکت و واحد غیرفعال است
        self.company_combo.setEnabled(False)
        self.unit_combo.setEnabled(False)

    def _get_debt_amount(self):
        """مقدار بدهی تسویه‌نشده‌ی شرکت انتخابی با واحد انتخابی"""
        if self.company_combo.count() == 0 or self.unit_combo.count() == 0:
            return 0
        company_id = self.company_combo.currentData()
        unit_id = self.unit_combo.currentData()
        if company_id is None or unit_id is None:
            return 0
        result = db.fetch_one(
            """SELECT COALESCE(SUM(ei.amount), 0) as debt
               FROM exit_items ei
               JOIN exit_permits ep ON ei.exit_permit_id = ep.id
               WHERE ep.company_id = ? AND ei.is_debt = 1
               AND ei.debt_settled = 0 AND ei.unit_id = ?""",
            (company_id, unit_id)
        )
        return result["debt"] if result else 0

    def _check_debt(self):
        """بررسی و نمایش اطلاعات بدهی"""
        if self.cert_data:
            return
        debt = self._get_debt_amount()
        if debt > 0:
            unit_name = self.unit_combo.currentText()
            self.debt_info_label.setText(
                f"⚠️ این شرکت {debt} {unit_name} بدهی گواهی دارد.\n"
                f"هنگام ثبت، از مقدار کل گواهی جدید کسر می‌شود."
            )
            self.debt_info_label.show()
        else:
            self.debt_info_label.hide()

    def _save(self):
        if self.company_combo.count() == 0:
            QMessageBox.warning(
                self, "خطا",
                "هیچ شرکتی با گواهی تولید ثبت نشده است.\n"
                "ابتدا در بخش شرکت‌ها، گزینه «دارای گواهی تولید» را فعال کنید."
            )
            return

        cert_number = self.cert_number_input.text().strip()
        if not cert_number:
            QMessageBox.warning(self, "خطا", "شماره گواهی الزامی است")
            return

        product_type = self.product_type_input.text().strip()
        if not product_type:
            QMessageBox.warning(self, "خطا", "نوع کالا الزامی است")
            return

        total_amount = self.total_amount_input.value()
        if total_amount <= 0:
            QMessageBox.warning(self, "خطا", "مقدار کل باید بزرگتر از صفر باشد")
            return

        company_id = self.company_combo.currentData()
        unit_id = self.unit_combo.currentData()
        issue_date = self.issue_date_input.text().strip()
        if issue_date and not is_valid_shamsi_date(issue_date):
            QMessageBox.warning(
                self, "خطا",
                "تاریخ گواهی نامعتبر است.\n"
                "فرمت صحیح: 1405/03/15 و ماه/روز باید واقعی باشند.\n"
                "(می‌توانید خالی بگذارید یا از تقویم استفاده کنید.)"
            )
            return

        expiry_date = self.expiry_date_input.text().strip()
        if expiry_date and not is_valid_shamsi_date(expiry_date):
            QMessageBox.warning(
                self, "خطا",
                "تاریخ انقضا نامعتبر است.\n"
                "فرمت صحیح: 1406/03/15 و ماه/روز باید واقعی باشند.")
            return
        # انقضا نباید قبل از تاریخ صدور باشد
        if issue_date and expiry_date:
            d1, d2 = _parse_shamsi(issue_date), _parse_shamsi(expiry_date)
            if d1 and d2 and d2 < d1:
                QMessageBox.warning(
                    self, "خطا",
                    "تاریخ انقضا نمی‌تواند قبل از تاریخ صدور گواهی باشد.")
                return

        if self.cert_data:
            # ─── حالت ویرایش: بازمحاسبه باقیمانده ───
            old_total = self.cert_data["total_amount"]
            old_remaining = self.cert_data["remaining_amount"]
            used = old_total - old_remaining
            new_remaining = total_amount - used
            if new_remaining < 0:
                new_remaining = 0
            status = 'active' if new_remaining > 0 else 'exhausted'

            db.execute(
                """UPDATE certificates SET certificate_number=?, product_type=?,
                   total_amount=?, remaining_amount=?, issue_date=?, expiry_date=?, status=?
                   WHERE id=?""",
                (cert_number, product_type, total_amount, new_remaining,
                 issue_date, expiry_date or None, status, self.cert_data["id"])
            )
        else:
            # ─── حالت افزودن: بررسی و تسویه بدهی ───
            debt = self._get_debt_amount()
            if debt > 0:
                if total_amount < debt:
                    QMessageBox.warning(
                        self, "خطا",
                        f"مقدار کل گواهی ({total_amount}) کمتر از بدهی ({debt}) است!"
                    )
                    return

                unit_name = self.unit_combo.currentText()
                reply = QMessageBox.question(
                    self, "تأیید کسر بدهی",
                    f"این شرکت {debt} {unit_name} بدهی دارد.\n"
                    f"از مقدار کل گواهی جدید کسر شود؟\n"
                    f"باقیمانده پس از کسر: {total_amount - debt} {unit_name}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            remaining = total_amount - debt
            status = 'active' if remaining > 0 else 'exhausted'

            # ثبت گواهی + تسویه بدهی‌ها در یک تراکنش اتمیک؛
            # certificate_id واقعی روی ردیف‌های بدهی ثبت می‌شود تا
            # بازگردانی سهمیه در ویرایش/حذف مجوز همیشه روی گواهی درست کار کند
            with db.transaction() as tx:
                cert_id = tx.insert(
                    """INSERT INTO certificates
                       (company_id, certificate_number, product_type, total_amount,
                        remaining_amount, unit_id, issue_date, expiry_date, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (company_id, cert_number, product_type, total_amount,
                     remaining, unit_id, issue_date, expiry_date or None, status)
                )
                if debt > 0:
                    _settle_company_debts_tx(tx, cert_id, company_id, unit_id, total_amount)

        self.accept()
from PyQt6.QtCore import Qt, pyqtSignal

class CertificateWindow(QWidget):
    """پنجره مدیریت گواهی‌های تولید"""
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # setWindowTitle و resize حذف
        self._setup_ui()
        self._load_certificates()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # هدر و جستجو
        header_layout = QHBoxLayout()
        title = QLabel("📜 مدیریت گواهی‌های تولید")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a1a2e;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 جستجو بر اساس نام شرکت...")
        self.search_input.setFixedWidth(300)
        self.search_input.textChanged.connect(self._on_search)
        header_layout.addWidget(self.search_input)
        layout.addLayout(header_layout)

        # جدول
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "شناسه", "شرکت", "شماره گواهی", "نوع کالا",
            "مقدار کل", "باقیمانده", "واحد", "تاریخ", "وضعیت"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # دکمه‌ها
        btn_layout = QHBoxLayout()

        btn_add = QPushButton("➕ افزودن گواهی")
        btn_add.setStyleSheet(
            "background-color: #3498db; color: white; padding: 8px 15px; "
            "font-size: 13px; border-radius: 5px; border: none;"
        )
        btn_add.clicked.connect(self._add_certificate)

        btn_edit = QPushButton("✏️ ویرایش")
        btn_edit.setStyleSheet(
            "background-color: #f39c12; color: white; padding: 8px 15px; "
            "font-size: 13px; border-radius: 5px; border: none;"
        )
        btn_edit.clicked.connect(self._edit_certificate)

        btn_archive = QPushButton("📁 بایگانی")
        btn_archive.setStyleSheet(
            "background-color: #95a5a6; color: white; padding: 8px 15px; "
            "font-size: 13px; border-radius: 5px; border: none;"
        )
        btn_archive.clicked.connect(self._archive_certificate)

        btn_close = QPushButton("بستن")
        btn_close.setStyleSheet(
            "padding: 8px 15px; font-size: 13px; border-radius: 5px; border: 1px solid #ccc;"
        )
        btn_close.clicked.connect(self.back_requested.emit)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_archive)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        self.setStyleSheet("""
            QTableWidget { border: 1px solid #ddd; border-radius: 5px; font-size: 13px; }
            QTableWidget::item { padding: 5px; }
            QHeaderView::section { background-color: #1a1a2e; color: white; font-weight: bold; padding: 5px; border: none; }
            QLineEdit { padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; }
        """)

    def _load_certificates(self, search_text=""):
        if search_text:
            records = db.fetch_all(
                """SELECT cert.*, c.name as company_name, u.name as unit_name
                   FROM certificates cert
                   JOIN companies c ON cert.company_id = c.id
                   JOIN units u ON cert.unit_id = u.id
                   WHERE c.name LIKE ?
                   ORDER BY cert.created_at DESC""",
                (f"%{search_text}%",)
            )
        else:
            records = db.fetch_all(
                """SELECT cert.*, c.name as company_name, u.name as unit_name
                   FROM certificates cert
                   JOIN companies c ON cert.company_id = c.id
                   JOIN units u ON cert.unit_id = u.id
                   ORDER BY cert.created_at DESC"""
            )

        self.table.setRowCount(0)
        for rec in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(rec["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(rec["company_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(rec["certificate_number"]))
            self.table.setItem(row, 3, QTableWidgetItem(rec["product_type"]))
            self.table.setItem(row, 4, QTableWidgetItem(str(rec["total_amount"])))
            self.table.setItem(row, 5, QTableWidgetItem(str(rec["remaining_amount"])))
            self.table.setItem(row, 6, QTableWidgetItem(rec["unit_name"]))
            self.table.setItem(row, 7, QTableWidgetItem(rec["issue_date"] or ""))

            status_text = {
                'active': '✅ فعال',
                'exhausted': '⚠️ تمام‌شده',
                'archived': '📁 بایگانی'
            }.get(rec["status"], rec["status"])

            status_item = QTableWidgetItem(status_text)
            if rec["status"] == 'active':
                status_item.setForeground(QColor("#2ecc71"))
                if is_cert_expired(dict(rec)):
                    status_item = QTableWidgetItem("⛔ منقض‌شده")
                    status_item.setForeground(QColor("#B91C1C"))
                elif is_expiring_soon(dict(rec)):
                    status_item = QTableWidgetItem("⏳ نزدیک انقضا")
                    status_item.setForeground(QColor("#D97706"))
            elif rec["status"] == 'exhausted':
                status_item.setForeground(QColor("#e74c3c"))
            else:
                status_item.setForeground(QColor("#95a5a6"))
            self.table.setItem(row, 8, status_item)

    def _on_search(self, text):
        self._load_certificates(text)

    def _add_certificate(self):
        companies = db.fetch_all(
            "SELECT COUNT(*) as cnt FROM companies WHERE has_certificate = 1"
        )
        if companies and companies[0]["cnt"] == 0:
            QMessageBox.warning(
                self, "خطا",
                "هیچ شرکتی با گواهی تولید ثبت نشده است.\n"
                "ابتدا در بخش شرکت‌ها، گزینه «دارای گواهی تولید» را فعال کنید."
            )
            return

        dialog = CertificateFormDialog(self)
        if dialog.exec():
            self._load_certificates(self.search_input.text())

    def _edit_certificate(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "یک گواهی را انتخاب کنید")
            return

        cert_id = int(self.table.item(row, 0).text())
        record = db.fetch_one("SELECT * FROM certificates WHERE id=?", (cert_id,))
        if record:
            dialog = CertificateFormDialog(self, dict(record))
            if dialog.exec():
                self._load_certificates(self.search_input.text())

    def _archive_certificate(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "یک گواهی را انتخاب کنید")
            return

        cert_id = int(self.table.item(row, 0).text())
        cert_name = self.table.item(row, 1).text()
        cert_num = self.table.item(row, 2).text()
        status = self.table.item(row, 8).text()

        if status == "📁 بایگانی":
            # خروج از بایگانی: برگرداندن وضعیت به فعال (اگر باقیمانده > 0) یا تمام‌شده
            rec = db.fetch_one(
                "SELECT remaining_amount FROM certificates WHERE id=?", (cert_id,)
            )
            if not rec:
                return
            new_status = "active" if rec["remaining_amount"] > 0 else "exhausted"
            reply = QMessageBox.question(
                self, "خروج از بایگانی",
                f"گواهی «{cert_num}» از بایگانی خارج و به وضعیت "
                f"«{'فعال' if new_status == 'active' else 'تمام‌شده'}» برگردانده شود؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                db.execute(
                    "UPDATE certificates SET status=? WHERE id=?",
                    (new_status, cert_id)
                )
                self._load_certificates(self.search_input.text())
            return

        # بایگانی عادی — منع بایگانی گواهی دارای بدهی تسویه‌نشده
        debts = db.fetch_all(
            """SELECT COALESCE(SUM(ei.amount), 0) as debt, u.name as unit
               FROM exit_items ei
               JOIN exit_permits ep ON ei.exit_permit_id = ep.id
               JOIN units u ON ei.unit_id = u.id
               WHERE ei.certificate_id = ? AND ei.is_debt = 1 AND ei.debt_settled = 0
               GROUP BY ei.unit_id""",
            (cert_id,)
        )
        if debts:
            debt_text = "، ".join(
                f"{d['debt']:g} {d['unit']}" for d in debts
            )
            QMessageBox.warning(
                self, "خطا",
                f"این گواهی بدهی تسویه‌نشده دارد ({debt_text})\n"
                f"ابتدا با ثبت گواهی جدید، بدهی‌ها را تسویه کنید."
            )
            return

        reply = QMessageBox.question(
            self, "تأیید بایگانی",
            f"آیا از بایگانی گواهی شماره «{cert_num}» متعلق به «{cert_name}» مطمئن هستید؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            db.execute(
                "UPDATE certificates SET status='archived' WHERE id=?",
                (cert_id,)
            )
            self._load_certificates(self.search_input.text())