"""
مدیریت اتصال و عملیات پایگاه داده
"""
import sqlite3
from contextlib import contextmanager
from config import DB_PATH, ensure_directories


class DatabaseManager:
    def __init__(self, db_path=None):
        ensure_directories()
        self.db_path = str(db_path) if db_path else str(DB_PATH)
        self._create_tables()

    def get_connection(self):
        """ایجاد اتصال به دیتابیس"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def transaction(self):
        """
        تراکنش اتمیک: همه‌ی عملیات یا با هم commit می‌شوند یا با هم rollback.
        اتصال همیشه بسته می‌شود.

        مثال:
            with db.transaction() as tx:
                permit_id = tx.insert("INSERT INTO ...", (...))
                tx.execute("INSERT INTO exit_items ...", (...))
        """
        conn = self.get_connection()
        try:
            with conn:  # commit در صورت موفقیت / rollback در صورت خطا
                yield _Transaction(conn)
        finally:
            conn.close()

    def _create_tables(self):
        """ساخت تمام جداول در صورت عدم وجود"""
        with self.transaction() as tx:
            cursor = tx.conn.cursor()

            # ─── جدول شرکت‌ها ───
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    economic_code TEXT,
                    phone TEXT,
                    ceo_name TEXT,
                    representative_name TEXT,
                    has_certificate BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                )
            """)

            # ─── جدول واحدها ───
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
            """)

            # ─── جدول گواهی‌های تولید ───
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS certificates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_id INTEGER NOT NULL,
                    certificate_number TEXT NOT NULL,
                    product_type TEXT NOT NULL,
                    total_amount REAL NOT NULL,
                    remaining_amount REAL NOT NULL,
                    unit_id INTEGER NOT NULL,
                    issue_date TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (company_id) REFERENCES companies(id),
                    FOREIGN KEY (unit_id) REFERENCES units(id)
                )
            """)

            # ─── جدول مجوزهای خروج ───
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS exit_permits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    permit_number TEXT NOT NULL UNIQUE,
                    company_id INTEGER NOT NULL,
                    exit_date TEXT NOT NULL,
                    destination TEXT,
                    customs_representative TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (company_id) REFERENCES companies(id)
                )
            """)

            # ─── جدول کالاهای هر مجوز ───
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS exit_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exit_permit_id INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    unit_id INTEGER NOT NULL,
                    certificate_id INTEGER,
                    is_debt BOOLEAN DEFAULT 0,
                    debt_settled BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (exit_permit_id) REFERENCES exit_permits(id),
                    FOREIGN KEY (unit_id) REFERENCES units(id),
                    FOREIGN KEY (certificate_id) REFERENCES certificates(id)
                )
            """)

            # ─── جدول اسکن‌ها ───
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scanned_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    exit_permit_id INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    page_number INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (exit_permit_id) REFERENCES exit_permits(id)
                )
            """)

            # ─── جدول تنظیمات ───
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT
                )
            """)

            # ─── جدول تاریخچه پشتیبان‌ها ───
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_path TEXT,
                    created_at TEXT,
                    status TEXT DEFAULT 'success'
                )
            """)

    # ─── عملیات عمومی CRUD ───

    def execute(self, query, params=()):
        """اجرای کوئری (INSERT/UPDATE/DELETE) و برگرداندن ID"""
        with self.transaction() as tx:
            return tx.execute(query, params)

    def fetch_one(self, query, params=()):
        """گرفتن یک رکورد"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()
        finally:
            conn.close()

    def fetch_all(self, query, params=()):
        """گرفتن همه‌ی رکوردها"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()


class _Transaction:
    """نمای اتمیک روی اتصال بازِ تراکنش"""

    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=()):
        """اجرای کوئری داخل تراکنش و برگرداندن ID"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.lastrowid

    def insert(self, query, params=()):
        """alias برای خوانایی کد هنگام INSERT"""
        return self.execute(query, params)

    def fetch_one(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()

    def fetch_all(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


# نمونه‌ی سراسری
db = DatabaseManager()
