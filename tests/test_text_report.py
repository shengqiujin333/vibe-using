import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from vibe_using.cli import main
from vibe_using.database import InventoryDB
from vibe_using.models import Node, ScanResult, WindowInfo
from vibe_using.text_report import default_report_path, format_text_report


class TextReportTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "db.sqlite3"
        self.db = InventoryDB(self.db_path)
        self.result = ScanResult(
            pid=42, title="测试窗口\n坏行", windows=[WindowInfo(12, 42, "测试窗口")],
            nodes=[
                Node(1, None, 12, 0, "WindowControl", "主窗口"),
                Node(2, 1, 12, 1, "MenuItemControl", "文件", access_key="Alt+F", action_candidate=True),
                Node(3, 2, 12, 2, "ButtonControl", "导出", automation_id="export", accelerator_key="Ctrl+E", action_candidate=True),
            ],
            errors=["部分面板无法访问"], truncated=True,
        )

    def test_tree_and_metadata(self):
        text = format_text_report(self.result)
        self.assertIn("软件窗口: 测试窗口 坏行", text)
        self.assertIn("- #1 [WindowControl] 主窗口", text)
        self.assertIn("    - #2 [MenuItemControl] 文件", text)
        self.assertIn("      - #3 [ButtonControl] 导出", text)
        self.assertIn("快捷键=Ctrl+E", text)
        self.assertIn("AutomationId=export", text)
        self.assertIn("扫描是否截断: 是", text)
        self.assertIn("部分面板无法访问", text)

    def test_file_has_chinese_readable_utf8_bom(self):
        scan_id = self.db.save(self.result)
        path = self.db.export_txt(scan_id, Path(self.tempdir.name) / "result.txt")
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertIn("导出", path.read_text(encoding="utf-8-sig"))
        self.assertIn("扫描编号: 1", path.read_text(encoding="utf-8-sig"))

    def test_cli_exports_txt_without_windows(self):
        self.db.save(self.result)
        output = Path(self.tempdir.name) / "manual.txt"
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = main(["--db", str(self.db_path), "--export-txt", "1", "--output", str(output)])
        self.assertEqual(exit_code, 0)
        self.assertTrue(output.exists())
        self.assertIn(str(output), stdout.getvalue())

    def test_missing_window_and_empty_controls(self):
        text = format_text_report({"title": "", "pid": 55, "windows": [{"hwnd": 5, "pid": 55, "title": "Win"}], "nodes": []})
        self.assertIn("(没有读取到 UIA 控件)", text)

    def test_default_path_in_provided_folder(self):
        folder = Path(self.tempdir.name) / "reports"
        self.assertEqual(default_report_path(3, 45, folder), folder / "scan-3-pid-45.txt")


if __name__ == "__main__":
    unittest.main()
