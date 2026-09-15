"""
اسکن مستقیم از نرم‌افزار با WIA ویندوز
"""
import os


def scan_document(output_path):
    """
    اسکن سند با WIA و ذخیره در مسیر مشخص‌شده.
    در صورت موفقیت مسیر فایل، در غیر این صورت None برمی‌گرداند.
    """
    try:
        from comtypes.client import CreateObject
        dialog = CreateObject("WIA.CommonDialog")
        # انتخاب دستگاه (۱ = اسکنر)
        device = dialog.ShowSelectDevice(1, True, False)
        if device is None:
            return None
        item = device.Items.Item(1)
        # فرمت JPEG
        jpeg_format = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
        image = dialog.ShowTransfer(item, jpeg_format, False)
        if image:
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