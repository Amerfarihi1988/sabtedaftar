"""تست اسکن بدون سخت‌افزار — اجرا: python tests/test_scanner.py"""
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.scanner import PNG_FORMAT, scan_document


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = str(Path(self.temp.name) / "letter.png")
        self.image = Mock(FormatID=PNG_FORMAT.lower())
        self.dialog = Mock()
        self.dialog.ShowAcquireImage.return_value = self.image
        self.create = Mock(return_value=self.dialog)
        client = ModuleType("comtypes.client")
        client.CreateObject = self.create
        comtypes = ModuleType("comtypes")
        comtypes.client = client
        self.modules = patch.dict(sys.modules, {
            "comtypes": comtypes, "comtypes.client": client,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_acquisition_shows_settings_instead_of_direct_transfer(self):
        self.assertEqual(scan_document(self.output), self.output)
        self.dialog.ShowAcquireImage.assert_called_once_with(
            1, 1, 131072, PNG_FORMAT, True, True, False
        )
        self.dialog.ShowSelectDevice.assert_not_called()
        self.dialog.ShowTransfer.assert_not_called()
        self.create.assert_called_once_with("WIA.CommonDialog")
        self.image.SaveFile.assert_called_once_with(self.output)

    def test_driver_format_is_converted_without_resize_or_crop(self):
        self.image.FormatID = "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}"
        processor = Mock()
        property_value = SimpleNamespace(Value=None)
        processor.FilterInfos.Item.return_value = SimpleNamespace(FilterID="convert")
        processor.Filters.Item.return_value.Properties.Item.return_value = property_value
        converted = Mock(FormatID=PNG_FORMAT)
        processor.Apply.return_value = converted
        self.create.side_effect = [self.dialog, processor]

        self.assertEqual(scan_document(self.output), self.output)
        self.assertEqual(self.create.call_args_list[1].args, ("WIA.ImageProcess",))
        processor.FilterInfos.Item.assert_called_once_with("Convert")
        processor.Filters.Add.assert_called_once_with("convert")
        processor.Filters.Item.assert_called_once_with(1)
        processor.Filters.Item.return_value.Properties.Item.assert_called_once_with("FormatID")
        self.assertEqual(property_value.Value, PNG_FORMAT)
        processor.Apply.assert_called_once_with(self.image)
        self.image.SaveFile.assert_not_called()
        converted.SaveFile.assert_called_once_with(self.output)

    def test_cancel_does_not_save(self):
        self.dialog.ShowAcquireImage.return_value = None
        self.assertIsNone(scan_document(self.output))
        self.image.SaveFile.assert_not_called()
        self.assertFalse(Path(self.output).exists())

    def test_acquisition_failure_returns_none(self):
        self.dialog.ShowAcquireImage.side_effect = RuntimeError("device offline")
        with patch("builtins.print") as log:
            self.assertIsNone(scan_document(self.output))
        self.image.SaveFile.assert_not_called()
        self.assertIn("device offline", log.call_args.args[0])

    def test_save_failure_does_not_report_success(self):
        self.image.SaveFile.side_effect = OSError("access denied")
        with patch("builtins.print"):
            self.assertIsNone(scan_document(self.output))

    def test_conversion_failure_does_not_save_wrong_format(self):
        self.image.FormatID = "BMP"
        processor = Mock()
        processor.Apply.side_effect = RuntimeError("conversion failed")
        self.create.side_effect = [self.dialog, processor]
        with patch("builtins.print"):
            self.assertIsNone(scan_document(self.output))
        self.image.SaveFile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
