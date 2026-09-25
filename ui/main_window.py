"""
پنجره اصلی نرم‌افزار — نوار ناوبری بالا (قالب اداری تک‌پنجره‌ای)
منو به‌صورت تب‌های افقی زیر هدر؛ آیکون‌های SVG تک‌رنگ (بدون ایموجی)
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QListWidget,
    QListWidgetItem, QStatusBar, QStackedWidget
)
from PyQt6.QtCore import Qt, QSize, QTimer, QByteArray, QSettings
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer
from database.db_manager import db
from services.quota import is_low_quota, get_expiring_certificates, forecast_certificate_exhaustion
from services.backup import auto_backup_if_needed
from ui.company_window import CompanyWindow
from ui.certificate_window import CertificateWindow
from ui.exit_permit_window import ExitPermitWindow
from ui.search_window import SearchWindow
from ui.settings_window import SettingsWindow
from ui.reports_window import ReportsWindow
from ui.debt_window import DebtWindow
from ui.charts_window import ChartsWindow
from ui.ui_helpers import fade_in, show_toast, format_thousands, set_table_empty_state, set_cell_pill
from config import APP_NAME, APP_VERSION
import jdatetime


# ─── آیکون‌های SVG تک‌رنگ (stroke=currentColor برای رنگ‌آمیزی داینامیک) ───
_S = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
ICONS = {
    "dashboard": f'<svg viewBox="0 0 24 24" {_S}><path d="M3 11l9-8 9 8"/><path d="M5 9.8V21h14V9.8"/></svg>',
    "new_permit": f'<svg viewBox="0 0 24 24" {_S}><circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/></svg>',
    "search": f'<svg viewBox="0 0 24 24" {_S}><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>',
    "reports": f'<svg viewBox="0 0 24 24" {_S}><path d="M4 20h16"/><path d="M7 20v-6M12 20V10M17 20v-4"/></svg>',
    "certificates": f'<svg viewBox="0 0 24 24" {_S}><path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/><path d="M9.5 14l2 2 3.5-3.5"/></svg>',
    "companies": f'<svg viewBox="0 0 24 24" {_S}><rect x="4" y="3" width="16" height="18" rx="1.5"/><path d="M8 7h2M14 7h2M8 11h2M14 11h2M8 15h2M14 15h2"/></svg>',
    "settings": f'<svg viewBox="0 0 24 24" {_S}><path d="M4 7h10M18 7h2M16 5v4"/><path d="M4 17h2M10 17h10M8 15v4"/></svg>',
    "debts": f'<svg viewBox="0 0 24 24" {_S}><path d="M12 3v18"/><circle cx="7" cy="12" r="4.5"/><path d="M17 12h4"/></svg>',
    "charts": f'<svg viewBox="0 0 24 24" {_S}><path d="M4 20h16"/><path d="M6 16l4-4 3 3 5-6"/><path d="M17 9h3v3"/></svg>',
    "exit": f'<svg viewBox="0 0 24 24" {_S}><path d="M14 8V5a1.5 1.5 0 0 0-1.5-1.5H6A1.5 1.5 0 0 0 4.5 5v14A1.5 1.5 0 0 0 6 20.5h6.5A1.5 1.5 0 0 0 14 19v-3"/><path d="M9 12h11M17 9l3 3-3 3"/></svg>',
}


def make_icon(svg, color):
    """ساخت QIcon از رشته SVG با رنگ مشخص (currentColor جایگزین می‌شود)"""
    renderer = QSvgRenderer(QByteArray(svg.replace("currentColor", color).encode("utf-8")))
    pixmap = QPixmap(36, 36)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    icon = QIcon()
    icon.addPixmap(pixmap)
    return icon


class StatCard(QFrame):
    """کارت آماری رنگی تخت (بدون گرادیان)"""

    COLORS = {
        "blue": ("#EEF2FF", "#4F46E5"),
        "green": ("#ECFDF5", "#059669"),
        "purple": ("#F5F3FF", "#7C3AED"),
        "red": ("#FEF2F2", "#DC2626"),
    }

    def __init__(self, title, color="blue", icon_svg=None):
        super().__init__()
        self.setObjectName("statCard")
        self.setFixedHeight(92)

        bg, fg = self.COLORS.get(color, self.COLORS["blue"])
        self.setStyleSheet(f"QFrame#statCard {{ background-color: {bg}; border-radius: 14px; border: 1px solid transparent; }}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        icon_label = QLabel()
        if icon_svg:
            icon_label.setPixmap(make_icon(icon_svg, fg).pixmap(26, 26))
        icon_label.setFixedSize(42, 42)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            f"background-color: white; border-radius: 11px; color: {fg};"
        )
        layout.addWidget(icon_label)

        text_box = QVBoxLayout()
        text_box.setSpacing(0)

        self.value_label = QLabel("۰")
        self.value_label.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {fg}; background: transparent; border: none;"
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-size: 12px; color: #6B7280; background: transparent; border: none;"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        text_box.addStretch()
        text_box.addWidget(self.value_label)
        text_box.addWidget(self.title_label)
        text_box.addStretch()

        layout.addLayout(text_box)
        layout.addStretch()

    def set_value(self, value):
        self.value_label.setText(self._to_persian(value))

    def _to_persian(self, num):
        return str(num).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — نسخه {APP_VERSION}")
        self.resize(1200, 760)
        self._layout_settled = False
        self._current_nav = "dashboard"
        self._setup_ui()
        self._load_data()
        self._install_shortcuts()

    def showEvent(self, event):
        super().showEvent(event)
        # بار اول که استایل‌ها polish می‌شوند، sizeHint ویجت‌ها عوض می‌شود ولی
        # چیدمان قبلی می‌ماند → رندر ناقص تا مینیمم/ماکسیمم دستی.
        # یک بار بعد از نمایش، چیدمان همه صفحات را مجبور به محاسبه دوباره می‌کنیم.
        if not self._layout_settled:
            self._layout_settled = True
            QTimer.singleShot(60, self._settle_layouts)

    def _settle_layouts(self):
        for i in range(self.stack.count()):
            lay = self.stack.widget(i).layout()
            if lay:
                lay.invalidate()
                lay.activate()
        lay = self.centralWidget().layout()
        if lay:
            lay.invalidate()
            lay.activate()
        self.update()

    # ─── یادآوری چیدمان پنجره (QSettings) ───

    def _settings_obj(self):
        return QSettings("SabteDaftar", "DafterKhorojKala")

    def restore_layout(self):
        """بازیابی سایز/موقعیت پنجره و تب آخر از اجرای قبل
        نکته: restoreGeometry در صفحات شلوغ گاهی به minimumSize گیر می‌کند؛
        بنابراین اندازه را مستقیم هم اعمال می‌کنیم (geometry کامل، نه فقط حدس)"""
        try:
            s = self._settings_obj()
            geo = s.value("window/geometry")
            if geo is not None:
                # در save_layout به‌صورت hex رشته ذخیره شده — باید fromHex شود
                if isinstance(geo, str):
                    raw = QByteArray.fromHex(geo.encode("utf-8"))
                elif isinstance(geo, (bytes, bytearray)):
                    raw = QByteArray.fromHex(bytes(geo))
                else:
                    raw = geo  # QByteArray مستقیم
                self.restoreGeometry(raw)
                # fallback: restoreGeometry گاهی در صفحات سنگین fails می‌شود؛
                # اگر سایز خیلی با ذخیره فرق دارد، minimumSize را موقتاً رها کن
                saved_w = s.value("window/width", 0, type=int)
                saved_h = s.value("window/height", 0, type=int)
                if saved_w > 400 and saved_h > 300:
                    if abs(self.width() - saved_w) > 40 or abs(self.height() - saved_h) > 40:
                        self.resize(saved_w, saved_h)
            if s.value("window/maximized", "0") == "1":
                self.showMaximized()
            last = s.value("window/last_nav", "dashboard")
            if last in self.nav_buttons:
                self._on_nav_click(last)
        except Exception:
            pass

    def save_layout(self):
        """ذخیره چیدمان هنگام بستن برنامه"""
        try:
            s = self._settings_obj()
            s.setValue("window/geometry", bytes(self.saveGeometry().toHex()))
            # اندازه صریح هم ذخیره می‌شود — fallback برای restoreGeometry
            if not self.isMaximized():
                s.setValue("window/width", self.width())
                s.setValue("window/height", self.height())
            s.setValue("window/maximized", "1" if self.isMaximized() else "0")
            s.setValue("window/last_nav", self._current_nav)
        except Exception:
            pass

    def closeEvent(self, event):
        self.save_layout()
        super().closeEvent(event)

    # ─── میان‌برهای صفحه‌کلید ───

    def _install_shortcuts(self):
        """F1-F9 ناوبری + Esc بازگشت به داشبورد + F1 در هر جا داشبورد"""
        from PyQt6.QtGui import QShortcut, QKeySequence
        keys = {
            "dashboard": "F1", "new_permit": "F2", "search": "F3",
            "charts": "F4", "reports": "F5", "certificates": "F6",
            "debts": "F7", "companies": "F8", "settings": "F9",
        }
        for key, seq in keys.items():
            sc = QShortcut(QKeySequence(seq), self)
            sc.activated.connect(lambda k=key: self._on_nav_click(k))
        esc = QShortcut(QKeySequence("Esc"), self)
        esc.activated.connect(self._go_dashboard)

    def _show_shortcuts_dialog(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("میان‌برهای صفحه‌کلید")
        lay = QVBoxLayout(dlg)
        rows = [
            ("F1", "داشبورد"), ("F2", "ثبت مجوز خروج"), ("F3", "جستجو و گزارش"),
            ("F4", "نمودارها"), ("F5", "گزارش‌های رسمی"), ("F6", "گواهی‌های تولید"),
            ("F7", "تسویه بدهی‌ها"), ("F8", "مدیریت شرکت‌ها"), ("F9", "تنظیمات"),
            ("Esc", "بازگشت به داشبورد"), ("Ctrl+S", "ذخیره فرم مجوز"),
        ]
        for k, d in rows:
            lbl = QLabel(f"<b style='color:#4F46E5'>{k}</b> — {d}")
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(lbl)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._create_topbar())

        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self.dashboard_page = self._create_dashboard()
        self.company_page = CompanyWindow()
        self.cert_page = CertificateWindow()
        self.permit_page = ExitPermitWindow()
        self.search_page = SearchWindow()
        self.reports_page = ReportsWindow()
        self.settings_page = SettingsWindow()
        self.debt_page = DebtWindow()
        self.charts_page = ChartsWindow()

        self.stack.addWidget(self.dashboard_page)   # index 0
        self.stack.addWidget(self.company_page)     # index 1
        self.stack.addWidget(self.cert_page)        # index 2
        self.stack.addWidget(self.permit_page)      # index 3
        self.stack.addWidget(self.search_page)      # index 4
        self.stack.addWidget(self.reports_page)     # index 5
        self.stack.addWidget(self.settings_page)    # index 6
        self.stack.addWidget(self.debt_page)        # index 7
        self.stack.addWidget(self.charts_page)      # index 8

        for page in [self.company_page, self.cert_page,
                     self.permit_page, self.search_page,
                     self.reports_page, self.settings_page,
                     self.debt_page, self.charts_page]:
            page.back_requested.connect(self._go_dashboard)

        self.search_page.edit_permit_requested.connect(self._open_edit_permit)
        self.search_page.duplicate_permit_requested.connect(self._open_duplicate_permit)

        status = QStatusBar()
        self.setStatusBar(status)
        today = jdatetime.date.today().strftime("%Y/%m/%d")
        status.showMessage(f"  امروز: {today}")

    def _create_topbar(self):
        """هدر سفید + تب‌های افقی ناوبری"""
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(100)

        lay = QVBoxLayout(bar)
        lay.setContentsMargins(18, 10, 18, 0)
        lay.setSpacing(0)

        # ─── ردیف برند: لوگو + عنوان + تاریخ + خروج ───
        brand = QHBoxLayout()
        brand.setSpacing(10)

        logo = QLabel("د")
        logo.setObjectName("logomark")
        logo.setFixedSize(36, 36)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        t1 = QLabel(APP_NAME)
        t1.setObjectName("appTitle")
        t2 = QLabel("مدیریت مجوز خروج کالا")
        t2.setObjectName("appSubtitle")
        title_box.addWidget(t1)
        title_box.addWidget(t2)
        brand.addLayout(title_box)

        brand.addStretch()

        today = jdatetime.date.today().strftime("%Y/%m/%d")
        date_label = QLabel(f"📅 {today}")
        date_label.setObjectName("pageDate")
        brand.addWidget(date_label)
        brand.addSpacing(12)

        btn_exit = QPushButton("خروج از برنامه")
        btn_exit.setObjectName("btnExitTop")
        btn_exit.setIcon(make_icon(ICONS["exit"], "#DC2626"))
        btn_exit.setIconSize(QSize(15, 15))
        btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_exit.clicked.connect(self.close)
        brand.addWidget(btn_exit)

        lay.addLayout(brand)

        # ─── ردیف تب‌های ناوبری ───
        nav_items = [
            ("dashboard", "داشبورد"),
            ("new_permit", "ثبت مجوز خروج"),
            ("search", "جستجو و گزارش"),
            ("charts", "نمودارها"),
            ("reports", "گزارش‌های رسمی"),
            ("certificates", "گواهی‌های تولید"),
            ("debts", "تسویه بدهی‌ها"),
            ("companies", "مدیریت شرکت‌ها"),
            ("settings", "تنظیمات"),
        ]

        tabs = QHBoxLayout()
        tabs.setSpacing(2)
        self.nav_buttons = {}
        for key, text in nav_items:
            btn = QPushButton(text)
            btn.setProperty("nav", True)
            btn.setIcon(make_icon(ICONS[key], "#6B7280"))
            btn.setIconSize(QSize(17, 17))
            btn.setFixedHeight(44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, k=key: self._on_nav_click(k))
            tabs.addWidget(btn)
            self.nav_buttons[key] = btn
        self._set_active_nav("dashboard")
        lay.addLayout(tabs)

        return bar

    def _set_active_nav(self, key):
        """مشخص کردن تب فعال: خط زیرینی + رنگ + آیکون رنگی"""
        for k, btn in self.nav_buttons.items():
            is_active = (k == key)
            btn.setProperty("active", is_active)
            btn.setIcon(make_icon(ICONS[k], "#4F46E5" if is_active else "#6B7280"))
            btn.style().unpolish(btn)
            btn.style().polish(btn)

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

        # ─── ردیف اقدام سریع — پرکارترین کارها یک کلیک ───
        quick_row = QHBoxLayout()
        quick_row.setSpacing(12)

        def quick_btn(text, icon_key, color, nav_key):
            b = QPushButton(f"  {text}")
            b.setIcon(make_icon(ICONS[icon_key], "white"))
            b.setIconSize(QSize(17, 17))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(44)
            b.setStyleSheet(
                f"background-color: {color}; color: white; font-weight: bold;"
                "border: none; border-radius: 12px; font-size: 13px; padding: 0 20px;"
            )
            b.clicked.connect(lambda: self._on_nav_click(nav_key))
            return b

        quick_row.addWidget(quick_btn("ثبت مجوز جدید", "new_permit", "#4F46E5", "new_permit"))
        quick_row.addWidget(quick_btn("جستجو", "search", "#0891B2", "search"))
        quick_row.addWidget(quick_btn("تسویه بدهی‌ها", "debts", "#D97706", "debts"))
        quick_row.addWidget(quick_btn("پشتیبان‌گیری", "settings", "#059669", "settings"))
        quick_row.addStretch()

        btn_keys = QPushButton("⌨ میان‌برها")
        btn_keys.setObjectName("btnDefault")
        btn_keys.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_keys.setFixedHeight(44)
        btn_keys.clicked.connect(self._show_shortcuts_dialog)
        quick_row.addWidget(btn_keys)

        layout.addLayout(quick_row)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(14)

        self.card_today = StatCard("خروج امروز", "blue", ICONS["dashboard"])
        self.card_companies = StatCard("کل شرکت‌ها", "green", ICONS["companies"])
        self.card_certificates = StatCard("گواهی‌های فعال", "purple", ICONS["certificates"])
        self.card_debts = StatCard("بدهی گواهی", "red", ICONS["reports"])

        # کارت‌های قابل کلیک → میان‌بر به صفحه مربوط
        self.card_today.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card_today.setToolTip("مشاهده جستجو")
        self.card_today.mouseReleaseEvent = lambda e: self._on_nav_click("search")

        self.card_companies.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card_companies.setToolTip("مدیریت شرکت‌ها")
        self.card_companies.mouseReleaseEvent = lambda e: self._on_nav_click("companies")

        self.card_certificates.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card_certificates.setToolTip("گواهی‌های تولید")
        self.card_certificates.mouseReleaseEvent = lambda e: self._on_nav_click("certificates")

        self.card_debts.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card_debts.setToolTip("صفحه تسویه بدهی‌ها")
        self.card_debts.mouseReleaseEvent = lambda e: self._on_nav_click("debts")

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

        expiry_label = QLabel("گواهی‌های نزدیک به انقضا (۳۰ روز و کمتر):")
        expiry_label.setStyleSheet("font-weight: bold; color: #B91C1C; font-size: 12px;")
        alerts_layout.addWidget(expiry_label)

        self.expiry_list = QListWidget()
        alerts_layout.addWidget(self.expiry_list)

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

        set_table_empty_state(
            self.today_table, not today_records,
            title="امروز خروجی ثبت نشده",
            subtitle="با دکمه «ثبت مجوز جدید» یا F2 اولین مجوز امروز را ثبت کنید"
        )

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
            item = QListWidgetItem(
                f"  🔴 {rec['name']} — بدهی: {format_thousands(rec['debt_amount'])} {rec['unit']}"
            )
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
            # پیش‌بینی اتمام بر اساس میانگین مصرف ماهانه
            forecast = forecast_certificate_exhaustion(dict(rec))
            forecast_part = f" — {forecast['message']}" if forecast.get("message") else ""
            item = QListWidgetItem(
                f"  🟡 {rec['name']} — باقیمانده: {rec['remaining_amount']} {rec['unit']} "
                f"({rec['product_type']}){forecast_part}"
            )
            item.setForeground(QColor("#D97706"))
            self.warn_list.addItem(item)

        # گواهی‌های نزدیک به انقضا (۳۰ روز) + منقض‌شده‌ها
        self.expiry_list.clear()
        for cert in get_expiring_certificates(days=30):
            days = cert["days_to_expiry"]
            if days < 0:
                text = f"  ⛔ {cert['company_name']} — گواهی «{cert['certificate_number']}» منقض شده ({abs(days)} روز پیش)"
            else:
                text = f"  ⏳ {cert['company_name']} — گواهی «{cert['certificate_number']}» تا {days} روز دیگر منقض می‌شود"
            item = QListWidgetItem(text)
            item.setForeground(QColor("#B91C1C"))
            self.expiry_list.addItem(item)

    def _on_nav_click(self, key):
        titles = {
            "dashboard": "داشبورد",
            "companies": "مدیریت شرکت‌ها",
            "certificates": "گواهی‌های تولید",
            "new_permit": "ثبت مجوز خروج",
            "search": "جستجو و گزارش",
            "charts": "نمودارها",
            "reports": "گزارش‌های رسمی",
            "settings": "تنظیمات",
            "debts": "تسویه بدهی‌ها",
        }
        pages = {
            "dashboard": 0,
            "companies": 1,
            "certificates": 2,
            "new_permit": 3,
            "search": 4,
            "charts": 8,
            "reports": 5,
            "settings": 6,
            "debts": 7,
        }

        self._set_active_nav(key)
        self._current_nav = key

        self.page_title.setText(titles[key])
        self.stack.setCurrentIndex(pages[key])
        fade_in(self.stack.currentWidget())

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
        elif key == "debts":
            self.debt_page.refresh_page()
        elif key == "charts":
            self.charts_page.refresh_page()

    def maybe_auto_backup(self):
        """پشتیبان‌گیری خودکار روزانه + پشتیبان دوم هفتگی هنگام باز شدن برنامه"""
        try:
            path = auto_backup_if_needed()
            if path:
                self.statusBar().showMessage(
                    f"  💾 پشتیبان‌گیری خودکار انجام شد: {path}", 10000
                )
            # پشتیبان دوم هفتگی به مسیر خارجی (فلش/شبکه/درایو دیگر) —
            # محافظت در برابر خرابی دیسک؛ اگر مسیر در دسترس نباشد فقط لاگ می‌شود
            from services.backup import run_secondary_backup_if_needed
            status, sec_path = run_secondary_backup_if_needed()
            if status == "created":
                self.statusBar().showMessage(
                    f"  🛡 پشتیبان دوم (هفتگی) کپی شد: {sec_path}", 10000
                )
        except Exception as e:
            # بکاپ هرگز نباید باز شدن برنامه را مختل کند
            print(f"[پشتیبان خودکار] خطا: {e}")

    def _go_dashboard(self):
        self._on_nav_click("dashboard")

    def _open_duplicate_permit(self, permit_id):
        """«ثبت مشابه»: فرم ثبت جدید با الگوی مجوز قبلی"""
        self._set_active_nav("new_permit")
        self.page_title.setText("ثبت مشابه مجوز خروج")
        self.stack.setCurrentIndex(3)
        self.permit_page.load_for_duplicate(permit_id)

    def _open_edit_permit(self, permit_id):
        """ورود به صفحه ثبت در حالت ویرایش مجوز"""
        # توجه: _set_active_nav فقط استایل دکمه‌ها را عوض می‌کند؛
        # عنوان صفحه مستقیماً همین‌جا تنظیم می‌شود
        self._set_active_nav("new_permit")
        self.page_title.setText("ویرایش مجوز خروج")
        self.stack.setCurrentIndex(3)
        self.permit_page.load_for_edit(permit_id)
