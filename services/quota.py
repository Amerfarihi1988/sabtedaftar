"""
کنترل سهمیه و مدیریت بدهی گواهی تولید
"""
import math

from database.db_manager import db
from config import QUOTA_WARNING_THRESHOLD


def is_low_quota(total_amount, remaining_amount):
    """
    مرجع واحد تشخیص «گواهی رو به اتمام».
    QUOTA_WARNING_THRESHOLD = نسبت مصرف هشدار (0.9 یعنی از ۹۰٪ مصرف به بعد).
    در مرز دقیق (مثلاً باقیمانده دقیقاً ۱۰٪ کل) به‌خاطر خطای اعشار شناور،
    با math.isclose هشدار محسوب می‌شود.
    """
    try:
        boundary = total_amount * (1 - QUOTA_WARNING_THRESHOLD)
        return remaining_amount < boundary or math.isclose(
            remaining_amount, boundary, rel_tol=1e-9
        )
    except TypeError:
        return False


def get_active_certificate(company_id):
    """گواهی فعال شرکت"""
    row = db.fetch_one(
        """SELECT * FROM certificates
           WHERE company_id=? AND status='active'
           ORDER BY created_at DESC""",
        (company_id,)
    )
    return dict(row) if row else None


def get_certificate_info(company_id):
    """اطلاعات گواهی برای نمایش در فرم ثبت"""
    company = db.fetch_one("SELECT * FROM companies WHERE id=?", (company_id,))
    if not company or not company["has_certificate"]:
        return {"needs_certificate": False, "has_active": False}

    cert = get_active_certificate(company_id)
    if not cert:
        return {
            "needs_certificate": True,
            "has_active": False,
            "company_name": company["name"]
        }

    unit = db.fetch_one("SELECT name FROM units WHERE id=?", (cert["unit_id"],))
    return {
        "needs_certificate": True,
        "has_active": True,
        "certificate_id": cert["id"],
        "product_type": cert["product_type"],
        "total_amount": cert["total_amount"],
        "remaining_amount": cert["remaining_amount"],
        "unit_name": unit["name"] if unit else "",
        "unit_id": cert["unit_id"],
        "is_warning": is_low_quota(cert["total_amount"], cert["remaining_amount"]),
    }


def preview_deduction(company_id, items):
    """
    پیش‌نمایش کسر سهمیه برای تأیید کاربر (بدون انجام کسر).
    اگر کسری در کار باشد، اطلاعات آن را برمی‌گرداند، وگرنه None.
    """
    company = db.fetch_one("SELECT * FROM companies WHERE id=?", (company_id,))
    if not company or not company["has_certificate"]:
        return None

    cert = get_active_certificate(company_id)
    if not cert:
        return None

    unit = db.fetch_one("SELECT name FROM units WHERE id=?", (cert["unit_id"],))
    unit_name = unit["name"] if unit else ""

    total = sum(i["amount"] for i in items if i["unit_id"] == cert["unit_id"])
    if total <= 0:
        return None

    return {
        "certificate_number": cert["certificate_number"],
        "product_type": cert["product_type"],
        "unit_name": unit_name,
        "total_deduction": total,
        "remaining_before": cert["remaining_amount"],
        "remaining_after": cert["remaining_amount"] - total,
        "is_over": total > cert["remaining_amount"],
    }


