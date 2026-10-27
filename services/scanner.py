"""
اسکن مستقیم از نرم‌افزار با WIA ویندوز
"""

PNG_FORMAT = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"


def scan_document(output_path):
    """
    اسکن سند با پنجره تنظیمات WIA و ذخیره تصویر PNG در مسیر مشخص‌شده.
    در صورت موفقیت مسیر فایل، در غیر این صورت None برمی‌گرداند.
    """
    try:
        from comtypes.client import CreateObject
        dialog = CreateObject("WIA.CommonDialog")
        # به‌جای انتقال مستقیمِ آیتم با محدوده برش قبلیِ درایور، پنجره
        # دریافت تصویر را باز می‌کنیم تا کاربر تنظیمات و محدوده صفحه را ببیند.
        # DeviceType=Scanner, Intent=Color, Bias=MaximizeQuality,
        # AlwaysSelectDevice=True, UseCommonUI=True, CancelError=False
        image = dialog.ShowAcquireImage(
            1, 1, 131072, PNG_FORMAT, True, True, False
        )
        if image is None:
            return None

        # بعضی درایورها فرمت درخواستی را نادیده می‌گیرند؛ پسوند PNG به‌تنهایی
        # فرمت تصویر را عوض نمی‌کند. تبدیل بدون تغییر اندازه یا برش انجام می‌شود.
        if image.FormatID.upper() != PNG_FORMAT.upper():
            processor = CreateObject("WIA.ImageProcess")
            processor.Filters.Add(processor.FilterInfos.Item("Convert").FilterID)
            processor.Filters.Item(1).Properties.Item("FormatID").Value = PNG_FORMAT
            image = processor.Apply(image)

        image.SaveFile(output_path)
        return output_path
    except Exception as e:
        print(f"[اسکنر] خطا: {e}")
    return None


def has_scanner():
    """بررسی موجود بودن اسکنر روی سیستم"""
    try:
        from comtypes.client import CreateObject
        manager = CreateObject("WIA.DeviceManager")
        for info in manager.DeviceInfos:
            if info.Type == 1:
                return True
    except:
        pass
    return False
