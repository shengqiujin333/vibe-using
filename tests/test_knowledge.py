import unittest

from vibe_using.knowledge import enrich_nodes
from vibe_using.models import Node, ScanResult, WindowInfo
from vibe_using.text_report import format_text_report


class KnowledgeTests(unittest.TestCase):
    def test_child_text_fallback_only_for_single_label(self):
        nodes = [
            Node(1, None, 12, 0, "PaneControl", name="主界面"),
            Node(2, 1, 12, 1, "ButtonControl", name=""),
            Node(3, 2, 12, 2, "TextControl", name="导出"),
            Node(4, 1, 12, 1, "GroupControl", name=""),
            Node(5, 4, 12, 2, "TextControl", name="标签甲"),
            Node(6, 4, 12, 2, "TextControl", name="标签乙"),
            Node(7, 1, 12, 1, "EditControl", name=""),
            Node(8, 7, 12, 2, "TextControl", name="private content"),
        ]
        enrich_nodes(nodes)
        self.assertEqual(nodes[1].name, "导出")
        self.assertEqual(nodes[1].name_source, "child_text")
        self.assertIn("主界面 > 导出", nodes[1].path)
        self.assertEqual(nodes[3].name, "")
        self.assertEqual(nodes[6].name, "")
        self.assertEqual(nodes[1].purpose_source, "name_guess_unverified")

    def test_operation_and_help_are_distinguished_from_guess(self):
        nodes = [Node(1, None, 23, 0, "ButtonControl", name="生成", help_text="生成目标文件", supported_patterns=["Invoke"], accelerator_key="Ctrl+G", action_candidate=True)]
        enrich_nodes(nodes)
        self.assertEqual(nodes[0].purpose, "生成目标文件")
        self.assertEqual(nodes[0].purpose_source, "uia_helptext_unverified")
        self.assertIn("UIA Invoke", nodes[0].operation)
        self.assertIn("Ctrl+G", nodes[0].operation)
        report = format_text_report(ScanResult(pid=8, title="App", windows=[WindowInfo(23, 8, "App")], nodes=nodes))
        self.assertIn("一、可识别的功能与菜单入口", report)
        self.assertIn("在哪里: 生成", report)
        self.assertIn("作用: 生成目标文件", report)
        self.assertIn("怎么操作: UIA Invoke", report)

    def test_menu_group_included_in_primary_list(self):
        nodes = [Node(1, None, 12, 0, "PaneControl", name="主窗口"), Node(2, 1, 12, 1, "GroupControl", name="文件")]
        enrich_nodes(nodes)
        report = format_text_report(ScanResult(pid=8, title="App", windows=[WindowInfo(12, 8, "App")], nodes=nodes))
        self.assertIn("#2 文件 [GroupControl]", report)
        self.assertIn("鼠标/键盘操作，待验证", report)
        self.assertIn("根据名称推测", report)

    def test_unknown_is_not_invented(self):
        nodes = [Node(1, None, 10, 0, "ButtonControl", name="自定义指令", action_candidate=True)]
        enrich_nodes(nodes)
        report = format_text_report(ScanResult(pid=5, title="App", windows=[WindowInfo(10, 5, "App")], nodes=nodes))
        self.assertIn("未知；不能仅凭控件类型确定功能", report)


if __name__ == "__main__":
    unittest.main()
