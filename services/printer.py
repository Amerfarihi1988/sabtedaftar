"""
چاپ روبرگه «خروج بلامانع»
"""
import html
import traceback
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtGui import QTextDocument, QFont, QPageSize
from PyQt6.QtWidgets import QMessageBox
from services.org_settings import get_org_title


def print_exit_permit(data, show_dialog=True):
    """چاپ روبرگه خروج بلامانع."""
    try:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        if show_dialog:
            try:
                from PyQt6.QtPrintSupport import QPrintDialog
                dialog = QPrintDialog(printer)
                dialog.setWindowTitle("چاپ روبرگه خروج بلامانع")
                if dialog.exec() != 1:
                    return False
            except Exception:
                pass

        doc = QTextDocument()
        doc.setDefaultFont(QFont("Tahoma", 11))
        html = _generate_html(data)
        # تنظیم متن به‌صورت HTML با پشتیبانی RTL
        doc.setHtml(html)
        # اطمینان از جهت RTL سند
        doc.setTextWidth(printer.pageRect(QPrinter.Unit.Point).width())
        doc.print(printer)
        return True

    except Exception as e:
        print(f"[چاپ] خطا: {e}")
        traceback.print_exc()
        return False


def print_to_pdf(data, filepath):
    """ذخیره‌ی روبرگه به‌صورت PDF"""
    try:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(filepath)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        doc = QTextDocument()
        doc.setDefaultFont(QFont("Tahoma", 11))
        doc.setHtml(_generate_html(data))
        doc.setTextWidth(printer.pageRect(QPrinter.Unit.Point).width())
        doc.print(printer)
        return True
    except Exception as e:
        print(f"[PDF] خطا: {e}")
        traceback.print_exc()
        return False


def _esc(value):
    """escape ورودی کاربر برای HTML — جلوگیری از به‌هم‌ریختن سند چاپی"""
    return html.escape(str(value if value is not None else ""), quote=True)


def _generate_html(data):
    rows = ""
    for i, item in enumerate(data.get("items", []), 1):
        rows += (
            f"<tr>"
            f"<td dir='rtl' align='center'>{i}</td>"
            f"<td dir='rtl' align='center'>{_esc(item['product_name'])}</td>"
            f"<td dir='rtl' align='center'>{_esc(item['amount'])}</td>"
            f"<td dir='rtl' align='center'>{_esc(item['unit_name'])}</td>"
            f"</tr>"
        )

    org_title = get_org_title() or ""
    org_line = (
        f'<p dir="rtl" style="font-size: 11pt; color: #555; margin-bottom: 2px;">{_esc(org_title)}</p>'
        if org_title else ""
    )

    return f"""
<html dir="rtl" lang="fa">
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: 'Tahoma', 'B Nazanin', 'Nazanin', sans-serif;
            font-size: 12pt;
            text-align: right;
            direction: rtl;
        }}
        .header {{
            text-align: center;
            margin-bottom: 25px;
        }}
        .header p {{
            text-align: center;
        }}
        .content {{
            margin: 25px 0;
            line-height: 2.5;
            text-align: right;
        }}
        .info {{
            margin: 15px 0;
            text-align: right;
        }}
        .info p {{
            text-align: right;
        }}
        .items {{
            margin: 20px 0;
            text-align: right;
        }}
        .items p {{
            text-align: right;
        }}
        .items table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11pt;
            direction: rtl;
        }}
        .items th, .items td {{
            border: 1px solid #333;
            padding: 6px;
            text-align: center;
        }}
        .signature {{
            margin-top: 60px;
            text-align: left;
        }}
    </style>
</head>
<body dir="rtl">
    <div class="header" dir="rtl">
        {org_line}
        <p dir="rtl">شماره ثبت: <b>{_esc(data['permit_number'])}</b></p>
        <p dir="rtl">تاریخ: <b>{_esc(data['exit_date'])}</b></p>
        <hr>
    </div>
    <div class="content" dir="rtl">
        <p dir="rtl">
            خروج کالا در متن نامه با تأیید نماینده گمرک آقا/خانم
            <b>{_esc(data['customs_representative'])}</b>
            بعد از بررسی عینی در مورخ <b>{_esc(data['exit_date'])}</b> بلامانع است.
        </p>
    </div>
    <div class="info" dir="rtl">
        <p dir="rtl">شرکت: <b>{_esc(data['company_name'])}</b></p>
        <p dir="rtl">مقصد: <b>{_esc(data.get('destination', ''))}</b></p>
    </div>
    <div class="items" dir="rtl">
        <p dir="rtl"><b>فهرست کالاها:</b></p>
        <table dir="rtl" align="center">
            <tr>
                <th dir="rtl" align="center">ردیف</th>
                <th dir="rtl" align="center">نام کالا</th>
                <th dir="rtl" align="center">مقدار</th>
                <th dir="rtl" align="center">واحد</th>
            </tr>
            {rows}
        </table>
    </div>
    <div class="signature">
        <p>مهر و امضای مسئول</p>
    </div>
</body>
</html>
"""