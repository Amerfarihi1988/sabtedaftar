"""
تولید گزارش‌های PDF رسمی
"""
import html
import traceback
import jdatetime
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtGui import QTextDocument, QFont, QPageSize
from config import APP_NAME
from services.org_settings import get_org_title, get_org_logo_path


def _esc(value):
    """escape ورودی کاربر برای HTML گزارش"""
    return html.escape(str(value if value is not None else ""), quote=True)


def _render_pdf(html_content, filepath):
    """رندر HTML به PDF"""
    try:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(filepath)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        doc = QTextDocument()
        doc.setDefaultFont(QFont("Tahoma", 11))
        doc.setHtml(html_content)
        doc.print(printer)
        return True
    except Exception as e:
        print(f"[گزارش PDF] خطا: {e}")
        traceback.print_exc()
        return False


def _letterhead(subtitle):
    """سربرگ رسمی — عنوان سازمان و لوگوی ثبت‌شده در تنظیمات"""
    today = jdatetime.date.today().strftime("%Y/%m/%d")
    org_title = get_org_title() or APP_NAME

    # لوگو (اگر تنظیم و موجود باشد) به‌صورت data-URI جاسازی می‌شود
    logo_img = ""
    logo_path = get_org_logo_path()
    if logo_path:
        try:
            import base64
            import mimetypes
            mime = mimetypes.guess_type(logo_path)[0] or "image/png"
            with open(logo_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            logo_img = (
                f'<img src="data:{mime};base64,{b64}" width="70" '
                f'style="margin-bottom: 6px;">'
            )
        except Exception:
            logo_img = ""

    return f"""
    <div dir="rtl" style="text-align: center; margin-bottom: 20px;">
        {logo_img}
        <p dir="rtl" style="font-size: 15pt; font-weight: bold; margin-bottom: 2px;">{_esc(org_title)}</p>
        <p dir="rtl" style="font-size: 12pt; color: #444; margin-top: 0px;">{_esc(subtitle)}</p>
        <p dir="rtl" style="font-size: 10pt; color: #777; margin-top: 2px;">تاریخ تهیه گزارش: {today}</p>
        <hr>
    </div>
    """


def generate_period_report_pdf(filepath, date_from, date_to, company_name, records):
    """
    گزارش دوره‌ای خروج کالا.
    records: لیست دیکشنری با کلیدهای permit_number, exit_date, company_name,
             destination, customs_representative, items_text, debt_text
    """
    rows = ""
    for rec in records:
        debt = rec.get("debt_text") or "—"
        rows += (
            "<tr>"
            f"<td dir='rtl'>{_esc(rec['permit_number'])}</td>"
            f"<td dir='rtl'>{_esc(rec['exit_date'])}</td>"
            f"<td dir='rtl'>{_esc(rec['company_name'])}</td>"
            f"<td dir='rtl'>{_esc(rec.get('destination', ''))}</td>"
            f"<td dir='rtl'>{_esc(rec['customs_representative'])}</td>"
            f"<td dir='rtl'>{_esc(rec['items_text'])}</td>"
            f"<td dir='rtl'>{_esc(debt)}</td>"
            "</tr>"
        )

    company_line = _esc(company_name) if company_name else "همه شرکت‌ها"

    html = f"""
<html dir="rtl" lang="fa">
<head><meta charset="utf-8">
<style>
    body {{ font-family: 'Tahoma'; font-size: 10pt; direction: rtl; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
    th, td {{ border: 1px solid #333; padding: 5px; text-align: center; }}
    th {{ background-color: #EEE; }}
    .summary {{ margin-top: 20px; font-size: 11pt; }}
    .signature {{ margin-top: 60px; text-align: left; }}
</style>
</head>
<body>
    {_letterhead('گزارش دوره‌ای مجوزهای خروج کالا')}
    <p dir="rtl"><b>شرکت:</b> {company_line} &nbsp;&nbsp;|&nbsp;&nbsp; <b>از تاریخ:</b> {_esc(date_from)} &nbsp;&nbsp;|&nbsp;&nbsp; <b>تا تاریخ:</b> {_esc(date_to)}</p>
    <table dir="rtl">
        <tr>
            <th>شماره ثبت</th><th>تاریخ</th><th>شرکت</th><th>مقصد</th>
            <th>نماینده گمرک</th><th>کالاها</th><th>بدهی</th>
        </tr>
        {rows}
    </table>
    <div class="summary">
        <p dir="rtl"><b>تعداد کل مجوزها:</b> {len(records)}</p>
    </div>
    <div class="signature">
        <p>مهر و امضای مسئول</p>
    </div>
</body>
</html>
"""
    return _render_pdf(html, filepath)


def generate_certificate_report_pdf(filepath, cert, consumptions, unit_name):
    """
    ریز مصرف یک گواهی تولید.
    cert: دیکشنری اطلاعات گواهی
    consumptions: لیست دیکشنری با کلیدهای exit_date, permit_number,
                  product_name, amount, is_debt
    """
    rows = ""
    total_consumed = 0
    total_debt = 0
    for c in consumptions:
        total_consumed += c["amount"]
        if c["is_debt"]:
            total_debt += c["amount"]
        debt = "بدهی" if c["is_debt"] else "عادی"
        rows += (
            "<tr>"
            f"<td dir='rtl'>{_esc(c['exit_date'])}</td>"
            f"<td dir='rtl'>{_esc(c['permit_number'])}</td>"
            f"<td dir='rtl'>{_esc(c['product_name'])}</td>"
            f"<td dir='rtl'>{_esc(c['amount'])}</td>"
            f"<td dir='rtl'>{_esc(unit_name)}</td>"
            f"<td dir='rtl'>{_esc(debt)}</td>"
            "</tr>"
        )

    html = f"""
<html dir="rtl" lang="fa">
<head><meta charset="utf-8">
<style>
    body {{ font-family: 'Tahoma'; font-size: 11pt; direction: rtl; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 10pt; }}
    th, td {{ border: 1px solid #333; padding: 5px; text-align: center; }}
    th {{ background-color: #EEE; }}
    .info {{ line-height: 2.2; }}
    .summary {{ margin-top: 20px; font-size: 11pt; }}
    .signature {{ margin-top: 60px; text-align: left; }}
</style>
</head>
<body>
    {_letterhead('ریز مصرف گواهی تولید')}
    <div class="info" dir="rtl">
        <p dir="rtl"><b>شرکت:</b> {_esc(cert['company_name'])}</p>
        <p dir="rtl"><b>شماره گواهی:</b> {_esc(cert['certificate_number'])} &nbsp;&nbsp;|&nbsp;&nbsp; <b>نوع کالا:</b> {_esc(cert['product_type'])}</p>
        <p dir="rtl"><b>مقدار کل:</b> {_esc(cert['total_amount'])} {_esc(unit_name)} &nbsp;&nbsp;|&nbsp;&nbsp; <b>باقیمانده:</b> {_esc(cert['remaining_amount'])} {_esc(unit_name)}</p>
    </div>
    <table dir="rtl">
        <tr>
            <th>تاریخ خروج</th><th>شماره ثبت</th><th>نام کالا</th>
            <th>مقدار</th><th>واحد</th><th>وضعیت</th>
        </tr>
        {rows}
    </table>
    <div class="summary" dir="rtl">
        <p dir="rtl"><b>جمع مصرف ثبت‌شده:</b> {total_consumed} {_esc(unit_name)}</p>
        <p dir="rtl"><b>جمع بدهی‌ها:</b> {total_debt} {_esc(unit_name)}</p>
    </div>
    <div class="signature">
        <p>مهر و امضای مسئول</p>
    </div>
</body>
</html>
"""
    return _render_pdf(html, filepath)


def generate_daily_manifest_pdf(filepath, exit_date, records, totals):
    """
    مانیفست روزانه — کل خروج‌های یک روز در یک سند رسمی (برای ارائه به گمرک).

    records: [{permit_number, company_name, destination, items_text}]
    totals:  {permits: int, items: int, total_amount: float}
    """
    rows = ""
    for rec in records:
        rows += (
            "<tr>"
            f"<td dir='rtl'>{_esc(rec['permit_number'])}</td>"
            f"<td dir='rtl'>{_esc(rec['company_name'])}</td>"
            f"<td dir='rtl'>{_esc(rec.get('destination', ''))}</td>"
            f"<td dir='rtl'>{_esc(rec.get('items_text', ''))}</td>"
            "</tr>"
        )

    amt = totals.get("total_amount", 0)
    amt_str = f"{int(amt):,}" if amt == int(amt) else f"{amt:,.2f}"

    html = f"""
<html dir="rtl" lang="fa">
<head><meta charset="utf-8">
<style>
    body {{ font-family: 'Tahoma'; font-size: 10pt; direction: rtl; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
    th, td {{ border: 1px solid #333; padding: 5px; text-align: center; }}
    th {{ background-color: #EEE; }}
    .summary {{ margin-top: 20px; font-size: 11pt; }}
    .signature {{ margin-top: 60px; text-align: left; }}
</style>
</head>
<body>
    {_letterhead('مانیفست روزانه خروج کالا')}
    <p dir="rtl"><b>تاریخ:</b> {_esc(exit_date)}</p>
    <table dir="rtl">
        <tr>
            <th>شماره ثبت</th><th>شرکت</th><th>مقصد</th><th>کالاها</th>
        </tr>
        {rows or '<tr><td colspan="4">خروجی در این تاریخ ثبت نشده</td></tr>'}
    </table>
    <div class="summary" dir="rtl">
        <p dir="rtl"><b>تعداد مجوزها:</b> {totals.get('permits', 0)} &nbsp;|&nbsp;
           <b>تعداد ردیف کالا:</b> {totals.get('items', 0)} &nbsp;|&nbsp;
           <b>مجموع مقادیر:</b> {amt_str}</p>
    </div>
    <div class="signature">
        <p>مهر و امضای مسئول</p>
    </div>
</body>
</html>
"""
    return _render_pdf(html, filepath)


def generate_company_statement_pdf(filepath, company_name, records, certs, debts):
    """
    صورتحساب/گردش کامل یک شرکت — همه‌ی مجوزهای خروج، گواهی‌ها و بدهی‌ها در یک سند.

    records: [{permit_number, exit_date, destination, items_text, debt_text}]
    certs:   [{certificate_number, product_type, total_amount, remaining_amount,
               status, unit_name}]
    debts:   [{permit_number, exit_date, product_name, amount, unit_name,
               debt_settled}]
    """
    # ─── جدول مجوزها ───
    permit_rows = ""
    for rec in records:
        permit_rows += (
            "<tr>"
            f"<td dir='rtl'>{_esc(rec['permit_number'])}</td>"
            f"<td dir='rtl'>{_esc(rec['exit_date'])}</td>"
            f"<td dir='rtl'>{_esc(rec.get('destination', ''))}</td>"
            f"<td dir='rtl'>{_esc(rec['items_text'])}</td>"
            f"<td dir='rtl'>{_esc(rec.get('debt_text') or '—')}</td>"
            "</tr>"
        )

    # ─── جدول گواهی‌ها ───
    cert_rows = ""
    for c in certs:
        status_fa = {'active': 'فعال', 'exhausted': 'تمام‌شده', 'archived': 'بایگانی'}.get(
            c.get("status"), c.get("status", "")
        )
        rem = c["remaining_amount"]
        rem_str = f"{int(rem):,}" if rem == int(rem) else f"{rem:,.2f}"
        cert_rows += (
            "<tr>"
            f"<td dir='rtl'>{_esc(c['certificate_number'])}</td>"
            f"<td dir='rtl'>{_esc(c['product_type'])}</td>"
            f"<td dir='rtl'>{_esc(c['total_amount'])} {_esc(c['unit_name'])}</td>"
            f"<td dir='rtl'>{rem_str} {_esc(c['unit_name'])}</td>"
            f"<td dir='rtl'>{_esc(status_fa)}</td>"
            "</tr>"
        )

    # ─── جدول بدهی‌ها ───
    debt_rows = ""
    for d in debts:
        settled = "تسویه‌شده" if d["debt_settled"] else "تسویه‌نشده"
        color = "#2e7d32" if d["debt_settled"] else "#c62828"
        amt = d["amount"]
        amt_str = f"{int(amt):,}" if amt == int(amt) else f"{amt:,.2f}"
        debt_rows += (
            "<tr>"
            f"<td dir='rtl'>{_esc(d['permit_number'])}</td>"
            f"<td dir='rtl'>{_esc(d['exit_date'])}</td>"
            f"<td dir='rtl'>{_esc(d['product_name'])}</td>"
            f"<td dir='rtl'>{amt_str} {_esc(d['unit_name'])}</td>"
            f"<td dir='rtl' style='color: {color}; font-weight: bold;'>{_esc(settled)}</td>"
            "</tr>"
        )

    debt_total_open = sum(d["amount"] for d in debts if not d["debt_settled"])
    debt_total_str = (
        f"{int(debt_total_open):,}" if debt_total_open == int(debt_total_open)
        else f"{debt_total_open:,.2f}"
    )

    html = f"""
<html dir="rtl" lang="fa">
<head><meta charset="utf-8">
<style>
    body {{ font-family: 'Tahoma'; font-size: 10pt; direction: rtl; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 9pt; margin-bottom: 14px; }}
    th, td {{ border: 1px solid #333; padding: 5px; text-align: center; }}
    th {{ background-color: #EEE; }}
    h3 {{ margin: 12px 0 6px; }}
    .summary {{ margin-top: 10px; font-size: 11pt; }}
    .signature {{ margin-top: 50px; text-align: left; }}
</style>
</head>
<body>
    {_letterhead('صورتحساب و گردش کامل شرکت')}
    <p dir="rtl"><b>شرکت:</b> {_esc(company_name)}</p>

    <h3 dir="rtl">۱) گواهی‌های تولید</h3>
    <table dir="rtl">
        <tr><th>شماره گواهی</th><th>نوع کالا</th><th>مقدار کل</th><th>باقیمانده</th><th>وضعیت</th></tr>
        {cert_rows or '<tr><td colspan="5">گواهی‌ای ثبت نشده</td></tr>'}
    </table>

    <h3 dir="rtl">۲) مجوزهای خروج</h3>
    <table dir="rtl">
        <tr><th>شماره ثبت</th><th>تاریخ</th><th>مقصد</th><th>کالاها</th><th>بدهی</th></tr>
        {permit_rows or '<tr><td colspan="5">مجوزی ثبت نشده</td></tr>'}
    </table>

    <h3 dir="rtl">۳) بدهی‌ها</h3>
    <table dir="rtl">
        <tr><th>شماره ثبت</th><th>تاریخ</th><th>کالا</th><th>مقدار</th><th>وضعیت</th></tr>
        {debt_rows or '<tr><td colspan="5">بدهی‌ای ثبت نشده</td></tr>'}
    </table>

    <div class="summary" dir="rtl">
        <p dir="rtl"><b>جمع بدهی تسویه‌نشده:</b> {debt_total_str}</p>
        <p dir="rtl"><b>تعداد مجوزها:</b> {len(records)}</p>
    </div>
    <div class="signature">
        <p>مهر و امضای مسئول</p>
    </div>
</body>
</html>
"""
    return _render_pdf(html, filepath)