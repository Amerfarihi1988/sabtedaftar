"""
صفحه ثبت/ویرایش مجوز خروج کالا
اسکن + ثبت کالاها + کنترل سهمیه + چاپ
"""
from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFormLayout, QGroupBox, QDoubleSpinBox, QTextEdit,
    QListWidget,QCompleter, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence
from database.db_manager import db
from services.numbering import generate_permit_number_in_tx, get_next_number_preview
from services.scanner import scan_document, has_scanner
from ui.shamsi_calendar import ShamsiDateEdit, is_valid_shamsi_date
from services.quota import (
    get_certificate_info, process_items, preview_deduction,
    apply_quota_plan, restore_permit_quota_tx,
)
from services.quota import get_active_certificate
from services.printer import print_exit_permit, print_to_pdf
from ui.persian_amount import PersianAmountSpinBox
from ui.ui_helpers import show_toast
from config import SCANS_DIR
import jdatetime
import os


class ExitPermitWindow(QWidget):
    """صفحه ثبت و ویرایش مجوز خروج"""

    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.edit_mode = False
        self.editing_permit_id = None
        self.original_scan_count = 0
        self.scanned_files = []
        self._setup_ui()
        self._prefill()

        # میان‌بر Ctrl+S = ذخیره
        QShortcut(QKeySequence.StandardKey.Save, self).activated.connect(self._save_and_print)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ─── ناحیه اسکرول: با پنجره کوتاه، فرم اسکرول می‌شود نه آنکه دکمه‌ها بیرون بزنند ───
        # توجه: استایل با سلکتور کامل — استایل بدون سلکتور به فرزندان منتقل می‌شود و
        # گرادیان دکمه‌ها و سفیدی گروه‌ها را خنثی می‌کند (متن سفید روی زمینه روشن)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # سلکتور نوع: فقط خودِ اسکرول‌اریا؛ به فرزندان نشت نمی‌کند
        # (استایل viewport بدون سلکتور بود که گرادیان دکمه‌ها را می‌کشت)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setObjectName("scrollContent")  # شفافیت با سلکتور ID در styles.css
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 10, 16, 6)
        layout.setSpacing(10)

        # ─── نوار حالت ویرایش ───
        self.edit_header = QLabel()
        self.edit_header.setStyleSheet(
            "padding: 10px; border-radius: 10px; font-size: 14px; font-weight: bold; "
            "background-color: #FEF3C7; color: #92400E;"
        )
        self.edit_header.hide()
        layout.addWidget(self.edit_header)

        # ─── بخش اطلاعات بالا ───
        top_group = QGroupBox("اطلاعات مجوز")
        top_layout = QFormLayout(top_group)
        top_layout.setSpacing(8)

        self.permit_number_input = QLineEdit()
        self.permit_number_input.setReadOnly(True)
        self.permit_number_input.setStyleSheet("font-weight: bold;")
        top_layout.addRow("شماره ثبت:", self.permit_number_input)

        self.date_input = ShamsiDateEdit()
        top_layout.addRow("تاریخ خروج:", self.date_input)

        self.company_combo = QComboBox()
        self.company_combo.setPlaceholderText("انتخاب شرکت...")
        self.company_combo.setMinimumHeight(35)
        self.company_combo.setEditable(True)
        self.company_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.company_combo.lineEdit().setPlaceholderText("جستجو یا انتخاب شرکت...")
        self.company_combo.currentIndexChanged.connect(self._on_company_changed)
        top_layout.addRow("شرکت:", self.company_combo)

        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("مقصد کالا")
        top_layout.addRow("مقصد:", self.destination_input)

        self.customs_rep_input = QLineEdit()
        self.customs_rep_input.setPlaceholderText("نام نماینده گمرک")
        top_layout.addRow("نماینده گمرک:", self.customs_rep_input)

        layout.addWidget(top_group)

        # ─── اطلاعات گواهی ───
        self.cert_info_label = QLabel()
        self.cert_info_label.setStyleSheet(
            "padding: 8px; border-radius: 10px; font-size: 13px;"
        )
        self.cert_info_label.setWordWrap(True)
        self.cert_info_label.hide()
        layout.addWidget(self.cert_info_label)

        # ─── بخش کالاها ───
        items_group = QGroupBox("کالاهای خروجی")
        items_layout = QVBoxLayout(items_group)

        self.items_table = QTableWidget(0, 4)
        self.items_table.setHorizontalHeaderLabels(["نام کالا", "مقدار", "واحد", ""])
        self.items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.items_table.setColumnWidth(1, 180)
        self.items_table.setColumnWidth(2, 180)
        self.items_table.setColumnWidth(3, 55)
        self.items_table.setMinimumHeight(180)
        self.items_table.verticalHeader().setVisible(False)
        # ارتفاع ردیف‌ها متناسب با فیلدهای فرم (۴۰px) — با استایل سراسری (پدینگ+بوردر)
        # اگر ردیف ۱۷px بماند، فضای متن منفی می‌شود و تایپ کاربر دیده نمی‌شود
        self.items_table.verticalHeader().setDefaultSectionSize(40)
        self.items_table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        items_layout.addWidget(self.items_table)

        add_item_btn = QPushButton("➕ افزودن کالا")
        add_item_btn.setObjectName("btnPrimary")
        add_item_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_item_btn.clicked.connect(self._add_item_row)
        items_layout.addWidget(add_item_btn)

        # کشش گروه کالاها در فضای اضافی — بقیه بخش‌ها سایز طبیعی می‌مانند
        layout.addWidget(items_group, 1)

        # ─── بخش اسکن ───
        scan_group = QGroupBox("اسکن نامه")
        scan_layout = QHBoxLayout(scan_group)

        self.scan_list = QListWidget()
        self.scan_list.setMaximumHeight(100)
        scan_layout.addWidget(self.scan_list, stretch=1)

        scan_btn_layout = QVBoxLayout()
        self.btn_scan = QPushButton("🖨️ اسکن نامه")
        self.btn_scan.setObjectName("btnPrimary")
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.clicked.connect(self._do_scan)

        self.btn_add_image = QPushButton("📎 افزودن عکس")
        self.btn_add_image.setObjectName("btnNeutral")
        self.btn_add_image.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_image.clicked.connect(self._add_image_file)

        scan_btn_layout.addWidget(self.btn_scan)
        scan_btn_layout.addWidget(self.btn_add_image)
        scan_layout.addLayout(scan_btn_layout)

        layout.addWidget(scan_group)

        # ─── یادداشت ───
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("یادداشت (اختیاری)...")
        self.notes_input.setMaximumHeight(60)
        layout.addWidget(self.notes_input)

        # ─── دکمه‌های پایین — نوار ثابت خارج از اسکرول: همیشه دیده می‌شوند ───
        footer = QFrame()
        footer.setObjectName("formFooter")
        btn_layout = QHBoxLayout(footer)
        btn_layout.setContentsMargins(16, 6, 16, 10)
        btn_layout.addStretch()

        btn_cancel = QPushButton("انصراف")
        btn_cancel.setObjectName("btnDefault")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.back_requested.emit)

        self.btn_save_print = QPushButton("💾 ذخیره و چاپ")
        self.btn_save_print.setObjectName("btnSuccess")
        self.btn_save_print.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_print.clicked.connect(self._save_and_print)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_save_print)
        outer.addWidget(footer)

    def _prefill(self):
        self.permit_number_input.setText(get_next_number_preview())
        today = jdatetime.date.today().strftime("%Y/%m/%d")
        self.date_input.setText(today)
        self._load_companies()
        self._add_item_row()

    def refresh_page(self):
        """رفرش صفحه هنگام هر بار ورود به حالت ثبت جدید"""
        self._reset_form()
        self._load_companies()

    def _load_companies(self):
        current_id = self.company_combo.currentData()
        records = db.fetch_all("SELECT id, name FROM companies ORDER BY name")
        self.company_combo.blockSignals(True)
        self.company_combo.clear()
        self.company_combo.addItem("— انتخاب کنید —", None)
        for rec in records:
            self.company_combo.addItem(rec["name"], rec["id"])
        if current_id is not None:
            idx = self.company_combo.findData(current_id)
            if idx >= 0:
                self.company_combo.setCurrentIndex(idx)
        self.company_combo.blockSignals(False)

        # جستجوی زنده با تایپ
        names = [rec["name"] for rec in records]
        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.company_combo.setCompleter(completer)

        self._on_company_changed()

    def _on_company_changed(self):
        company_id = self.company_combo.currentData()
        if company_id is None:
            self.cert_info_label.hide()
            return

        info = get_certificate_info(company_id)
        if not info["needs_certificate"]:
            self.cert_info_label.setText("✅ این شرکت نیازی به گواهی تولید ندارد.")
            self.cert_info_label.setStyleSheet(
                "padding: 8px; border-radius: 10px; font-size: 13px; "
                "background-color: #D1FAE5; color: #065F46;"
            )
            self.cert_info_label.show()
        elif not info["has_active"]:
            if info.get("all_expired"):
                self.cert_info_label.setText(
                    f"⛔ شرکت «{info.get('company_name', '')}» گواهی‌دار است ولی "
                    f"گواهی فعالش منقض شده (انقضا: {info.get('expiry_date')}).\n"
                    f"گواهی جدید ثبت کنید یا خروج به‌عنوان بدهی ثبت می‌شود."
                )
            else:
                self.cert_info_label.setText(
                    f"⚠️ شرکت «{info.get('company_name', '')}» گواهی‌دار است "
                    f"ولی گواهی فعالی ندارد. خروج به‌عنوان بدهی ثبت می‌شود."
                )
            self.cert_info_label.setStyleSheet(
                "padding: 8px; border-radius: 10px; font-size: 13px; "
                "background-color: #FEF3C7; color: #92400E;"
            )
            self.cert_info_label.show()
        else:
            remaining = info["remaining_amount"]
            total = info["total_amount"]
            pct = (remaining / total * 100) if total > 0 else 0

            expiry_part = ""
            if info.get("expiry_date") and info.get("days_to_expiry") is not None:
                d = info["days_to_expiry"]
                if d < 0:
                    expiry_part = f" — ⛔ منقض‌شده ({abs(d)} روز پیش)"
                else:
                    expiry_part = f" — انقضا: {info['expiry_date']} ({d} روز مانده)"

            if info["is_warning"]:
                self.cert_info_label.setText(
                    f"🟡 گواهی: {info['product_type']} — "
                    f"باقیمانده: {remaining} {info['unit_name']} "
                    f"از {total} ({pct:.1f}%) — رو به اتمام!{expiry_part}"
                )
                self.cert_info_label.setStyleSheet(
                    "padding: 8px; border-radius: 10px; font-size: 13px; "
                    "background-color: #FEF3C7; color: #92400E;"
                )
            else:
                self.cert_info_label.setText(
                    f"✅ گواهی: {info['product_type']} — "
                    f"باقیمانده: {remaining} {info['unit_name']} از {total}{expiry_part}"
                )
                self.cert_info_label.setStyleSheet(
                    "padding: 8px; border-radius: 10px; font-size: 13px; "
                    "background-color: #D1FAE5; color: #065F46;"
                )
            self.cert_info_label.show()

    def _add_item_row(self):
        row = self.items_table.rowCount()
        self.items_table.insertRow(row)

        name_input = QLineEdit()
        name_input.setPlaceholderText("نام کالا")
        # اتوکامپلیت از تاریخچه‌ی کالاهای ثبت‌شده — صرفه‌جویی در تایپ روزانه
        completer = QCompleter(self._get_product_names(), self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        name_input.setCompleter(completer)
        self.items_table.setCellWidget(row, 0, name_input)

        # حداقل ارتفاع فیلدها تا داخل سلول ۴۰ پیکسلی کامل دیده و تایپ شوند
        name_input.setMinimumHeight(36)

        amount_input = PersianAmountSpinBox()
        amount_input.setRange(0, 9999999999)
        amount_input.setDecimals(2)
        amount_input.setMinimumHeight(36)
        amount_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.items_table.setCellWidget(row, 1, amount_input)

        unit_combo = QComboBox()
        unit_combo.setMinimumHeight(36)
        units = db.fetch_all("SELECT id, name FROM units ORDER BY name")
        for u in units:
            unit_combo.addItem(u["name"], u["id"])
        self.items_table.setCellWidget(row, 2, unit_combo)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(35, 30)
        del_btn.setStyleSheet("color: #EF4444; font-size: 14px; border: none; font-weight: bold;")
        # خودِ دکمه پاس داده می‌شود؛ ردیف لحظه‌ی کلیک پیدا می‌شود (بدون ایندکس stale)
        del_btn.clicked.connect(lambda checked=False, b=del_btn: self._remove_item_row(b))
        self.items_table.setCellWidget(row, 3, del_btn)

    def _get_product_names(self):
        """لیست نام‌های یکتای کالاهای ثبت‌شده‌ی قبلی برای اتوکامپلیت"""
        try:
            rows = db.fetch_all(
                "SELECT DISTINCT product_name FROM exit_items ORDER BY product_name"
            )
            return [r["product_name"] for r in rows if r["product_name"]]
        except Exception:
            return []

    def _remove_item_row(self, del_btn):
        """حذف ردیف بر اساس موقعیت لحظه‌ای دکمه — نه ایندکس هنگام ساخت"""
        row = None
        for r in range(self.items_table.rowCount()):
            if self.items_table.cellWidget(r, 3) is del_btn:
                row = r
                break
        if row is None:
            return  # دکمه مربوط به ردیفی است که قبلاً حذف شده

        if self.items_table.rowCount() > 1:
            self.items_table.removeRow(row)
        else:
            QMessageBox.information(self, "توجه", "حداقل یک ردیف کالا باید وجود داشته باشد")

    def load_for_duplicate(self, permit_id):
        """
        «ثبت مشابه»: بارگذاری اطلاعات یک مجوز قبلی به‌عنوان الگوی ثبت جدید.
        شماره ثبت و تاریخ بازنشانی می‌شوند و اسکن‌ها کپی نمی‌شوند —
        ذخیره‌ی نهایی یک مجوز کاملاً جدید می‌سازد.
        """
        rec = db.fetch_one("SELECT * FROM exit_permits WHERE id=?", (permit_id,))
        if not rec:
            QMessageBox.warning(self, "خطا", "مجوز یافت نشد")
            return

        # حالت ثبت جدید (نه ویرایش)
        self.edit_mode = False
        self.editing_permit_id = None
        self.original_scan_count = 0
        self.edit_header.hide()
        self.btn_save_print.setText("💾 ذخیره و چاپ")

        self.permit_number_input.setText(get_next_number_preview())
        self.date_input.setText(jdatetime.date.today().strftime("%Y/%m/%d"))

        self.company_combo.blockSignals(True)
        idx = self.company_combo.findData(rec["company_id"])
        if idx >= 0:
            self.company_combo.setCurrentIndex(idx)
        self.company_combo.blockSignals(False)
        self._on_company_changed()

        self.destination_input.setText(rec["destination"] or "")
        self.customs_rep_input.setText(rec["customs_representative"] or "")
        self.notes_input.setPlainText(rec["notes"] or "")

        # کالاهای مجوز قبلی به‌عنوان الگو
        while self.items_table.rowCount() > 0:
            self.items_table.removeRow(0)
        items = db.fetch_all(
            """SELECT product_name, amount, unit_id FROM exit_items
               WHERE exit_permit_id=?""",
            (permit_id,)
        )
        for it in items:
            row = self.items_table.rowCount()
            self._add_item_row()
            name_w = self.items_table.cellWidget(row, 0)
            amount_w = self.items_table.cellWidget(row, 1)
            unit_w = self.items_table.cellWidget(row, 2)
            name_w.setText(it["product_name"])
            amount_w.setValue(it["amount"])
            u_idx = unit_w.findData(it["unit_id"])
            if u_idx >= 0:
                unit_w.setCurrentIndex(u_idx)

        # اسکن‌ها متعلق به مجوز قبلی‌اند — کپی نمی‌شوند
        self.scanned_files = []
        self.scan_list.clear()

    def load_for_edit(self, permit_id):
        """بارگذاری مجوز برای ویرایش"""
        rec = db.fetch_one("SELECT * FROM exit_permits WHERE id=?", (permit_id,))
        if not rec:
            QMessageBox.warning(self, "خطا", "مجوز یافت نشد")
            return

        self.edit_mode = True
        self.editing_permit_id = permit_id

        self.edit_header.setText(
            f"⚠️ حالت ویرایش — مجوز شماره «{rec['permit_number']}». "
            f"پس از ذخیره، سهمیه‌ی گواهی دوباره محاسبه می‌شود."
        )
        self.edit_header.show()
        self.btn_save_print.setText("💾 ذخیره تغییرات")

        self.permit_number_input.setText(rec["permit_number"])
        self.date_input.setText(rec["exit_date"])

        self.company_combo.blockSignals(True)
        idx = self.company_combo.findData(rec["company_id"])
        if idx >= 0:
            self.company_combo.setCurrentIndex(idx)
        self.company_combo.blockSignals(False)
        self._on_company_changed()

        self.destination_input.setText(rec["destination"] or "")
        self.customs_rep_input.setText(rec["customs_representative"] or "")
        self.notes_input.setPlainText(rec["notes"] or "")

        # کالاها
        while self.items_table.rowCount() > 0:
            self.items_table.removeRow(0)
        items = db.fetch_all(
            """SELECT product_name, amount, unit_id FROM exit_items
               WHERE exit_permit_id=?""",
            (permit_id,)
        )
        for it in items:
            row = self.items_table.rowCount()
            self._add_item_row()
            name_w = self.items_table.cellWidget(row, 0)
            amount_w = self.items_table.cellWidget(row, 1)
            unit_w = self.items_table.cellWidget(row, 2)
            name_w.setText(it["product_name"])
            amount_w.setValue(it["amount"])
            u_idx = unit_w.findData(it["unit_id"])
            if u_idx >= 0:
                unit_w.setCurrentIndex(u_idx)

        # اسکن‌های موجود
        scans = db.fetch_all(
            "SELECT file_path, page_number FROM scanned_documents WHERE exit_permit_id=? ORDER BY page_number",
            (permit_id,)
        )
        self.scanned_files = [s["file_path"] for s in scans]
        self.original_scan_count = len(self.scanned_files)
        self.scan_list.clear()
        for s in scans:
            self.scan_list.addItem(f"📄 صفحه {s['page_number']}: {os.path.basename(s['file_path'])}")

    def _do_scan(self):
        company_id = self.company_combo.currentData()
        if company_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا شرکت را انتخاب کنید")
            return

        if not has_scanner():
            QMessageBox.warning(
                self, "اسکنر یافت نشد",
                "هیچ اسکنری روی سیستم یافت نشد.\n"
                "می‌توانید از دکمه «افزودن عکس» برای انتخاب فایل تصویر استفاده کنید."
            )
            return

        permit_num = self.permit_number_input.text().replace("/", "-")
        page = len(self.scanned_files) + 1
        filename = f"{permit_num}_{company_id}_{self.date_input.text().replace('/', '-')}_p{page}.png"
        filepath = os.path.join(str(SCANS_DIR), filename)

        result = scan_document(filepath)
        if result:
            self.scanned_files.append(result)
            self.scan_list.addItem(f"📄 صفحه {page}: {filename}")
            show_toast(self, "اسکن انجام شد ✓", "success")
        else:
            QMessageBox.warning(self, "خطا", "اسکن ناموفق بود یا لغو شد")

    def _add_image_file(self):
        from PyQt6.QtWidgets import QFileDialog
        company_id = self.company_combo.currentData()
        if company_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا شرکت را انتخاب کنید")
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self, "انتخاب تصویر نامه", "",
            "تصاویر (*.png *.jpg *.jpeg *.bmp *.tiff)"
        )
        if not filepath:
            return

        permit_num = self.permit_number_input.text().replace("/", "-")
        page = len(self.scanned_files) + 1
        filename = f"{permit_num}_{company_id}_{self.date_input.text().replace('/', '-')}_p{page}.png"
        dest_path = os.path.join(str(SCANS_DIR), filename)

        import shutil
        shutil.copy2(filepath, dest_path)
        self.scanned_files.append(dest_path)
        self.scan_list.addItem(f"📄 صفحه {page}: {filename}")

    def _collect_items(self):
        items = []
        for row in range(self.items_table.rowCount()):
            name_widget = self.items_table.cellWidget(row, 0)
            amount_widget = self.items_table.cellWidget(row, 1)
            unit_widget = self.items_table.cellWidget(row, 2)

            if not name_widget or not amount_widget or not unit_widget:
                continue

            product_name = name_widget.text().strip()
            amount = amount_widget.value()
            unit_id = unit_widget.currentData()

            if product_name and amount > 0 and unit_id:
                unit_name = unit_widget.currentText()
                items.append({
                    "product_name": product_name,
                    "amount": amount,
                    "unit_id": unit_id,
                    "unit_name": unit_name,
                })
        return items

    def _validate_date(self):
        """اعتبارسنجی واقعی تاریخ شمسی (فرمت + ماه/روز معتبر)"""
        date_text = self.date_input.text().strip()
        if not is_valid_shamsi_date(date_text):
            QMessageBox.warning(
                self, "خطا",
                "تاریخ نامعتبر است.\n"
                "فرمت صحیح: 1405/06/16 و ماه/روز باید واقعی باشند\n"
                "(مثلاً 1405/13/01 یا 1405/06/31 پذیرفته نمی‌شود)."
            )
            return None
        return date_text

    def _save_and_print(self):
        company_id = self.company_combo.currentData()
        if company_id is None:
            QMessageBox.warning(self, "خطا", "شرکت را انتخاب کنید")
            return

        items = self._collect_items()
        if not items:
            QMessageBox.warning(self, "خطا", "حداقل یک کالا وارد کنید")
            return

        destination = self.destination_input.text().strip()
        customs_rep = self.customs_rep_input.text().strip()
        if not customs_rep:
            QMessageBox.warning(self, "خطا", "نام نماینده گمرک را وارد کنید")
            return

        exit_date = self._validate_date()
        if exit_date is None:
            return

        try:
            quota_items = [
                {"product_name": i["product_name"], "amount": i["amount"], "unit_id": i["unit_id"]}
                for i in items
            ]

            # ─── تأیید کسر سهمیه (گزینه ۳) ───
            preview = preview_deduction(company_id, quota_items)
            if preview:
                if preview["is_over"]:
                    deduct_msg = (
                        f"⚠️ هشدار: مجموع کسر ({preview['total_deduction']} {preview['unit_name']}) "
                        f"از باقیمانده گواهی ({preview['remaining_before']}) بیشتر است!\n"
                        f"مابه‌التفاوت به‌عنوان بدهی ثبت می‌شود.\n\n"
                    )
                else:
                    deduct_msg = (
                        f"باقیمانده پس از کسر: "
                        f"{preview['remaining_after']} {preview['unit_name']}\n\n"
                    )

                reply = QMessageBox.question(
                    self, "تأیید کسر سهمیه",
                    f"از گواهی شماره «{preview['certificate_number']}» "
                    f"({preview['product_type']}) مجموعاً "
                    f"{preview['total_deduction']} {preview['unit_name']} کسر می‌شود.\n\n"
                    f"{deduct_msg}"
                    f"تأیید می‌کنید؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            # ─── گارد گواهی منقض (دفاع عمیق): اگر تنها گواهی فعال منقض باشد ───
            cert = get_active_certificate(company_id)
            if cert is None:
                company = db.fetch_one(
                    "SELECT has_certificate FROM companies WHERE id=?", (company_id,)
                )
                if company and company["has_certificate"]:
                    reply = QMessageBox.question(
                        self, "گواهی منقض",
                        "گواهی فعال این شرکت منقض شده است.\n"
                        "ادامه = ثبت به‌عنوان بدهی. ادامه می‌دهید؟",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.No:
                        return

            # ─── برنامه‌ریزی کسر سهمیه (بدون اثر جانبی) ───
            processed, warnings = process_items(company_id, quota_items)

            if warnings:
                warning_text = "\n\n".join(warnings)
                reply = QMessageBox.question(
                    self, "هشدار سهمیه",
                    f"{warning_text}\n\nآیا ادامه می‌دهید؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return

            if self.edit_mode:
                # ─── حالت ویرایش: ثبت اتمیک ───
                permit_id = self.editing_permit_id
                permit_number = self.permit_number_input.text()

                with db.transaction() as tx:
                    # ۱. بازگردانی سهمیه‌ی کالاهای قبلی
                    restore_permit_quota_tx(tx, permit_id)
                    # ۲. حذف کالاهای قبلی
                    tx.execute(
                        "DELETE FROM exit_items WHERE exit_permit_id=?",
                        (permit_id,)
                    )
                    # ۳. به‌روزرسانی اطلاعات مجوز
                    tx.execute(
                        """UPDATE exit_permits SET company_id=?, exit_date=?,
                           destination=?, customs_representative=?, notes=?
                           WHERE id=?""",
                        (company_id, exit_date, destination, customs_rep,
                         self.notes_input.toPlainText().strip(), permit_id)
                    )
                    # ۴. ثبت کالاهای جدید
                    for item, proc in zip(items, processed):
                        tx.insert(
                            """INSERT INTO exit_items
                               (exit_permit_id, product_name, amount, unit_id,
                                certificate_id, is_debt)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (permit_id, item["product_name"], item["amount"],
                             item["unit_id"], proc["certificate_id"], 1 if proc["is_debt"] else 0)
                        )
                    # ۵. ثبت اسکن‌های جدید (فقط موارد افزوده‌شده)
                    # page_number از شماره‌های موجودِ موجود ادامه می‌یابد،
                    # نه از موقعیت در لیست حافظه — تا اگر ترتیب/حذف تغییر کند،
                    # شماره‌های صفحه‌های قبلی ثابت بمانند
                    max_existing_page = tx.fetch_one(
                        "SELECT COALESCE(MAX(page_number), 0) as mx FROM scanned_documents WHERE exit_permit_id=?",
                        (permit_id,)
                    )["mx"]
                    for i, filepath in enumerate(self.scanned_files, 1):
                        if i > self.original_scan_count:
                            max_existing_page += 1
                            tx.insert(
                                "INSERT INTO scanned_documents (exit_permit_id, file_path, page_number) VALUES (?, ?, ?)",
                                (permit_id, filepath, max_existing_page)
                            )
                    # ۶. کسر سهمیه‌ی گواهی‌ها
                    apply_quota_plan(tx, processed)

                show_toast(self, f"مجوز «{permit_number}» به‌روزرسانی شد ✓", "success", 3000)
                self._reset_form()
                self.back_requested.emit()
                return

            # ─── حالت ثبت جدید: ثبت اتمیک ───
            with db.transaction() as tx:
                permit_number = generate_permit_number_in_tx(tx)

                permit_id = tx.insert(
                    """INSERT INTO exit_permits
                       (permit_number, company_id, exit_date, destination,
                        customs_representative, notes)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (permit_number, company_id, exit_date,
                     destination, customs_rep, self.notes_input.toPlainText().strip())
                )

                for item, proc in zip(items, processed):
                    tx.insert(
                        """INSERT INTO exit_items
                           (exit_permit_id, product_name, amount, unit_id,
                            certificate_id, is_debt)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (permit_id, item["product_name"], item["amount"],
                         item["unit_id"], proc["certificate_id"], 1 if proc["is_debt"] else 0)
                    )

                for i, filepath in enumerate(self.scanned_files, 1):
                    tx.insert(
                        "INSERT INTO scanned_documents (exit_permit_id, file_path, page_number) VALUES (?, ?, ?)",
                        (permit_id, filepath, i)
                    )

                apply_quota_plan(tx, processed)

            print_data = {
                "permit_number": permit_number,
                "exit_date": exit_date,
                "customs_representative": customs_rep,
                "company_name": self.company_combo.currentText(),
                "destination": destination,
                "items": items,
            }

            show_toast(self, f"مجوز «{permit_number}» ثبت شد ✓", "success", 3000)

            reply = QMessageBox.question(
                self, "چاپ روبرگه",
                f"مجوز خروج با شماره «{permit_number}» ثبت شد.\n\n"
                "می‌خواهید روبرگه را چاپ کنید؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    printed = print_exit_permit(print_data, show_dialog=True)
                    if not printed:
                        from PyQt6.QtWidgets import QFileDialog
                        pdf_path, _ = QFileDialog.getSaveFileName(
                            self, "ذخیره روبرگه", f"{permit_number}.pdf", "PDF (*.pdf)"
                        )
                        if pdf_path:
                            if print_to_pdf(print_data, pdf_path):
                                show_toast(self, "روبرگه PDF شد ✓", "success")
                except Exception as e:
                    QMessageBox.warning(
                        self, "خطای چاپ",
                        f"چاپ مستقیم ناموفق بود: {e}\n"
                        "مجوز خروج با موفقیت ثبت شد."
                    )

            self._reset_form()

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در ثبت: {e}")

    def _reset_form(self):
        """پاک کردن فرم و برگشت به حالت ثبت جدید"""
        self.edit_mode = False
        self.editing_permit_id = None
        self.original_scan_count = 0
        self.edit_header.hide()
        self.btn_save_print.setText("💾 ذخیره و چاپ")

        self.destination_input.clear()
        self.customs_rep_input.clear()
        self.notes_input.clear()
        self.scanned_files = []
        self.scan_list.clear()
        self.company_combo.setCurrentIndex(0)
        while self.items_table.rowCount() > 0:
            self.items_table.removeRow(0)
        self._add_item_row()
        self.permit_number_input.setText(get_next_number_preview())
        self.date_input.setText(jdatetime.date.today().strftime("%Y/%m/%d"))