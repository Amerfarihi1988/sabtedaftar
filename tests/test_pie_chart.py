"""
تست درصدهای نمودار دایره‌ای «سهم شرکت‌ها» — اجرا: python tests/test_pie_chart.py
بازتولید باگ اسکرین‌شات: دو شرکت ۲۰۰ و ۱۰۰ تن → برچسب‌ها باید ۶۷٪ و ۳۳٪ باشند،
نه ۱۰۰٪ و ۳۳٪ (باگ خواندن slice_.percentage() در لحظه‌ی append).
دیتابیس موقت؛ دیتابیس واقعی دست نمی‌خورد.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

tmp = tempfile.mkdtemp()

# ── پچ config پیش از ایمپورت ماژول‌های دیتابیس ──
import config  # noqa: E402
config.DB_PATH = Path(tmp) / "test.db"
config.BACKUP_DIR = Path(tmp) / "backups"
config.ensure_directories()

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402

app = QApplication(sys.argv)
app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

try:
    from PyQt6.QtCharts import QPieSeries  # noqa: E402
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

from database.db_manager import db  # noqa: E402  (singleton: ساخت جداول)

failures = []


def check(label, cond, detail=""):
    mark = "✓" if cond else "✗"
    print(f"{mark} {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(label)


# ═══ داده‌ی آزمون: جهان آرا ۲۰۰، کاوه ۱۰۰ ═══
# بدون seed: یک واحد آزمونی می‌سازیم (این تست مستقل از seed است)
unit_id = db.execute("INSERT INTO units (name) VALUES (?)", ("تن آزمون",))

c1 = db.execute("INSERT INTO companies (name, has_certificate) VALUES (?, 0)",
                ("جهان آرا",))
c2 = db.execute("INSERT INTO companies (name, has_certificate) VALUES (?, 0)",
                ("کاوه",))

for company_id, amount in [(c1, 200.0), (c2, 100.0)]:
    permit_id = db.execute(
        """INSERT INTO exit_permits (permit_number, company_id, exit_date)
           VALUES (?, ?, ?)""",
        (f"1405/9{company_id:02d}", company_id, "1405/07/01"),
    )
    db.execute(
        """INSERT INTO exit_items (exit_permit_id, product_name, amount, unit_id)
           VALUES (?, ?, ?, ?)""",
        (permit_id, "کالای آزمون", amount, unit_id),
    )

# ═══ رسم نمودار دایره‌ای همان‌طور که برنامه انجام می‌دهد ═══
from ui.charts_window import ChartsWindow  # noqa: E402

w = ChartsWindow()
w._render_pie()
app.processEvents()

series = w.pie_view.chart().series()[0]

check("تعداد برش‌ها = ۲", series.count() == 2, f"count={series.count()}")

labels = {}
for i in range(series.count()):
    sl = series.slices()[i]
    labels[sl.label().split(" — ")[0]] = sl.label()

# جمع درصدها باید ۱۰۰ شود (باگ قبلی: ۱۰۰ + ۳۳ = ۱۳۳)
pcts = [float(sl.label().split(" — ")[1].rstrip("%")) for sl in series.slices()]
check("جمع درصدها = ۱۰۰", abs(sum(pcts) - 100.0) < 0.5, f"{pcts} → sum={sum(pcts):.1f}")

# برش بزرگ‌تر (جهان آرا، ۲۰۰ از ۳۰۰) باید ۶۷٪ باشد نه ۱۰۰٪
p_jahan = float(labels["جهان آرا"].split(" — ")[1].rstrip("%"))
check("جهان آرا ≈ ۶۷٪", abs(p_jahan - 66.7) < 1.0, f"{p_jahan:.1f}%")

# برش کوچک‌تر (کاوه، ۱۰۰ از ۳۰۰) باید ۳۳٪ بماند
p_kaveh = float(labels["کاوه"].split(" — ")[1].rstrip("%"))
check("کاوه ≈ ۳۳٪", abs(p_kaveh - 33.3) < 1.0, f"{p_kaveh:.1f}%")

# هندسه‌ی دایره هم باید با درصدها هم‌خوان باشد
check("هندسه: سهم جهان آرا ≈ ۲/۳",
      abs(max(sl.percentage() for sl in series.slices()) - 2 / 3) < 0.01)

# ═══ سناریوی جمع-۹۹: سه شرکت مساوی → برچسب‌ها باید ۳۴/۳۳/۳۳ شوند (جمع = ۱۰۰) ═══
# با گرد کردن معمولی، ۳۳٫۳۳٪ سه بار به ۳۳ گرد می‌شود و جمع ۹۹ چاپ می‌شد
for name in ["مساوی یک", "مساوی دو", "مساوی سه"]:
    cid = db.execute("INSERT INTO companies (name, has_certificate) VALUES (?, 0)", (name,))
    pid = db.execute(
        "INSERT INTO exit_permits (permit_number, company_id, exit_date) VALUES (?, ?, ?)",
        (f"1405/8{cid:02d}", cid, "1405/07/05"),
    )
    db.execute(
        "INSERT INTO exit_items (exit_permit_id, product_name, amount, unit_id) VALUES (?, 'ک', 100.0, ?)",
        (pid, unit_id),
    )

w.f_date_from.setText("1405/07/05")
w.f_date_to.setText("1405/07/05")
w._render_pie()
app.processEvents()

sers3 = w.pie_view.chart().series()[0]
labels3 = [s.label() for s in sers3.slices()]
pcts3 = [float(s.label().split(" — ")[1].rstrip("%")) for s in sers3.slices()]
check("سه‌شرکت-مساوی: جمع برچسب‌ها = ۱۰۰", sum(pcts3) == 100,
      f"{labels3} → sum={sum(pcts3)}")
check("سه‌شرکت-مساوی: ۳۴/۳۳/۳۳", sorted(pcts3, reverse=True) == [34.0, 33.0, 33.0],
      f"{sorted(pcts3, reverse=True)}")

# ═══ سناریوی مرزی: همه‌ی مقادیر صفر → نباید کرش کند ═══
db.execute("INSERT INTO companies (name, has_certificate) VALUES (?, 0)",
           ("صفرِ آزمون",))
c3 = db.fetch_one("SELECT id FROM companies WHERE name='صفرِ آزمون'")["id"]
permit_id = db.execute(
    "INSERT INTO exit_permits (permit_number, company_id, exit_date) VALUES (?, ?, ?)",
    ("1405/990", c3, "1405/07/02"),
)
unit_id2 = db.fetch_one("SELECT id FROM units WHERE name='تن آزمون'")["id"]
db.execute(
    "INSERT INTO exit_items (exit_permit_id, product_name, amount, unit_id) VALUES (?, ?, 0, ?)",
    (permit_id, "کالای صفر", unit_id2),
)
# صفرِ آزمون فقط ردیف صفر دارد و جهان آرا/کاوه هم دارند → grand_total > 0، عادی رسم می‌شود.
# حالت real-edge: بازه‌ای که فقط ردیف صفر دارد → نمودار خالی پیام‌دار (نه کرش)
w.f_date_from.setText("1404/01/01")
w.f_date_to.setText("1404/12/29")
w._render_pie()
app.processEvents()
check("بازه‌ی بی‌داده → نمودار پیام‌دار (بدون کرش)", w.pie_view.chart() is not None)

print()
if failures:
    print(f"FAIL: {len(failures)} case(s): {failures}")
    sys.exit(1)
print("ALL OK — درصدهای نمودار دایره‌ای درست است")
