"""
کنترل سهمیه و مدیریت بدهی گواهی تولید

شامل:
- تشخیص گواهی رو به اتمام (نسبی)
- پشتیبانی از تاریخ انقضای گواهی (شمسی) — گواهی منقض‌شده پذیرفته نمی‌شود
- پیش‌بینی اتمام گواهی بر اساس میانگین مصرف ماهانه
"""
import math

import jdatetime

from database.db_manager import db
from config import QUOTA_WARNING_THRESHOLD


def _parse_shamsi(text):
    """تبدیل رشته تاریخ شمسی «1405/03/15» به jdatetime.date — یا None"""
    if not text:
        return None
    try:
        parts = str(text).replace("-", "/").split("/")
        if len(parts) != 3:
            return None
        return jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError):
        return None


def cert_expiry_status(cert):
    """
    وضعیت انقضای یک گواهی (دیکشنری با expiry_date شمسی).
    خروجی: (منقض‌شده: bool, روز تا انقضا: int یا None)
    گواهی بدون تاریخ انقضا: (False, None) — انقضا ندارد.
    """
    exp = _parse_shamsi(cert.get("expiry_date")) if isinstance(cert, dict) else None
    if exp is None:
        return False, None
    today = jdatetime.date.today()
    days = (exp - today).days
    return days < 0, days


def is_cert_expired(cert):
    """آیا گواهی منقض شده است؟"""
    expired, _ = cert_expiry_status(cert)
    return expired


def is_expiring_soon(cert, days=30):
    """آیا گواهی تا «days» روز آینده منقض می‌شود؟"""
    expired, remaining = cert_expiry_status(cert)
    if expired or remaining is None:
        return False
    return remaining <= days


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
    """
    گواهی فعال شرکت — گواهی منقض‌شده پذیرفته نمی‌شود.
    اولویت: نزدیک‌ترین انقضا اول (تا قبل از مصرف گواهی با انقضای دور،
    گواهی در حال انقضا مصرف شود)؛ گواهی بدون انقضا آخر.
    مرتب‌سازی در پایتون انجام می‌شود تا فرمت‌های شمسی صفرنپر هم درست سورت شوند.
    """
    rows = db.fetch_all(
        """SELECT * FROM certificates
           WHERE company_id=? AND status='active'
           ORDER BY created_at DESC""",
        (company_id,)
    )
    candidates = [dict(r) for r in rows if not is_cert_expired(dict(r))]
    if not candidates:
        return None

    def expiry_key(cert):
        exp = _parse_shamsi(cert.get("expiry_date"))
        # بدون انقضا → آخر لیست؛ با انقضا → نزدیک‌ترین اول
        return (0, exp.toordinal()) if exp else (1, 0)

    candidates.sort(key=expiry_key)
    return candidates[0]


def get_certificate_info(company_id):
    """اطلاعات گواهی برای نمایش در فرم ثبت"""
    company = db.fetch_one("SELECT * FROM companies WHERE id=?", (company_id,))
    if not company or not company["has_certificate"]:
        return {"needs_certificate": False, "has_active": False}

    cert = get_active_certificate(company_id)
    if not cert:
        # آیا اصلاً گواهی فعالی هست که فقط منقض شده باشد؟ (پیام دقیق‌تر)
        any_active = db.fetch_one(
            "SELECT expiry_date FROM certificates WHERE company_id=? AND status='active' LIMIT 1",
            (company_id,)
        )
        info = {
            "needs_certificate": True,
            "has_active": False,
            "company_name": company["name"]
        }
        if any_active and any_active["expiry_date"]:
            info["all_expired"] = True
            info["expiry_date"] = any_active["expiry_date"]
        return info

    unit = db.fetch_one("SELECT name FROM units WHERE id=?", (cert["unit_id"],))
    expired, days_to_expiry = cert_expiry_status(cert)
    return {
        "needs_certificate": True,
        "has_active": True,
        "certificate_id": cert["id"],
        "product_type": cert["product_type"],
        "total_amount": cert["total_amount"],
        "remaining_amount": cert["remaining_amount"],
        "unit_name": unit["name"] if unit else "",
        "unit_id": cert["unit_id"],
        "expiry_date": cert.get("expiry_date"),
        "days_to_expiry": days_to_expiry,
        "is_expiring_soon": is_expiring_soon(cert),
        "is_warning": is_low_quota(cert["total_amount"], cert["remaining_amount"]),
    }


