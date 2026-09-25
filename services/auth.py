"""
رمز ورود اختیاری برنامه — ذخیره‌ی امن در تنظیمات

طرح:
- رمز هرگز به‌صورت خام ذخیره نمی‌شود؛ هش PBKDF2-HMAC-SHA256 با salt تصادفی
  (در قالب «pbkdf2_sha256$iterations$salt_hex$hash_hex» در settings می‌نشیند).
- اگر کلید password_hash خالی/ناموجود باشد، برنامه بدون رمز باز می‌شود
  (رمز اختیاری است — فعال‌سازی فقط از تنظیمات).
- مقایسه با compare_digest تا زمان‌گیری (timing attack) ممکن نباشد.
"""
import hashlib
import hmac
import secrets

from database.db_manager import db

# پارامترهای PBKDF2 (OWASP 2023 حداقل 600k برای SHA-256 — ولی برای شروع سریع
# برنامه‌ی دسکتاپِ تک‌کاربره، 200k تعادل خوبی بین امنیت و تأخیر <۰.۲ ثانیه است)
PBKDF2_ITERATIONS = 200_000

KEY = "password_hash"


def _hash_password(password, salt_hex=None, iterations=PBKDF2_ITERATIONS):
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return (
        f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"
    )


def is_password_set():
    """آیا رمز ورود فعالی ثبت شده است؟"""
    rec = db.fetch_one("SELECT value FROM settings WHERE key=?", (KEY,))
    return bool(rec and rec["value"] and rec["value"].startswith("pbkdf2_sha256$"))


def verify_password(password):
    """بررسی رمز ورودی با هش ذخیره‌شده — خروجی: درست/غلط"""
    rec = db.fetch_one("SELECT value FROM settings WHERE key=?", (KEY,))
    if not rec or not rec["value"]:
        return True  # رمزی ثبت نشده → همیشه مجاز
    try:
        algo, iterations, salt_hex, hash_hex = rec["value"].split("$")
        if algo != "pbkdf2_sha256":
            return False
        expected = _hash_password(password, salt_hex, int(iterations))
        expected_hash = expected.split("$")[3]
        return hmac.compare_digest(expected_hash, hash_hex)
    except (ValueError, TypeError):
        return False


def set_password(password):
    """ثبت/تغییر رمز — رمز خام ذخیره نمی‌شود"""
    if not password or not password.strip():
        raise ValueError("رمز خالی است")
    db.execute(
        """INSERT INTO settings (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (KEY, _hash_password(password.strip()))
    )


def clear_password():
    """حذف رمز — برنامه بدون رمز باز می‌شود"""
    db.execute("DELETE FROM settings WHERE key=?", (KEY,))
