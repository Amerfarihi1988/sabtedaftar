"""
صفحه تسویه بدهی‌های گواهی — لیست بدهی‌های تسویه‌نشده به تفکیک شرکت/واحد

تسویه مستقیم: انتخاب گواهی فعال برای هر بدهی → کسر از باقیمانده گواهی +
علامت‌گذاری debt_settled + اتصال certificate_id — همه در یک تراکنش اتمیک.
"""
import traceback
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QComboBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from database.db_manager import db


class DebtWindow(QWidget):
    """صفحه تسویه بدهی‌های گواهی"""
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.refresh_page()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        header = QLabel("🔴 بدهی‌های تسویه‌نشده — خروج‌هایی که سهمیه گواهی نداشتند")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #E11D48; padding: 4px;")
        layout.addWidget(header)

        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet("font-size: 12px; color: #555; padding: 2px 4px;")
        layout.addWidget(self.lbl_summary)

        table_group = QGroupBox("بدهی‌ها به تفکیک مجوز")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "تاریخ", "شماره ثبت", "شرکت", "کالا",
            "مقدار بدهی", "تسویه با گواهی"
        ])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 180)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 240)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        table_layout.addWidget(self.table)
        layout.addWidget(table_group, stretch=1)

        btn_row = QHBoxLayout()
        self.btn_settle = QPushButton("✅ تسویه انتخاب‌شده‌ها")
        self.btn_settle.setObjectName("btnSuccess")
        self.btn_settle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settle.clicked.connect(self._settle_selected)

        btn_back = QPushButton("بازگشت به داشبورد")
        btn_back.setObjectName("btnDefault")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.back_requested.emit)

        btn_row.addWidget(self.btn_settle)
        btn_row.addStretch()
        btn_row.addWidget(btn_back)
        layout.addLayout(btn_row)

        self.setStyleSheet("""
            QTableWidget { border: 1px solid #E4E7F2; border-radius: 10px; font-size: 13px; }
            QHeaderView::section {
                background-color: #F0F2F8; color: #4F46E5;
                font-weight: bold; padding: 8px; border: none;
                border-bottom: 2px solid #4F46E5;
            }
        """)

    def refresh_page(self):
        self._load_debts()

    def _load_debts(self):
        """بارگذاری بدهی‌های تسویه‌نشده با گواهی‌های فعال هم‌واحد برای هر ردیف"""
        try:
            debts = db.fetch_all(
                """SELECT ei.id as item_id, ei.amount, ei.product_name,
                          ep.exit_date, ep.permit_number, ep.company_id,
                          c.name as company_name, u.name as unit_name, ei.unit_id
                   FROM exit_items ei
                   JOIN exit_permits ep ON ei.exit_permit_id = ep.id
                   JOIN companies c ON ep.company_id = c.id
                   JOIN units u ON ei.unit_id = u.id
                   WHERE ei.is_debt = 1 AND ei.debt_settled = 0
                   ORDER BY ep.exit_date, ep.id"""
            )
            certs = db.fetch_all(
                """SELECT cert.id, cert.company_id, cert.unit_id, cert.remaining_amount,
                          cert.certificate_number, cert.product_type
                   FROM certificates cert
                   WHERE cert.status = 'active' AND cert.remaining_amount > 0
                   ORDER BY cert.remaining_amount DESC"""
            )

            self.table.setRowCount(0)
            for d in debts:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(d["exit_date"] or ""))
                self.table.setItem(row, 1, QTableWidgetItem(d["permit_number"] or ""))
                self.table.setItem(row, 2, QTableWidgetItem(d["company_name"] or ""))
                self.table.setItem(
                    row, 3,
                    QTableWidgetItem(f"{d['product_name']} ({d['unit_name']})")
                )
                amt = int(d["amount"]) if d["amount"] == int(d["amount"]) else d["amount"]
                amt_item = QTableWidgetItem(f"{amt:g} {d['unit_name']}")
                amt_item.setForeground(QColor("#E11D48"))
                self.table.setItem(row, 4, amt_item)

                # کمبوی گواهی‌های فعال هم‌شرکت و هم‌واحد با ظرفیت کافی
                combo = QComboBox()
                eligible = [
                    c for c in certs
                    if c["company_id"] == d["company_id"]
                    and c["unit_id"] == d["unit_id"]
                    and c["remaining_amount"] >= d["amount"]
                ]
                combo.addItem("— انتخاب گواهی —", None)
                for c in eligible:
                    rem = c["remaining_amount"]
                    rem_str = f"{int(rem):,}" if rem == int(rem) else f"{rem:,.2f}"
                    combo.addItem(
                        f"{c['certificate_number']} — باقیمانده {rem_str}",
                        c["id"]
                    )
                self.table.setCellWidget(row, 5, combo)

            self.lbl_summary.setText(
                f"{len(debts)} بدهی تسویه‌نشده" if debts
                else "هیچ بدهی تسویه‌نشده‌ای وجود ندارد ✓"
            )
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"خطا در بارگذاری بدهی‌ها: {e}")

    def _settle_selected(self):
        """تسویه بدهی‌های ردیف‌هایی که گواهی برایشان انتخاب شده — اتمیک و گروهی"""
        settlements = []  # (item_id, cert_id, amount)
        # شناسه ردیف‌ها هم‌تراز با ترتیب _load_debts خوانده می‌شود
        # (همان کوئری با همان ORDER BY؛ کمبوها به همین ترتیب ساخته شده‌اند)
        debts_sorted_ui = db.fetch_all(
            """SELECT ei.id as item_id, ei.amount
               FROM exit_items ei
               JOIN exit_permits ep ON ei.exit_permit_id = ep.id
               WHERE ei.is_debt = 1 AND ei.debt_settled = 0
               ORDER BY ep.exit_date, ep.id"""
        )
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 5)
            if combo is None:
                continue
            cert_id = combo.currentData()
            if cert_id is None:
                continue
            if row < len(debts_sorted_ui):
                settlements.append(
                    (debts_sorted_ui[row]["item_id"], cert_id,
                     debts_sorted_ui[row]["amount"])
                )

        if not settlements:
            QMessageBox.warning(
                self, "انتخاب نشده",
                "برای هیچ ردیفی گواهی انتخاب نشده است.\n"
                "در ستون «تسویه با گواهی» گواهی مناسب را انتخاب کنید."
            )
            return

        reply = QMessageBox.question(
            self, "تأیید تسویه",
            f"{len(settlements)} بدهی تسویه می‌شود و از باقیمانده گواهی‌های "
            f"انتخاب‌شده کسر می‌گردد.\nادامه می‌دهید؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            with db.transaction() as tx:
                for item_id, cert_id, amount in settlements:
                    # قفل منطقی: بدهی هنوز تسویه‌نشده باشد
                    row = tx.fetch_one(
                        "SELECT amount, debt_settled FROM exit_items WHERE id=?",
                        (item_id,)
                    )
                    if not row or row["debt_settled"] == 1:
                        continue

                    cert = tx.fetch_one(
                        "SELECT remaining_amount, status FROM certificates WHERE id=?",
                        (cert_id,)
                    )
                    if not cert or cert["status"] == 'archived':
                        raise ValueError("گواهی انتخابی معتبر نیست")

                    new_remaining = cert["remaining_amount"] - row["amount"]
                    if new_remaining < 0:
                        raise ValueError(
                            "باقیمانده گواهی برای این بدهی کافی نیست — "
                            "صفحه را رفرش و دوباره تلاش کنید"
                        )
                    status = 'active' if new_remaining > 0 else 'exhausted'
                    tx.execute(
                        "UPDATE certificates SET remaining_amount=?, status=? WHERE id=?",
                        (new_remaining, status, cert_id)
                    )
                    tx.execute(
                        "UPDATE exit_items SET debt_settled=1, certificate_id=? WHERE id=?",
                        (cert_id, item_id)
                    )

            QMessageBox.information(
                self, "موفق",
                f"✅ {len(settlements)} بدهی تسویه شد و به گواهی‌ها متصل گردید."
            )
            self._load_debts()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "خطا", f"تسویه انجام نشد: {e}")
