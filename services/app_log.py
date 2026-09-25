"""
لاگ فایل سراسری برنامه — همه‌ی خطاها و رویدادهای مهم در data/app.log

- استانداردهای logging پایتون + هندلر فایل با چرخش (۵ فایل × ۲MB)
- hook سراسری برای خطاهای ناگرفته (sys.excepthook + threading excepthook)
- هدایت پیام‌های Qt (qInstallMessageHandler) به همین لاگ
- در EXE بدون کنسول، تنها راه دیدن خطاها همین فایل است
"""
import logging
import logging.handlers
import sys
import threading
import traceback
from pathlib import Path

from config import DB_PATH

_logger = None


def _log_path():
    return Path(DB_PATH).parent / "app.log"


def setup_logging():
    """راه‌اندازی لاگ سراسری — یک‌بار در ابتدای main() صدا زده می‌شود"""
    global _logger
    if _logger is not None:
        return _logger

    try:
        _log_path().parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            _log_path(), maxBytes=2 * 1024 * 1024, backupCount=5,
            encoding="utf-8"
        )
    except OSError:
        # اگر نوشتن فایل ممکن نبود، لاگ فقط به stdout می‌رود
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))

    logger = logging.getLogger("sabtedaftar")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    _logger = logger

    _install_excepthook(logger)
    _install_qt_message_handler(logger)
    return logger


def _install_excepthook(logger):
    """خطاهای ناگرفته‌ی thread اصلی و بقیه threadها به لاگ می‌روند"""
    def _hook(exc_type, exc_value, exc_tb):
        logger.critical(
            "خطای ناگرفته:\n" + "".join(traceback.format_exception(
                exc_type, exc_value, exc_tb
            ))
        )
        # رفتار پیش‌فرض (چاپ و خروج) حفظ می‌شود
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook

    def _thread_hook(args):
        logger.critical(
            f"خطای ناگرفته در thread {args.thread.name}:\n" +
            "".join(traceback.format_exception(
                args.exc_type, args.exc_value, args.exc_traceback
            ))
        )

    threading.excepthook = _thread_hook


def _install_qt_message_handler(logger):
    """پیام‌های هشدار/خطای Qt (از جمله signal/slot errors) به لاگ می‌روند"""
    try:
        from PyQt6.QtCore import qInstallMessageHandler, QtMsgType

        def _qt_handler(msg_type, context, message):
            level = {
                QtMsgType.QtDebugMsg: logging.DEBUG,
                QtMsgType.QtInfoMsg: logging.INFO,
                QtMsgType.QtWarningMsg: logging.WARNING,
                QtMsgType.QtCriticalMsg: logging.ERROR,
                QtMsgType.QtFatalMsg: logging.CRITICAL,
            }.get(msg_type, logging.INFO)
            logger.log(level, f"Qt: {message}")

        qInstallMessageHandler(_qt_handler)
    except Exception:
        pass


def log_path():
    """مسیر فایل لاگ برای نمایش در UI"""
    return _log_path()


def get_logger(name="sabtedaftar"):
    """دریافت لاگر برنامه (پس از setup_logging)"""
    return logging.getLogger(name)


def read_recent_lines(max_lines=500):
    """خواندن آخرین خطوط لاگ برای نمایش در دیالوگ تنظیمات"""
    try:
        if not _log_path().exists():
            return "لاگی ثبت نشده است."
        with open(_log_path(), "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return "".join(lines[-max_lines:])
    except OSError as e:
        return f"خواندن لاگ ممکن نشد: {e}"
