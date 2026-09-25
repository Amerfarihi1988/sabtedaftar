"""
ورودی مقدار با پشتیبانی اعداد فارسی

کاربر می‌تواند ۱۲٫۵ یا ۱۲.5 تایپ کند؛ در valueFromText به 12.5 نرمال
می‌شود. برخلاف override خطای validate، فقط valueFromText را عوض می‌کنیم
(override validate با c-api ارقام یونیکد در PySide6/PyQt6 کرش می‌کند).
"""
from PyQt6.QtWidgets import QDoubleSpinBox

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٫،", "0123456789..")


def normalize_fa_number(text):
    """تبدیل ارقام و جداکننده‌های فارسی به لاتین"""
    return text.translate(_FA_DIGITS)


class PersianAmountSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox که ارقام فارسی را می‌پذیرد و نرمال می‌کند"""

    def valueFromText(self, text):
        return super().valueFromText(normalize_fa_number(text))

    def textFromValue(self, value):
        # نمایش با ارقام لاتین برای سادگی ویرایش بعدی
        return super().textFromValue(value)