def forecast_certificate_exhaustion(cert, months=6):
    """
    پیش‌بینی اتمام گواهی بر اساس میانگین مصرف ماهانه (شمسی).

    خروجی دیکشنری:
      monthly_avg      — میانگین مصرف ماهانه (بدون احتساب بدهی‌ها؛ بدهی از سهمیه کسر نشده)
      months_left      — چند ماه مانده (float) یا None اگر مصرفی نیست
      exhaustion_date  — تاریخ شمسی تخمینی اتمام («1405/08») یا None
      message          — جمله‌ی آماده برای نمایش
    """
    rows = db.fetch_all(
        """SELECT ep.exit_date, SUM(ei.amount) as used
           FROM exit_items ei
           JOIN exit_permits ep ON ei.exit_permit_id = ep.id
           WHERE ei.certificate_id = ? AND ei.is_debt = 0
           GROUP BY ep.exit_date""",
        (cert["id"],)
    )
    if not rows:
        return {"monthly_avg": 0.0, "months_left": None,
                "exhaustion_date": None,
                "message": "مصرفی برای پیش‌بینی ثبت نشده است"}

    # گروه‌بندی بر اساس ماه شمسی «1405/07»
    monthly = {}
    for r in rows:
        month_key = str(r["exit_date"])[:7]
        monthly[month_key] = monthly.get(month_key, 0.0) + (r["used"] or 0)

    avg = sum(monthly.values()) / len(monthly)
    remaining = cert["remaining_amount"]
    if remaining <= 0:
        return {"monthly_avg": avg, "months_left": 0.0,
                "exhaustion_date": "الان",
                "message": "باقیمانده صفر است"}
    if avg <= 0:
        return {"monthly_avg": 0.0, "months_left": None,
                "exhaustion_date": None,
                "message": "مصرف ماهانه‌ای ثبت نشده"}

    months_left = remaining / avg

    # تاریخ تخمینی اتمام: از ماه جاری به بعد
    today = jdatetime.date.today()
    total_months = today.month + int(math.ceil(months_left))
    year = today.year + (total_months - 1) // 12
    month = (total_months - 1) % 12 + 1
    exhaustion_date = f"{year}/{month:02d}"

    if months_left < 1:
        msg = f"کمتر از یک ماه مانده (میانگین مصرف: {avg:g} در ماه)"
    elif months_left < 2:
        msg = f"حدود {months_left:.1f} ماه مانده"
    else:
        msg = f"حدود {int(round(months_left))} ماه مانده (تا {exhaustion_date})"

    return {"monthly_avg": avg, "months_left": months_left,
            "exhaustion_date": exhaustion_date, "message": msg}


def get_expiring_certificates(days=30):
    """گواهی‌های فعالِ نزدیک به انقضا (تا «days» روز آینده) برای هشدار داشبورد"""
    rows = db.fetch_all(
        """SELECT cert.*, c.name as company_name, u.name as unit_name
           FROM certificates cert
           JOIN companies c ON cert.company_id = c.id
           JOIN units u ON cert.unit_id = u.id
           WHERE cert.status = 'active' AND cert.expiry_date IS NOT NULL"""
    )
    result = []
    for row in rows:
        cert = dict(row)
        expired, remaining = cert_expiry_status(cert)
        if expired:
            result.append({**cert, "days_to_expiry": remaining})
        elif remaining is not None and remaining <= days:
            result.append({**cert, "days_to_expiry": remaining})
    # منقض‌شده‌ها اول (بحرانی‌تر)
    result.sort(key=lambda c: (c["days_to_expiry"] > 0, c["days_to_expiry"]))
    return result


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

    بدهیِ تسویه‌نشده بازگردانی نمی‌شود: گواهی هنگام ثبتِ بدهی چیزی کسر نکرده،
    پس برگرداندن مقدار، باقیمانده را تورم می‌داد. بدهیِ تسویه‌شده اما
    از گواهی پرداخت‌کننده کسر شده و با حذف/ویرایش مجوز باید به همان گواهی برگردد.
    """
    items = tx.fetch_all(
        """SELECT certificate_id, amount FROM exit_items
           WHERE exit_permit_id=? AND certificate_id IS NOT NULL
             AND (is_debt = 0 OR debt_settled = 1)""",
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