def plan_quota_items(company_id, items):
    """
    برنامه‌ریزی کسر سهمیه — کاملاً بدون اثر جانبی (فقط خواندن).

    خروجی: (processed, warnings)
    processed: لیست دیکشنری‌های {product_name, amount, unit_id,
               certificate_id, is_debt, certificate_remaining_after}
               که با data items هم‌اندیس است.
    """
    company = db.fetch_one("SELECT * FROM companies WHERE id=?", (company_id,))
    needs_certificate = bool(company and company["has_certificate"])
    cert = get_active_certificate(company_id) if needs_certificate else None

    warnings = []
    processed = []

    for item in items:
        cert_id = None
        is_debt = False

        if needs_certificate:
            if cert and cert["unit_id"] == item["unit_id"]:
                cert_id = cert["id"]
                if cert["remaining_amount"] >= item["amount"]:
                    new_remaining = cert["remaining_amount"] - item["amount"]
                    if is_low_quota(cert["total_amount"], new_remaining):
                        warnings.append(
                            f"🟡 سهمیه رو به اتمام: {new_remaining} باقیمانده"
                        )
                    cert["remaining_amount"] = new_remaining  # فقط در حافظه
                else:
                    # سهمیه ناکافی → بدهی
                    is_debt = True
                    warnings.append(
                        f"🔴 کالای «{item['product_name']}» به مقدار {item['amount']} "
                        f"ثبت شد ولی سهمیه کافی نیست (بدهی)"
                    )
            elif not cert:
                # شرکت گواهی‌دار ولی گواهی فعالی ندارد
                is_debt = True
                warnings.append(
                    f"🔴 شرکت گواهی‌دار است ولی گواهی فعالی ندارد. "
                    f"خروج «{item['product_name']}» به‌عنوان بدهی ثبت شد."
                )

        processed.append({
            "product_name": item["product_name"],
            "amount": item["amount"],
            "unit_id": item["unit_id"],
            "certificate_id": cert_id,
            "is_debt": is_debt,
        })

    return processed, warnings


def apply_quota_plan(tx, processed):
    """
    اعمال برنامه‌ی کسر سهمیه داخل تراکنشِ باز.
    tx: آبجکت _Transaction از db.transaction()
    """
    for proc in processed:
        if proc["certificate_id"] is None or proc["is_debt"]:
            continue
        row = tx.fetch_one(
            "SELECT remaining_amount, total_amount FROM certificates WHERE id=?",
            (proc["certificate_id"],)
        )
        if not row:
            continue
        new_remaining = row["remaining_amount"] - proc["amount"]
        status = 'active' if new_remaining > 0 else 'exhausted'
        tx.execute(
            "UPDATE certificates SET remaining_amount=?, status=? WHERE id=?",
            (new_remaining, status, proc["certificate_id"])
        )


def restore_permit_quota_tx(tx, permit_id):
    """
    بازگردانی سهمیه‌ی گواهی‌ها داخل تراکنشِ باز (حذف/ویرایش مجوز).
    برای هر کالای متصل به گواهی، مقدار به باقیمانده‌ی همان گواهی اضافه می‌شود.
    گواهی‌های بایگانی‌شده دست‌نخورده می‌مانند.
    """
    items = tx.fetch_all(
        """SELECT certificate_id, amount FROM exit_items
           WHERE exit_permit_id=? AND certificate_id IS NOT NULL""",
        (permit_id,)
    )
    for it in items:
        cert = tx.fetch_one(
            "SELECT * FROM certificates WHERE id=?",
            (it["certificate_id"],)
        )
        if not cert or cert["status"] == 'archived':
            continue
        new_remaining = cert["remaining_amount"] + it["amount"]
        status = 'active' if new_remaining > 0 else 'exhausted'
        tx.execute(
            "UPDATE certificates SET remaining_amount=?, status=? WHERE id=?",
            (new_remaining, status, cert["id"])
        )


def restore_permit_quota(permit_id):
    """بازگردانی سهمیه در تراکنش مستقل (برای سازگاری با فراخواننده‌های فعلی)"""
    with db.transaction() as tx:
        restore_permit_quota_tx(tx, permit_id)


def process_items(company_id, items):
    """
    سازگاری با فراخواننده‌های قدیمی: برنامه‌ریزی بدون اثر جانبی.
    (اعمال واقعی باید با apply_quota_plan داخل تراکنش انجام شود.)
    """
    return plan_quota_items(company_id, items)
