"""
صفحه جستجو و گزارش مجوزهای خروج - با ویرایش و حذف
"""
import os
import traceback
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QFormLayout, QComboBox,
    QCheckBox, QFileDialog
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap
from database.db_manager import db
from services.quota import restore_permit_quota_tx
from services.printer import print_exit_permit, print_to_pdf
from config import SCANS_DIR
from ui.shamsi_calendar import ShamsiDateEdit, is_valid_shamsi_date
from ui.ui_helpers import set_table_empty_state, set_cell_pill

class SearchWindow(QWidget):
    """صفحه جستجو و گزارش"""

    back_requested = pyqtSignal()
    edit_permit_requested = pyqtSignal(int)
    duplicate_permit_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self._setup_ui()
            self._load_results()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در بارگذاری: {e}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        filter_group = QGroupBox("فیلترهای جستجو")
        filter_layout = QFormLayout(filter_group)
        filter_layout.setSpacing(8)

        self.company_combo = QComboBox()
        self.company_combo.addItem("همه شرکت‌ها", None)
        self._load_companies()
        filter_layout.addRow("شرکت:", self.company_combo)

        self.permit_number_input = QLineEdit()
        self.permit_number_input.setPlaceholderText("مثال: 1405/012 یا 012")
        filter_layout.addRow("شماره ثبت:", self.permit_number_input)

        self.product_input = QLineEdit()
        self.product_input.setPlaceholderText("نام کالا...")
        filter_layout.addRow("نوع کالا:", self.product_input)

        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("مقصد...")
        filter_layout.addRow("مقصد:", self.destination_input)

        self.customs_input = QLineEdit()
        self.customs_input.setPlaceholderText("نام نماینده گمرک...")
        filter_layout.addRow("نماینده گمرک:", self.customs_input)

        self.txt_date_from = ShamsiDateEdit()
        self.txt_date_to = ShamsiDateEdit()

        date_layout = QHBoxLayout()
        self.chk_date = QCheckBox("فیلتر تاریخ")
        self.chk_date.setChecked(False)
        date_layout.addWidget(self.chk_date)
        date_layout.addWidget(QLabel("از:"))
        date_layout.addWidget(self.txt_date_from)
        date_layout.addWidget(QLabel("تا:"))
        date_layout.addWidget(self.txt_date_to)
        filter_layout.addRow("بازه تاریخ:", date_layout)

        self.chk_debt_only = QCheckBox("فقط خروج‌های بدهی")
        filter_layout.addRow("", self.chk_debt_only)

        layout.addWidget(filter_group)

        btn_layout = QHBoxLayout()

        btn_search = QPushButton("🔍 جستجو")
        btn_search.setObjectName("btnPrimary")
        btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_search.clicked.connect(self._load_results)

        btn_reset = QPushButton("🔄 بازنشانی")
        btn_reset.setObjectName("btnNeutral")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.clicked.connect(self._reset_filters)

        btn_excel = QPushButton("📊 خروجی Excel")
        btn_excel.setObjectName("btnSuccess")
        btn_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_excel.clicked.connect(self._export_excel)

        btn_view_scan = QPushButton("📄 مشاهده نامه")
        btn_view_scan.setObjectName("btnWarning")
        btn_view_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_view_scan.clicked.connect(self._view_scan)

        btn_edit = QPushButton("✏️ ویرایش مجوز")
        btn_edit.setObjectName("btnPrimary")
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.clicked.connect(self._edit_permit)

        btn_delete = QPushButton("🗑️ حذف مجوز")
        btn_delete.setObjectName("btnDanger")
        btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_delete.clicked.connect(self._delete_permit)

        btn_reprint = QPushButton("🖨️ چاپ روبرگه")
        btn_reprint.setObjectName("btnSuccess")
        btn_reprint.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reprint.clicked.connect(self._reprint_permit)

        btn_duplicate = QPushButton("📋 ثبت مشابه")
        btn_duplicate.setObjectName("btnPrimary")
        btn_duplicate.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_duplicate.clicked.connect(self._duplicate_permit)

        btn_back = QPushButton("بازگشت به داشبورد")
        btn_back.setObjectName("btnDefault")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.back_requested.emit)

        btn_layout.addWidget(btn_search)
        btn_layout.addWidget(btn_reset)
        btn_layout.addWidget(btn_excel)
        btn_layout.addWidget(btn_view_scan)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_delete)
        btn_layout.addWidget(btn_reprint)
        btn_layout.addWidget(btn_duplicate)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_back)
        layout.addLayout(btn_layout)

        results_group = QGroupBox("نتایج")
        results_layout = QVBoxLayout(results_group)

        self.lbl_count = QLabel("۰ نتیجه")
        self.lbl_count.setStyleSheet("font-size: 13px; color: #555;")
        results_layout.addWidget(self.lbl_count)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "شماره ثبت", "تاریخ", "شرکت", "مقصد",
            "نماینده گمرک", "کالاها (نام — مقدار واحد)", "بدهی", "شناسه"
        ])
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(6, 110)
        self.table.setColumnHidden(7, True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._edit_permit)  # دابل‌کلیک = ویرایش
        results_layout.addWidget(self.table)

        layout.addWidget(results_group)

        stats_group = QGroupBox("📊 آمار خروج‌ها")
        stats_layout = QHBoxLayout(stats_group)

        self.lbl_total = QLabel("کل: ۰")
        self.lbl_total.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        self.lbl_debts = QLabel("بدهی: ۰")
        self.lbl_debts.setStyleSheet("font-size: 14px; font-weight: bold; color: #e74c3c;")

        stats_layout.addWidget(self.lbl_total)
        stats_layout.addStretch()
        stats_layout.addWidget(self.lbl_debts)

        layout.addWidget(stats_group)

    def _load_companies(self):
        records = db.fetch_all("SELECT id, name FROM companies ORDER BY name")
        for rec in records:
            self.company_combo.addItem(rec["name"], rec["id"])

    def refresh_page(self):
        """رفرش لیست شرکت‌ها هنگام هر بار ورود به صفحه"""
        current_id = self.company_combo.currentData()
        self.company_combo.blockSignals(True)
        self.company_combo.clear()
        self.company_combo.addItem("همه شرکت‌ها", None)
        self._load_companies()
        if current_id is not None:
            idx = self.company_combo.findData(current_id)
            if idx >= 0:
                self.company_combo.setCurrentIndex(idx)
        self.company_combo.blockSignals(False)

    def _get_items_map(self, permit_ids):
        """
        کوئری دسته‌ای کالاهای همه‌ی مجوزها (رفع N+1).
        خروجی: {permit_id: [(items_text, debt_text), ...]} — یک جفت برای هر مجوز
        """
        result = {}
        if not permit_ids:
            return result
        placeholders = ",".join("?" for _ in permit_ids)
        rows = db.fetch_all(
            f"""SELECT ei.exit_permit_id, ei.product_name, ei.amount,
                      u.name as unit_name, ei.is_debt, ei.debt_settled
               FROM exit_items ei
               JOIN units u ON ei.unit_id = u.id
               WHERE ei.exit_permit_id IN ({placeholders})
               ORDER BY ei.exit_permit_id, ei.id""",
            tuple(permit_ids)
        )
        for r in rows:
            amount_str = self._format_number(r["amount"])
            text = f"{r['product_name']} — {amount_str} {r['unit_name']}"
            debt_text = None
            if r["is_debt"] and not r["debt_settled"]:
                debt_text = f"{r['product_name']}: {amount_str} {r['unit_name']}"
            result.setdefault(r["exit_permit_id"], []).append((text, debt_text))
        return result

    def _get_items_text(self, permit_id):
        """نسخه تک‌مجوزی (برای سازگاری) — از مپ دسته‌ای استفاده می‌کند"""
        mapping = self._get_items_map([permit_id])
        pairs = mapping.get(permit_id, [])
        parts = [p[0] for p in pairs]
        debt_parts = [p[1] for p in pairs if p[1]]
        return " | ".join(parts), " | ".join(debt_parts)

    def _format_number(self, num):
        """جداکننده هزارگان با ارقام فارسی: ۳٬۵۰۰٬۰۰۰"""
        from ui.ui_helpers import format_thousands
        return format_thousands(num)

    def _build_query(self):
        conditions = []
        params = []

        company_id = self.company_combo.currentData()
        if company_id is not None:
            conditions.append("ep.company_id = ?")
            params.append(company_id)

        permit_no = self.permit_number_input.text().strip()
        if permit_no:
            # جستجوی انعطاف‌پذیر: «1405/012» یا فقط «012»
            conditions.append("ep.permit_number LIKE ?")
            params.append(f"%{permit_no}%")

        product = self.product_input.text().strip()
        if product:
            conditions.append("ep.id IN (SELECT exit_permit_id FROM exit_items WHERE product_name LIKE ?)")
            params.append(f"%{product}%")

        destination = self.destination_input.text().strip()
        if destination:
            conditions.append("ep.destination LIKE ?")
            params.append(f"%{destination}%")

        customs = self.customs_input.text().strip()
        if customs:
            conditions.append("ep.customs_representative LIKE ?")
            params.append(f"%{customs}%")

        if self.chk_date.isChecked():
            date_from = self.txt_date_from.text().strip()
            date_to = self.txt_date_to.text().strip()
            if date_from:
                conditions.append("ep.exit_date >= ?")
                params.append(date_from)
            if date_to:
                conditions.append("ep.exit_date <= ?")
                params.append(date_to)

        if self.chk_debt_only.isChecked():
            # فقط بدهی‌های تسویه‌نشده — هم‌خوان با آمار داشبورد
            conditions.append(
                "ep.id IN (SELECT exit_permit_id FROM exit_items "
                "WHERE is_debt = 1 AND debt_settled = 0)"
            )

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        return where_clause, params

    def _load_results(self):
        try:
            # اعتبارسنجی واقعی تاریخ‌های فیلتر (در صورت فعال بودن)
            if self.chk_date.isChecked():
                date_from = self.txt_date_from.text().strip()
                date_to = self.txt_date_to.text().strip()
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

            where_clause, params = self._build_query()

            query = f"""
                SELECT ep.id, ep.permit_number, ep.exit_date, c.name as company_name,
                       ep.destination, ep.customs_representative
                FROM exit_permits ep
                JOIN companies c ON ep.company_id = c.id
                {where_clause}
                ORDER BY ep.exit_date DESC, ep.created_at DESC
            """

            records = db.fetch_all(query, tuple(params))

            # کوئری دسته‌ای کالاها (رفع N+1)
            items_map = self._get_items_map([r["id"] for r in records])

            self.table.setRowCount(0)
            debt_count = 0
            for rec in records:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(rec["permit_number"] or ""))
                self.table.setItem(row, 1, QTableWidgetItem(rec["exit_date"] or ""))
                self.table.setItem(row, 2, QTableWidgetItem(rec["company_name"] or ""))
                self.table.setItem(row, 3, QTableWidgetItem(rec["destination"] or ""))
                self.table.setItem(row, 4, QTableWidgetItem(rec["customs_representative"] or ""))

                pairs = items_map.get(rec["id"], [])
                items_text = " | ".join(p[0] for p in pairs)
                debt_text = " | ".join(p[1] for p in pairs if p[1])
                self.table.setItem(row, 5, QTableWidgetItem(items_text))

                # نشان رنگی وضعیت بدهی — یک نگاه کافی
                if debt_text:
                    set_cell_pill(self.table, row, 6, f"بدهی: {debt_text}", "red")
                    debt_count += 1
                else:
                    set_cell_pill(self.table, row, 6, "تسویه", "green")
                self.table.setItem(row, 7, QTableWidgetItem(str(rec["id"])))

            self.table.resizeRowsToContents()

            # حالت خالی: پیام دوستانه وقتی نتیجه‌ای نیست
            set_table_empty_state(
                self.table, not records,
                title="موردی یافت نشد",
                subtitle="فیلترها را تغییر دهید یا دکمه «پاک‌کردن فیلترها» را بزنید"
            )

            count = len(records)
            self.lbl_count.setText(f"{self._to_persian(count)} نتیجه")
            self.lbl_total.setText(f"کل: {self._to_persian(count)}")
            self.lbl_debts.setText(f"بدهی: {self._to_persian(debt_count)}")

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در جستجو: {e}")

    def _reset_filters(self):
        self.company_combo.setCurrentIndex(0)
        self.permit_number_input.clear()
        self.product_input.clear()
        self.destination_input.clear()
        self.customs_input.clear()
        self.txt_date_from.clear()
        self.txt_date_to.clear()
        self.chk_date.setChecked(False)
        self.chk_debt_only.setChecked(False)
        self._load_results()

    def _edit_permit(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "برای ویرایش، یک مجوز را انتخاب کنید")
            return
        permit_id = int(self.table.item(row, 7).text())
        self.edit_permit_requested.emit(permit_id)

    def _delete_permit(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "برای حذف، یک مجوز را انتخاب کنید")
            return

        permit_id = int(self.table.item(row, 7).text())
        permit_number = self.table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "تأیید حذف",
            f"آیا از حذف مجوز «{permit_number}» مطمئن هستید؟\n\n"
            "⚠️ سهمیه‌ی کسرشده از گواهی به‌صورت خودکار بازگردانی می‌شود\n"
            "و اسکن‌های این مجوز هم حذف خواهند شد.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # ۱. مسیر فایل‌های اسکن برای حذف بعدی از دیسک
            scans = db.fetch_all(
                "SELECT file_path FROM scanned_documents WHERE exit_permit_id=?",
                (permit_id,)
            )

            # ۲. بازگردانی سهمیه + حذف رکوردها در یک تراکنش اتمیک
            with db.transaction() as tx:
                restore_permit_quota_tx(tx, permit_id)
                tx.execute("DELETE FROM scanned_documents WHERE exit_permit_id=?", (permit_id,))
                tx.execute("DELETE FROM exit_items WHERE exit_permit_id=?", (permit_id,))
                tx.execute("DELETE FROM exit_permits WHERE id=?", (permit_id,))

            # ۳. حذف فایل‌های اسکن از دیسک (بعد از موفقیت تراکنش)
            for s in scans:
                try:
                    if os.path.exists(s["file_path"]):
                        os.remove(s["file_path"])
                except Exception:
                    pass

            from ui.ui_helpers import show_toast
            show_toast(self, f"مجوز «{permit_number}» حذف شد — سهمیه‌ها بازگشت ✓", "success", 3000)
            self._load_results()

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در حذف: {e}")

    def _export_excel(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "خطا", "هیچ داده‌ای برای خروجی وجود ندارد")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل Excel",
            f"گزارش_خروج_{QDate.currentDate().toString('yyyyMMdd')}.xlsx",
            "Excel (*.xlsx)"
        )
        if not filepath:
            return

        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "گزارش خروج"

            headers = [
                "شماره ثبت", "تاریخ", "شرکت", "مقصد", "نماینده گمرک",
                "نام کالا", "مقدار", "واحد", "وضعیت بدهی"
            ]

            thin = Side(style="thin", color="999999")
            border = Border(left=thin, right=thin, top=thin, bottom=thin)

            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True, color="FFFFFF", size=12)
                cell.fill = PatternFill(start_color="1A1A2E", end_color="1A1A2E", fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = border

            row_num = 2
            for row in range(self.table.rowCount()):
                permit_id = int(self.table.item(row, 7).text())
                permit_number = self.table.item(row, 0).text()
                exit_date = self.table.item(row, 1).text()
                company = self.table.item(row, 2).text()
                destination = self.table.item(row, 3).text()
                customs = self.table.item(row, 4).text()

                items = db.fetch_all(
                    """SELECT ei.product_name, ei.amount, u.name as unit_name, ei.is_debt
                       FROM exit_items ei
                       JOIN units u ON ei.unit_id = u.id
                       WHERE ei.exit_permit_id = ?""",
                    (permit_id,)
                )

                for it in items:
                    values = [
                        permit_number, exit_date, company, destination, customs,
                        it["product_name"], it["amount"], it["unit_name"],
                        "بدهی" if it["is_debt"] else "عادی"
                    ]
                    for col, value in enumerate(values, 1):
                        cell = ws.cell(row=row_num, column=col, value=value)
                        cell.alignment = Alignment(horizontal="right", vertical="center")
                        cell.border = border
                        if it["is_debt"]:
                            cell.fill = PatternFill(
                                start_color="FADBD8", end_color="FADBD8", fill_type="solid"
                            )
                    row_num += 1

            widths = [12, 12, 25, 15, 18, 30, 12, 10, 12]
            for col, width in enumerate(widths, 1):
                ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = width

            ws.sheet_view.rightToLeft = True

            wb.save(filepath)
            from ui.ui_helpers import show_toast
            import os as _os
            show_toast(self, f"اکسل ذخیره شد: {_os.path.basename(filepath)}", "success", 3200)

        except ImportError:
            QMessageBox.warning(
                self, "خطا",
                "کتابخانه openpyxl نصب نیست.\npip install openpyxl"
            )
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در تولید Excel: {e}")

    def _reprint_permit(self):
        """چاپ مجدد روبرگه «خروج بلامانع» مجوز انتخابی"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "برای چاپ، یک مجوز را انتخاب کنید")
            return

        permit_id = int(self.table.item(row, 7).text())
        try:
            permit = db.fetch_one("SELECT * FROM exit_permits WHERE id=?", (permit_id,))
            if not permit:
                QMessageBox.warning(self, "خطا", "مجوز یافت نشد")
                return
            company = db.fetch_one(
                "SELECT name FROM companies WHERE id=?", (permit["company_id"],)
            )
            items = db.fetch_all(
                """SELECT ei.product_name, ei.amount, u.name as unit_name
                   FROM exit_items ei
                   JOIN units u ON ei.unit_id = u.id
                   WHERE ei.exit_permit_id=? ORDER BY ei.id""",
                (permit_id,)
            )
            if not items:
                QMessageBox.warning(self, "خطا", "این مجوز کالایی ندارد")
                return

            print_data = {
                "permit_number": permit["permit_number"],
                "exit_date": permit["exit_date"],
                "customs_representative": permit["customs_representative"] or "—",
                "company_name": company["name"] if company else "—",
                "destination": permit["destination"] or "",
                "items": [
                    {"product_name": it["product_name"],
                     "amount": it["amount"],
                     "unit_name": it["unit_name"]}
                    for it in items
                ],
            }
            printed = print_exit_permit(print_data, show_dialog=True)
            if not printed:
                # چاپ مستقیم انجام نشد → پیشنهاد PDF
                pdf_path, _ = QFileDialog.getSaveFileName(
                    self, "ذخیره روبرگه PDF",
                    f"{permit['permit_number'].replace('/', '-')}.pdf",
                    "PDF (*.pdf)"
                )
                if pdf_path and print_to_pdf(print_data, pdf_path):
                    QMessageBox.information(self, "PDF", "روبرگه به‌صورت PDF ذخیره شد ✓")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در چاپ: {e}")

    def _duplicate_permit(self):
        """«ثبت مشابه»: بازکردن فرم ثبت جدید با اطلاعات مجوز انتخابی به‌عنوان الگو"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "برای ثبت مشابه، یک مجوز را انتخاب کنید")
            return
        permit_id = int(self.table.item(row, 7).text())
        # سیگنال جداگانه — MainWindow فرم را در حالت ثبت جدید با الگو پر می‌کند
        self.duplicate_permit_requested.emit(permit_id)

    def _view_scan(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "خطا", "یک مجوز را انتخاب کنید")
            return

        permit_id = int(self.table.item(row, 7).text())
        scans = db.fetch_all(
            "SELECT file_path, page_number FROM scanned_documents WHERE exit_permit_id=? ORDER BY page_number",
            (permit_id,)
        )

        if not scans:
            QMessageBox.information(self, "اسکن", "هیچ اسکنی برای این مجوز ثبت نشده است")
            return

        self._show_image_viewer(scans)

    def _show_image_viewer(self, scans):
        viewer = QDialog(self)
        viewer.setWindowTitle("مشاهده نامه")
        viewer.resize(700, 900)
        layout = QVBoxLayout(viewer)

        if len(scans) > 1:
            page_combo = QComboBox()
            for scan in scans:
                page_combo.addItem(f"صفحه {scan['page_number']}", scan["file_path"])
            page_combo.currentIndexChanged.connect(
                lambda idx: self._update_image(lbl_image, page_combo.currentData())
            )
            layout.addWidget(page_combo)

        lbl_image = QLabel()
        lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_image)

        btn_close = QPushButton("بستن")
        btn_close.clicked.connect(viewer.accept)
        layout.addWidget(btn_close)

        self._update_image(lbl_image, scans[0]["file_path"])
        viewer.exec()

    def _update_image(self, label, filepath):
        if filepath and os.path.exists(filepath):
            pixmap = QPixmap(filepath)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    650, 750,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                label.setPixmap(scaled)
            else:
                label.setText("خطا در بارگذاری تصویر")
        else:
            label.setText("فایل یافت نشد")

    def _to_persian(self, num):
        persian_digits = "۰۱۲۳۴۵۶۷۸۹"
        return str(num).translate(str.maketrans("0123456789", persian_digits))