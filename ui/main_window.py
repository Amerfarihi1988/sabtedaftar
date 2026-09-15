"""
پنجره اصلی نرم‌افزار - داشبورد (قالب مدرن، تک‌پنجره‌ای)
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QListWidget,
    QListWidgetItem, QStatusBar, QStackedWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from database.db_manager import db
from services.quota import is_low_quota
from services.backup import auto_backup_if_needed
from ui.company_window import CompanyWindow
from ui.certificate_window import CertificateWindow
from ui.exit_permit_window import ExitPermitWindow
from ui.search_window import SearchWindow
from ui.settings_window import SettingsWindow
from ui.reports_window import ReportsWindow
from config import APP_NAME, APP_VERSION
import jdatetime


class StatCard(QFrame):
    """کارت آماری گرادیانی مدرن"""

    GRADIENTS = {
        "blue": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366F1, stop:1 #8B5CF6)",
        "green": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10B981, stop:1 #34D399)",
        "purple": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8B5CF6, stop:1 #D946EF)",
        "red": "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F43F5E, stop:1 #FB7185)",
    }

    def __init__(self, title, color="blue"):
        super().__init__()
        self.setObjectName("statCard")
        self.setFixedHeight(100)
        self.setStyleSheet(f"""
            QFrame#statCard {{
                background-color: {self.GRADIENTS.get(color, self.GRADIENTS['blue'])};
                border-radius: 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)

        self.value_label = QLabel("۰")
        self.value_label.setStyleSheet(
            "font-size: 30px; font-weight: bold; color: white; background: transparent;"
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-size: 12px; color: rgba(255,255,255,210); background: transparent;"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)

    def set_value(self, value):
        self.value_label.setText(self._to_persian(value))

    def _to_persian(self, num):
        return str(num).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — نسخه {APP_VERSION}")
        self.resize(1200, 760)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        self.dashboard_page = self._create_dashboard()
        self.company_page = CompanyWindow()
        self.cert_page = CertificateWindow()
        self.permit_page = ExitPermitWindow()
        self.search_page = SearchWindow()
        self.reports_page = ReportsWindow()
        self.settings_page = SettingsWindow()

        self.stack.addWidget(self.dashboard_page)   # index 0
        self.stack.addWidget(self.company_page)     # index 1
        self.stack.addWidget(self.cert_page)        # index 2
        self.stack.addWidget(self.permit_page)      # index 3
        self.stack.addWidget(self.search_page)      # index 4
        self.stack.addWidget(self.reports_page)     # index 5
        self.stack.addWidget(self.settings_page)    # index 6

        for page in [self.company_page, self.cert_page,
                     self.permit_page, self.search_page,
                     self.reports_page, self.settings_page]:
            page.back_requested.connect(self._go_dashboard)

        self.search_page.edit_permit_requested.connect(self._open_edit_permit)

        status = QStatusBar()
        self.setStatusBar(status)
        today = jdatetime.date.today().strftime("%Y/%m/%d")
        status.showMessage(f"  امروز: {today}")

    def _create_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(215)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 24, 14, 24)
        layout.setSpacing(6)

        title = QLabel("دفتر خروج کالا")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("مدیریت مجوز خروج کالا")
        subtitle.setObjectName("appSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        line = QFrame()
        line.setObjectName("goldLine")
        line.setFixedHeight(1)
        layout.addSpacing(10)
        layout.addWidget(line)
        layout.addSpacing(14)

        buttons = [
            ("🏠  داشبورد", "dashboard"),
            ("🏢  مدیریت شرکت‌ها", "companies"),
            ("📜  گواهی‌های تولید", "certificates"),
            ("➕  ثبت مجوز خروج", "new_permit"),
            ("🔍  جستجو و گزارش", "search"),
            ("📈  گزارش‌های رسمی", "reports"),
            ("⚙️  تنظیمات", "settings"),
        ]

        self.nav_buttons = {}
        for text, key in buttons:
            btn = QPushButton(text)
            btn.setFixedHeight(44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if key == "dashboard":
                btn.setObjectName("active")
            btn.clicked.connect(lambda checked, k=key: self._on_nav_click(k))
            layout.addWidget(btn)
            self.nav_buttons[key] = btn

        layout.addStretch()

        btn_exit = QPushButton("🚪  خروج از برنامه")
        btn_exit.setObjectName("btnExit")
        btn_exit.setFixedHeight(40)
        btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_exit.clicked.connect(self.close)
        layout.addWidget(btn_exit)

        return sidebar

    def _create_dashboard(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("pageHeader")
        header.setFixedHeight(64)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 10, 18, 10)

        self.page_title = QLabel("داشبورد")
        self.page_title.setObjectName("pageTitle")
        header_layout.addWidget(self.page_title)
        header_layout.addStretch()

        today = jdatetime.date.today().strftime("%Y/%m/%d")
        date_label = QLabel(f"📅 امروز: {today}")
        date_label.setObjectName("pageDate")
        header_layout.addWidget(date_label)

        layout.addWidget(header)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(14)

        self.card_today = StatCard("خروج امروز", "blue")
        self.card_companies = StatCard("کل شرکت‌ها", "green")
        self.card_certificates = StatCard("گواهی‌های فعال", "purple")
        self.card_debts = StatCard("بدهی گواهی", "red")

        cards_layout.addWidget(self.card_today, 0, 0)
        cards_layout.addWidget(self.card_companies, 0, 1)
        cards_layout.addWidget(self.card_certificates, 0, 2)
        cards_layout.addWidget(self.card_debts, 0, 3)
        layout.addLayout(cards_layout)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(14)

        today_group = QGroupBox("✨ خروج‌های ثبت‌شده امروز")
        today_layout = QVBoxLayout(today_group)
        self.today_table = QTableWidget(0, 4)
        self.today_table.setHorizontalHeaderLabels(
            ["شماره ثبت", "شرکت", "مقصد", "زمان ثبت"]
        )
        self.today_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.today_table.setAlternatingRowColors(True)
        self.today_table.verticalHeader().setVisible(False)
        today_layout.addWidget(self.today_table)
        bottom_layout.addWidget(today_group, stretch=2)

        alerts_group = QGroupBox("🔔 هشدارها")
        alerts_layout = QVBoxLayout(alerts_group)

        debt_label = QLabel("شرکت‌های دارای بدهی گواهی:")
        debt_label.setStyleSheet("font-weight: bold; color: #E11D48; font-size: 12px;")
        alerts_layout.addWidget(debt_label)

        self.debt_list = QListWidget()
        alerts_layout.addWidget(self.debt_list)

        warn_label = QLabel("گواهی‌های رو به اتمام (۹۰٪ و بیشتر):")
        warn_label.setStyleSheet("font-weight: bold; color: #D97706; font-size: 12px;")
        alerts_layout.addWidget(warn_label)

        self.warn_list = QListWidget()
        alerts_layout.addWidget(self.warn_list)

        bottom_layout.addWidget(alerts_group, stretch=1)
        layout.addLayout(bottom_layout, stretch=1)

        return container

    def _load_data(self):
        """بارگذاری داده‌های داشبورد"""
        today = jdatetime.date.today().strftime("%Y/%m/%d")

        today_permits = db.fetch_all(
            "SELECT COUNT(*) as cnt FROM exit_permits WHERE exit_date = ?",
            (today,)
        )
        self.card_today.set_value(today_permits[0]["cnt"] if today_permits else 0)

        companies = db.fetch_all("SELECT COUNT(*) as cnt FROM companies")
        self.card_companies.set_value(companies[0]["cnt"] if companies else 0)

        certs = db.fetch_all(
            "SELECT COUNT(*) as cnt FROM certificates WHERE status = 'active'"
        )
        self.card_certificates.set_value(certs[0]["cnt"] if certs else 0)

        debts = db.fetch_all(
            "SELECT COUNT(*) as cnt FROM exit_items WHERE is_debt = 1 AND debt_settled = 0"
        )
        self.card_debts.set_value(debts[0]["cnt"] if debts else 0)

        self.today_table.setRowCount(0)
        today_records = db.fetch_all(
            """SELECT ep.permit_number, c.name, ep.destination, ep.created_at
               FROM exit_permits ep
               JOIN companies c ON ep.company_id = c.id
               WHERE ep.exit_date = ?
               ORDER BY ep.created_at DESC""",
            (today,)
        )
        for row_data in today_records:
            row = self.today_table.rowCount()
            self.today_table.insertRow(row)
            self.today_table.setItem(row, 0, QTableWidgetItem(row_data["permit_number"]))
            self.today_table.setItem(row, 1, QTableWidgetItem(row_data["name"]))
            self.today_table.setItem(row, 2, QTableWidgetItem(row_data["destination"] or ""))
            self.today_table.setItem(row, 3, QTableWidgetItem(row_data["created_at"]))

        self.debt_list.clear()
        debt_records = db.fetch_all(
            """SELECT c.name, SUM(ei.amount) as debt_amount, u.name as unit
               FROM exit_items ei
               JOIN exit_permits ep ON ei.exit_permit_id = ep.id
               JOIN companies c ON ep.company_id = c.id
               JOIN units u ON ei.unit_id = u.id
               WHERE ei.is_debt = 1 AND ei.debt_settled = 0
               GROUP BY c.id, u.id"""
        )
        for rec in debt_records:
            item = QListWidgetItem(f"  🔴 {rec['name']} — بدهی: {rec['debt_amount']} {rec['unit']}")
            item.setForeground(QColor("#E11D48"))
            self.debt_list.addItem(item)

        self.warn_list.clear()
        warn_records = db.fetch_all(
            """SELECT c.name, cert.remaining_amount, cert.total_amount,
                      cert.product_type, u.name as unit
               FROM certificates cert
               JOIN companies c ON cert.company_id = c.id
               JOIN units u ON cert.unit_id = u.id
               WHERE cert.status = 'active'"""
        )
        for rec in warn_records:
            if not is_low_quota(rec["total_amount"], rec["remaining_amount"]):
                continue
            item = QListWidgetItem(
                f"  🟡 {rec['name']} — باقیمانده: {rec['remaining_amount']} {rec['unit']} ({rec['product_type']})"
            )
            item.setForeground(QColor("#D97706"))
            self.warn_list.addItem(item)

    def _on_nav_click(self, key):
        titles = {
            "dashboard": "داشبورد",
            "companies": "مدیریت شرکت‌ها",
            "certificates": "گواهی‌های تولید",
            "new_permit": "ثبت مجوز خروج",
            "search": "جستجو و گزارش",
            "reports": "گزارش‌های رسمی",
            "settings": "تنظیمات",
        }
        pages = {
            "dashboard": 0,
            "companies": 1,
            "certificates": 2,
            "new_permit": 3,
            "search": 4,
            "reports": 5,
            "settings": 6,
        }

        for k, btn in self.nav_buttons.items():
            btn.setObjectName("active" if k == key else "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.page_title.setText(titles[key])
        self.stack.setCurrentIndex(pages[key])

        if key == "dashboard":
            self._load_data()
        elif key == "search":
            self.search_page.refresh_page()
            self.search_page._load_results()
        elif key == "companies":
            self.company_page._load_companies()
        elif key == "certificates":
            self.cert_page._load_certificates()
        elif key == "new_permit":
            self.permit_page.refresh_page()
        elif key == "reports":
            self.reports_page.refresh_page()
        elif key == "settings":
            self.settings_page._load_backups()

    def maybe_auto_backup(self):
        """پشتیبان‌گیری خودکار روزانه هنگام باز شدن برنامه (اگر در تنظیمات فعال باشد)"""
        try:
            path = auto_backup_if_needed()
            if path:
                self.statusBar().showMessage(
                    f"  💾 پشتیبان‌گیری خودکار انجام شد: {path}", 10000
                )
        except Exception as e:
            # بکاپ هرگز نباید باز شدن برنامه را مختل کند
            print(f"[پشتیبان خودکار] خطا: {e}")

    def _go_dashboard(self):
        self._on_nav_click("dashboard")

    def _open_edit_permit(self, permit_id):
        """ورود به صفحه ثبت در حالت ویرایش مجوز"""
        for k, btn in self.nav_buttons.items():
            btn.setObjectName("active" if k == "new_permit" else "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.page_title.setText("ویرایش مجوز خروج")
        self.stack.setCurrentIndex(3)
        self.permit_page.load_for_edit(permit_id)