"""Chromium-like zero-sized properties should not crowd primary GUI inventory."""
import unittest

from vibe_using.control_visibility import is_property_control, location_status, tree_visible_ids
from vibe_using.models import Node, ScanResult, WindowInfo
from vibe_using.text_report import format_text_report


class LocationTests(unittest.TestCase):
    def test_zero_rectangle_is_unlocatable_even_if_enabled_and_toggle(self):
        n = {"role": "CheckBoxControl", "name": "公司", "enabled": True,
             "rect": [0, 0, 0, 0], "offscreen": False, "supported_patterns": ["Toggle"]}
        self.assertEqual(location_status(n), "no_geometry")
        self.assertEqual(location_status({**n, "rect": [-900, 100, -800, 150]}), "located")
        self.assertEqual(location_status({**n, "rect": [1, 1, 4, 4], "offscreen": True}), "offscreen")
        self.assertEqual(location_status({**n, "rect": None}), "no_geometry")
        self.assertEqual(location_status({**n, "rect": [0, 0, 0, 50]}), "no_geometry")

    def test_property_panel_is_contextual_control_not_top_menu(self):
        a = {"role": "CheckBoxControl", "automation_id": "sch_property_panelCompany",
             "path": "Main > sch_property_panel > 公司"}
        self.assertTrue(is_property_control(a))
        self.assertFalse(is_property_control({**a, "role": "MenuItemControl"}))

    def test_gui_filter_keeps_parent_chain_and_explicit_all(self):
        nodes = [
            {"id": 1, "parent_id": None, "name": "Main", "rect": None},
            {"id": 2, "parent_id": 1, "name": "Group", "rect": None},
            {"id": 3, "parent_id": 2, "name": "导出", "rect": [10, 10, 70, 50]},
            {"id": 4, "parent_id": 2, "name": "公司", "rect": [0, 0, 0, 0]},
        ]
        self.assertEqual(tree_visible_ids(nodes, only_located=True), {1, 2, 3})
        self.assertEqual(tree_visible_ids(nodes, only_located=False), {1, 2, 3, 4})

    def test_txt_primary_does_not_fill_with_zero_rect_checkbox(self):
        nodes = [Node(1, None, 2, 0, "ButtonControl", "导出", rect=[10, 10, 80, 60], action_candidate=True)]
        for i in range(2, 42):
            nodes.append(Node(i, 1, 2, 1, "CheckBoxControl", f"属性{i}",
                              rect=[0, 0, 0, 0], enabled=True, action_candidate=True,
                              operation="UIA Toggle（切换）", path=f"sch_property_panel > 属性{i}"))
        text = format_text_report(ScanResult(pid=42, title="Test", windows=[WindowInfo(2, 42, "Test")], nodes=nodes))
        primary = text.split("一、当前可定位的功能与菜单入口")[1].split("二、属性面板控件")[0]
        self.assertIn("#1 导出", primary)
        self.assertNotIn("#2 属性2", primary)
        self.assertIn("另外 10 项详见完整控件树", text)
        self.assertIn("#41 [CheckBoxControl] 属性41", text)


if __name__ == "__main__":
    unittest.main()
