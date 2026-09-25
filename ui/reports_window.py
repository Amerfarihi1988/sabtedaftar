"""
صفحه گزارش‌ها: گزارش دوره‌ای PDF + ریز مصرف گواهی
"""
import traceback
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QGroupBox, QFormLayout,
    QFileDialog, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from database.db_manager import db
from services.quota import is_low_quota
from services.report_pdf import (
    generate_period_report_pdf, generate_certificate_report_pdf,
    generate_company_statement_pdf, generate_daily_manifest_pdf,
)
from ui.shamsi_calendar import ShamsiDateEdit, is_valid_shamsi_date
from ui.ui_helpers import show_toast
import os

class ReportsWindow(QWidget):
    """صفحه گزارش‌ها"""

    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self._setup_ui()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در بارگذاری: {e}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        tabs = QTabWidget()
        tabs.addTab(self._create_period_tab(), "گزارش دوره‌ای PDF")
        tabs.addTab(self._create_cert_tab(), "ریز مصرف گواهی")
        layout.addWidget(tabs)

        btn_back = QPushButton("بازگشت به داشبورد")
        btn_back.setObjectName("btnDefault")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.back_requested.emit)
        layout.addWidget(btn_back)

    # ═══════════ تب ۱: گزارش دوره‌ای ═══════════

    def _create_period_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        form_group = QGroupBox("پارامترهای گزارش")
        form = QFormLayout(form_group)
        form.setSpacing(8)

        self.p_company_combo = QComboBox()
        self.p_company_combo.addItem("همه شرکت‌ها", None)
        self._load_companies_into(self.p_company_combo, only_cert=False)
        form.addRow("شرکت:", self.p_company_combo)

        self.p_date_from = ShamsiDateEdit()
        form.addRow("از تاریخ:", self.p_date_from)

        self.p_date_to = ShamsiDateEdit()
        form.addRow("تا تاریخ:", self.p_date_to)

        layout.addWidget(form_group)

        btn_row = QHBoxLayout()
        btn_preview = QPushButton("🔍 پیش‌نمایش نتایج")
        btn_preview.setObjectName("btnPrimary")
        btn_preview.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_preview.clicked.connect(self._preview_period)

        btn_pdf = QPushButton("📄 تولید PDF رسمی")
        btn_pdf.setObjectName("btnSuccess")
        btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pdf.clicked.connect(self._export_period_pdf)

        btn_manifest = QPushButton("📦 مانیفست روزانه PDF")
        btn_manifest.setObjectName("btnWarning")
        btn_manifest.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_manifest.clicked.connect(self._export_daily_manifest)

        btn_row.addWidget(btn_preview)
        btn_row.addWidget(btn_pdf)
        btn_row.addWidget(btn_manifest)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.p_lbl_count = QLabel("برای پیش‌نمایش، بازه تاریخ را وارد و دکمه را بزنید.")
        self.p_lbl_count.setStyleSheet("font-size: 13px; color: #555;")
        layout.addWidget(self.p_lbl_count)

        self.p_table = QTableWidget(0, 6)
        self.p_table.setHorizontalHeaderLabels([
            "شماره ثبت", "تاریخ", "شرکت", "مقصد", "کالاها", "بدهی"
        ])
        self.p_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.p_table.setAlternatingRowColors(True)
        self.p_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.p_table.verticalHeader().setVisible(False)
        layout.addWidget(self.p_table)

        # ذخیره نتایج برای PDF
        self._period_records = []
        return tab

    def _load_companies_into(self, combo, only_cert=False):
        if only_cert:
            records = db.fetch_all(
                "SELECT id, name FROM companies WHERE has_certificate = 1 ORDER BY name"
            )
        else:
            records = db.fetch_all("SELECT id, name FROM companies ORDER BY name")
        for rec in records:
            combo.addItem(rec["name"], rec["id"])

    def _collect_period_records(self):
        """جمع‌آوری رکوردهای بازه انتخابی"""
        date_from = self.p_date_from.text().strip()
        date_to = self.p_date_to.text().strip()

        conditions = []
        params = []

        company_id = self.p_company_combo.currentData()
        if company_id is not None:
            conditions.append("ep.company_id = ?")
            params.append(company_id)
        if date_from:
            if not is_valid_shamsi_date(date_from):
                QMessageBox.warning(
                    self, "خطا",
                    f"«از تاریخ» نامعتبر است: {date_from}\nمثال صحیح: 1405/01/01"
                )
                return []
            conditions.append("ep.exit_date >= ?")
            params.append(date_from)
        if date_to:
            if not is_valid_shamsi_date(date_to):
                QMessageBox.warning(
                    self, "خطا",
                    f"«تا تاریخ» نامعتبر است: {date_to}\nمثال صحیح: 1405/12/29"
                )
                return []
            conditions.append("ep.exit_date <= ?")
            params.append(date_to)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        query = f"""
            SELECT ep.id, ep.permit_number, ep.exit_date, c.name as company_name,
                   ep.destination, ep.customs_representative
            FROM exit_permits ep
            JOIN companies c ON ep.company_id = c.id
            {where_clause}
            ORDER BY ep.exit_date, ep.created_at
        """
        permits = db.fetch_all(query, tuple(params))

        records = []
        for p in permits:
            items = db.fetch_all(
                """SELECT ei.product_name, ei.amount, u.name as unit_name, ei.is_debt
                   FROM exit_items ei
                   JOIN units u ON ei.unit_id = u.id
                   WHERE ei.exit_permit_id = ?""",
                (p["id"],)
            )
            items_parts = []
            debt_parts = []
            for it in items:
                amt = int(it["amount"]) if it["amount"] == int(it["amount"]) else it["amount"]
                items_parts.append(f"{it['product_name']} — {amt} {it['unit_name']}")
                if it["is_debt"]:
                    debt_parts.append(f"{it['product_name']}: {amt} {it['unit_name']}")
            records.append({
                "permit_number": p["permit_number"],
                "exit_date": p["exit_date"],
                "company_name": p["company_name"],
                "destination": p["destination"] or "",
                "customs_representative": p["customs_representative"] or "",
                "items_text": " | ".join(items_parts),
                "debt_text": " | ".join(debt_parts),
            })
        return records

    def _preview_period(self):
        try:
            self._period_records = self._collect_period_records()
            self.p_table.setRowCount(0)
            for rec in self._period_records:
                row = self.p_table.rowCount()
                self.p_table.insertRow(row)
                self.p_table.setItem(row, 0, QTableWidgetItem(rec["permit_number"]))
                self.p_table.setItem(row, 1, QTableWidgetItem(rec["exit_date"]))
                self.p_table.setItem(row, 2, QTableWidgetItem(rec["company_name"]))
                self.p_table.setItem(row, 3, QTableWidgetItem(rec["destination"]))
                self.p_table.setItem(row, 4, QTableWidgetItem(rec["items_text"]))
                if rec["debt_text"]:
                    item = QTableWidgetItem(f"🔴 {rec['debt_text']}")
                    item.setForeground(QColor("#E11D48"))
                else:
                    item = QTableWidgetItem("—")
                self.p_table.setItem(row, 5, item)
            self.p_table.resizeRowsToContents()
            self.p_lbl_count.setText(f"{self._to_persian(len(self._period_records))} مجوز یافت شد")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در پیش‌نمایش: {e}")

    def _export_period_pdf(self):
        date_from = self.p_date_from.text().strip()
        date_to = self.p_date_to.text().strip()
        if date_from and not is_valid_shamsi_date(date_from):
            QMessageBox.warning(
                self, "خطا",
                f"«از تاریخ» نامعتبر است: {date_from}\nمثال صحیح: 1405/01/01"
            )
            return
        if date_to and not is_valid_shamsi_date(date_to):
            QMessageBox.warning(
                self, "خطا",
                f"«تا تاریخ» نامعتبر است: {date_to}\nمثال صحیح: 1405/12/29"
            )
            return

        if not self._period_records:
            reply = QMessageBox.question(
                self, "پیش‌نمایش نشده",
                "هنوز پیش‌نمایش نگرفته‌اید. ابتدا «پیش‌نمایش نتایج» را بزنید.\n"
                "آیا اکنون پیش‌نمایش گرفته و ادامه دهیم؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._preview_period()
            else:
                return

        if not self._period_records:
            QMessageBox.warning(self, "خطا", "هیچ داده‌ای در این بازه وجود ندارد")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "ذخیره گزارش PDF",
            f"گزارش_دوره‌ای_خروج_{self.p_date_from.text().replace('/', '-')}_تا_{self.p_date_to.text().replace('/', '-')}.pdf",
            "PDF (*.pdf)"
        )
        if not filepath:
            return

        company_name = self.p_company_combo.currentText()
        if self.p_company_combo.currentData() is None:
            company_name = None

        ok = generate_period_report_pdf(
            filepath,
            self.p_date_from.text().strip() or "ابتدا",
            self.p_date_to.text().strip() or "کنون",
            company_name,
            self._period_records
        )
        if ok:
            show_toast(self, f"گزارش PDF ذخیره شد: {os.path.basename(filepath)}", "success", 3200)
        else:
            QMessageBox.critical(self, "خطا", "تولید PDF ناموفق بود")

    def _export_daily_manifest(self):
        """مانیفست روزانه: خروج‌های یک تاریخ مشخص در یک سند رسمی"""
        exit_date = self.p_date_to.text().strip() or self.p_date_from.text().strip()
        if not exit_date:
            QMessageBox.warning(
                self, "خطا",
                "تاریخ مانیفست را در فیلد «تا تاریخ» (یا «از تاریخ») وارد کنید"
            )
            return
        if not is_valid_shamsi_date(exit_date):
            QMessageBox.warning(
                self, "خطا",
                f"تاریخ نامعتبر است: {exit_date}\nمثال صحیح: 1405/06/16"
            )
            return

        try:
            permits = db.fetch_all(
                """SELECT ep.id, ep.permit_number, ep.destination,
                          c.name as company_name
                   FROM exit_permits ep
                   JOIN companies c ON ep.company_id = c.id
                   WHERE ep.exit_date = ?
                   ORDER BY ep.created_at""",
                (exit_date,)
            )
            if not permits:
                QMessageBox.information(
                    self, "داده‌ای نیست",
                    f"در تاریخ «{exit_date}» خروجی ثبت نشده است."
                )
                return

            records = []
            total_items = 0
            total_amount = 0.0
            for p in permits:
                items = db.fetch_all(
                    """SELECT ei.product_name, ei.amount, u.name as unit_name
                       FROM exit_items ei
                       JOIN units u ON ei.unit_id = u.id
                       WHERE ei.exit_permit_id = ? ORDER BY ei.id""",
                    (p["id"],)
                )
                total_items += len(items)
                total_amount += sum(it["amount"] for it in items)
                items_text = " | ".join(
                    f"{it['product_name']} — {it['amount']:g} {it['unit_name']}"
                    for it in items
                )
                records.append({
                    "permit_number": p["permit_number"],
                    "company_name": p["company_name"],
                    "destination": p["destination"] or "",
                    "items_text": items_text,
                })

            filepath, _ = QFileDialog.getSaveFileName(
                self, "ذخیره مانیفست روزانه",
                f"مانیفست_{exit_date.replace('/', '-')}.pdf",
                "PDF (*.pdf)"
            )
            if not filepath:
                return

            ok = generate_daily_manifest_pdf(
                filepath, exit_date, records,
                {"permits": len(permits), "items": total_items,
                 "total_amount": total_amount}
            )
            if ok:
                show_toast(self, f"مانیفست ذخیره شد: {os.path.basename(filepath)}", "success", 3200)
            else:
                QMessageBox.critical(self, "خطا", "تولید PDF ناموفق بود")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در مانیفست: {e}")

    # ═══════════ تب ۲: ریز مصرف گواهی ═══════════

    def _create_cert_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        form_group = QGroupBox("انتخاب شرکت گواهی‌دار")
        form = QFormLayout(form_group)

        self.c_company_combo = QComboBox()
        self.c_company_combo.setPlaceholderText("انتخاب شرکت...")
        self.c_company_combo.currentIndexChanged.connect(self._load_certificates)
        form.addRow("شرکت:", self.c_company_combo)

        layout.addWidget(form_group)

        # جدول گواهی‌ها
        certs_group = QGroupBox("گواهی‌های شرکت")
        certs_layout = QVBoxLayout(certs_group)

        self.cert_table = QTableWidget(0, 6)
        self.cert_table.setHorizontalHeaderLabels([
            "شناسه", "شماره گواهی", "نوع کالا", "مقدار کل", "باقیمانده", "واحد"
        ])
        self.cert_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cert_table.setColumnHidden(0, True)
        self.cert_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.cert_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cert_table.setMaximumHeight(180)
        self.cert_table.verticalHeader().setVisible(False)
        certs_layout.addWidget(self.cert_table)
        layout.addWidget(certs_group)

        btn_row = QHBoxLayout()

        btn_statement = QPushButton("📑 صورتحساب شرکت (PDF)")
        btn_statement.setObjectName("btnWarning")
        btn_statement.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_statement.clicked.connect(self._export_company_statement)

        btn_show = QPushButton("📋 نمایش ریز مصرف")
        btn_show.setObjectName("btnPrimary")
        btn_show.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_show.clicked.connect(self._show_consumption)

        btn_pdf = QPushButton("📄 خروجی PDF ریز مصرف")
        btn_pdf.setObjectName("btnSuccess")
        btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pdf.clicked.connect(self._export_cert_pdf)

        btn_row.addWidget(btn_show)
        btn_row.addWidget(btn_pdf)
        btn_row.addWidget(btn_statement)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # جدول مصرف‌ها
        cons_group = QGroupBox("ریز مصرف گواهی انتخابی")
        cons_layout = QVBoxLayout(cons_group)

        self.c_lbl_summary = QLabel("ابتدا گواهی را انتخاب و «نمایش ریز مصرف» را بزنید.")
        self.c_lbl_summary.setStyleSheet("font-size: 13px; color: #555;")
        cons_layout.addWidget(self.c_lbl_summary)

        self.cons_table = QTableWidget(0, 5)
        self.cons_table.setHorizontalHeaderLabels([
            "تاریخ خروج", "شماره ثبت", "نام کالا", "مقدار", "وضعیت"
        ])
        self.cons_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cons_table.setAlternatingRowColors(True)
        self.cons_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.cons_table.verticalHeader().setVisible(False)
        cons_layout.addWidget(self.cons_table)

        layout.addWidget(cons_group, stretch=1)

        # ذخیره وضعیت
        self._current_cert = None
        self._current_consumptions = []
        self._current_unit_name = ""

        # بارگذاری شرکت‌های گواهی‌دار
        self._load_companies_into(self.c_company_combo, only_cert=True)
        return tab

    def _load_certificates(self):
        self.cert_table.setRowCount(0)
        self.cons_table.setRowCount(0)
        self.c_lbl_summary.setText("ابتدا گواهی را انتخاب و «نمایش ریز مصرف» را بزنید.")
        self._current_cert = None

        company_id = self.c_company_combo.currentData()
        if company_id is None:
            return

        records = db.fetch_all(
            """SELECT cert.*, u.name as unit_name
               FROM certificates cert
               JOIN units u ON cert.unit_id = u.id
               WHERE cert.company_id = ?
               ORDER BY cert.created_at DESC""",
            (company_id,)
        )
        for rec in records:
            row = self.cert_table.rowCount()
            self.cert_table.insertRow(row)
            self.cert_table.setItem(row, 0, QTableWidgetItem(str(rec["id"])))
            self.cert_table.setItem(row, 1, QTableWidgetItem(rec["certificate_number"]))
            self.cert_table.setItem(row, 2, QTableWidgetItem(rec["product_type"]))
            self.cert_table.setItem(row, 3, QTableWidgetItem(str(rec["total_amount"])))
            rem_item = QTableWidgetItem(str(rec["remaining_amount"]))
            if rec["remaining_amount"] <= 0:
                rem_item.setForeground(QColor("#E11D48"))
            elif is_low_quota(rec["total_amount"], rec["remaining_amount"]):
                rem_item.setForeground(QColor("#D97706"))
            self.cert_table.setItem(row, 4, rem_item)
            self.cert_table.setItem(row, 5, QTableWidgetItem(rec["unit_name"]))

    def _show_consumption(self):
        row = self.cert_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "یک گواهی را از جدول بالا انتخاب کنید")
            return

        try:
            cert_id = int(self.cert_table.item(row, 0).text())
            company_id = self.c_company_combo.currentData()

            rec = db.fetch_one(
                """SELECT cert.*, c.name as company_name, u.name as unit_name
                   FROM certificates cert
                   JOIN companies c ON cert.company_id = c.id
                   JOIN units u ON cert.unit_id = u.id
                   WHERE cert.id = ?""",
                (cert_id,)
            )
            if not rec:
                return

            self._current_cert = dict(rec)
            self._current_unit_name = rec["unit_name"]

            consumptions = db.fetch_all(
                """SELECT ei.amount, ei.is_debt, ei.product_name,
                          ep.exit_date, ep.permit_number
                   FROM exit_items ei
                   JOIN exit_permits ep ON ei.exit_permit_id = ep.id
                   WHERE ei.certificate_id = ?
                   ORDER BY ep.exit_date""",
                (cert_id,)
            )
            self._current_consumptions = [dict(c) for c in consumptions]

            self.cons_table.setRowCount(0)
            total = 0
            for c in self._current_consumptions:
                total += c["amount"]
                r = self.cons_table.rowCount()
                self.cons_table.insertRow(r)
                self.cons_table.setItem(r, 0, QTableWidgetItem(c["exit_date"]))
                self.cons_table.setItem(r, 1, QTableWidgetItem(c["permit_number"]))
                self.cons_table.setItem(r, 2, QTableWidgetItem(c["product_name"]))
                amt = int(c["amount"]) if c["amount"] == int(c["amount"]) else c["amount"]
                self.cons_table.setItem(r, 3, QTableWidgetItem(str(amt)))
                debt_item = QTableWidgetItem("🔴 بدهی" if c["is_debt"] else "عادی")
                if c["is_debt"]:
                    debt_item.setForeground(QColor("#E11D48"))
                self.cons_table.setItem(r, 4, debt_item)

            self.c_lbl_summary.setText(
                f"گواهی «{rec['certificate_number']}» — جمع مصرف ثبت‌شده: "
                f"{self._format(total)} {rec['unit_name']} از کل "
                f"{self._format(rec['total_amount'])} — باقیمانده: "
                f"{self._format(rec['remaining_amount'])} {rec['unit_name']}"
            )
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا: {e}")

    def _export_cert_pdf(self):
        if not self._current_cert:
            QMessageBox.warning(self, "خطا", "ابتدا گواهی را انتخاب و ریز مصرف را نمایش دهید")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "ذخیره ریز مصرف PDF",
            f"ریز_مصرف_{self._current_cert['certificate_number'].replace('/', '-')}.pdf",
            "PDF (*.pdf)"
        )
        if not filepath:
            return

        ok = generate_certificate_report_pdf(
            filepath,
            self._current_cert,
            self._current_consumptions,
            self._current_unit_name
        )
        if ok:
            show_toast(self, f"ریز مصرف PDF ذخیره شد: {os.path.basename(filepath)}", "success", 3200)
        else:
            QMessageBox.critical(self, "خطا", "تولید PDF ناموفق بود")

    def _export_company_statement(self):
        """صورتحساب کامل شرکت انتخابی: گواهی‌ها + مجوزها + بدهی‌ها"""
        company_id = self.c_company_combo.currentData()
        if company_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا شرکت را انتخاب کنید")
            return
        company_name = self.c_company_combo.currentText()

        try:
            certs = db.fetch_all(
                """SELECT cert.*, u.name as unit_name
                   FROM certificates cert
                   JOIN units u ON cert.unit_id = u.id
                   WHERE cert.company_id = ?
                   ORDER BY cert.created_at DESC""",
                (company_id,)
            )
            permits = db.fetch_all(
                """SELECT ep.id, ep.permit_number, ep.exit_date,
                          ep.destination, ep.customs_representative
                   FROM exit_permits ep
                   WHERE ep.company_id = ?
                   ORDER BY ep.exit_date, ep.id""",
                (company_id,)
            )

            records = []
            for p in permits:
                items = db.fetch_all(
                    """SELECT ei.product_name, ei.amount, u.name as unit_name, ei.is_debt, ei.debt_settled
                       FROM exit_items ei
                       JOIN units u ON ei.unit_id = u.id
                       WHERE ei.exit_permit_id = ?""",
                    (p["id"],)
                )
                items_parts, debt_parts = [], []
                for it in items:
                    amt = int(it["amount"]) if it["amount"] == int(it["amount"]) else it["amount"]
                    items_parts.append(f"{it['product_name']} — {amt} {it['unit_name']}")
                    if it["is_debt"] and not it["debt_settled"]:
                        debt_parts.append(f"{it['product_name']}: {amt} {it['unit_name']}")
                records.append({
                    "permit_number": p["permit_number"],
                    "exit_date": p["exit_date"],
                    "destination": p["destination"] or "",
                    "items_text": " | ".join(items_parts),
                    "debt_text": " | ".join(debt_parts),
                })

            debts = db.fetch_all(
                """SELECT ep.permit_number, ep.exit_date, ei.product_name,
                          ei.amount, u.name as unit_name, ei.debt_settled
                   FROM exit_items ei
                   JOIN exit_permits ep ON ei.exit_permit_id = ep.id
                   JOIN units u ON ei.unit_id = u.id
                   WHERE ep.company_id = ? AND ei.is_debt = 1
                   ORDER BY ep.exit_date, ep.id""",
                (company_id,)
            )

            if not certs and not permits:
                QMessageBox.information(
                    self, "داده‌ای نیست",
                    "این شرکت گواهی یا مجوزی ثبت نکرده است."
                )
                return

            filepath, _ = QFileDialog.getSaveFileName(
                self, "ذخیره صورتحساب",
                f"صورتحساب_{company_name.replace(' ', '_')}.pdf",
                "PDF (*.pdf)"
            )
            if not filepath:
                return

            ok = generate_company_statement_pdf(
                filepath, company_name, records,
                [dict(c) for c in certs], [dict(d) for d in debts]
            )
            if ok:
                show_toast(self, f"صورتحساب ذخیره شد: {os.path.basename(filepath)}", "success", 3200)
            else:
                QMessageBox.critical(self, "خطا", "تولید PDF ناموفق بود")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در صورتحساب: {e}")

    def refresh_page(self):
        """رفرش هنگام ورود به صفحه"""
        # شرکت‌های کمبوی گزارش دوره‌ای
        current = self.p_company_combo.currentData()
        self.p_company_combo.blockSignals(True)
        self.p_company_combo.clear()
        self.p_company_combo.addItem("همه شرکت‌ها", None)
        self._load_companies_into(self.p_company_combo, only_cert=False)
        if current is not None:
            idx = self.p_company_combo.findData(current)
            if idx >= 0:
                self.p_company_combo.setCurrentIndex(idx)
        self.p_company_combo.blockSignals(False)

        # شرکت‌های کمبوی ریز مصرف
        current_c = self.c_company_combo.currentData()
        self.c_company_combo.blockSignals(True)
        self.c_company_combo.clear()
        self._load_companies_into(self.c_company_combo, only_cert=True)
        if current_c is not None:
            idx = self.c_company_combo.findData(current_c)
            if idx >= 0:
                self.c_company_combo.setCurrentIndex(idx)
        self.c_company_combo.blockSignals(False)
        self._load_certificates()

    def _format(self, num):
        if num == int(num):
            return f"{int(num):,}"
        return f"{num:,.2f}"

    def _to_persian(self, num):
        return str(num).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))