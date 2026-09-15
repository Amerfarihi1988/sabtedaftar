"""
تولید گزارش‌های PDF رسمی
"""
import html
import traceback
import jdatetime
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtGui import QTextDocument, QFont, QPageSize
from config import APP_NAME


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
    """سربرگ رسمی"""
    today = jdatetime.date.today().strftime("%Y/%m/%d")
    return f"""
    <div dir="rtl" style="text-align: center; margin-bottom: 20px;">
        <p dir="rtl" style="font-size: 15pt; font-weight: bold; margin-bottom: 2px;">{APP_NAME}</p>
        <p dir="rtl" style="font-size: 12pt; color: #444; margin-top: 0px;">{subtitle}</p>
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