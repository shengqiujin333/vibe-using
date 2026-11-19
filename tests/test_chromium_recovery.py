"""Regression: a hollow Chromium scan must never be called a normal inventory."""
import unittest

from vibe_using.chromium_recovery import missing_chromium_contents, missing_chromium_contents_data
from vibe_using.models import WindowInfo
from vibe_using.scanner import Limits
from vibe_using.service import scan_with_recovery
from vibe_using.text_report import format_text_report
from vibe_using.windows_chromium import ActivationResult


class C:
    def __init__(self, role, name="", cls="", children=None):
        self.role, self.name, self.cls, self.kids = role, name, cls, children or []


class Adapter:
    def __init__(self, root):
        self.root = root

    def from_handle(self, hwnd):
        return self.root

    def describe(self, control):
        return {"role": control.role, "name": control.name, "class_name": control.cls}

    def children(self, control):
        return control.kids


def hollow():
    return C("PaneControl", "Editor", "Chrome_WidgetWin_1", [
        C("PaneControl", children=[C("PaneControl", children=[C("PaneControl")])]),
        C("TitleBarControl"),
    ])


def full():
    return C("PaneControl", "Editor", "Chrome_WidgetWin_1", [
        C("DocumentControl", children=[
            C("GroupControl", "文件", children=[C("MenuItemControl", "导出")]),
            C("GroupControl", "编辑"),
        ]),
    ])


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.windows = [WindowInfo(88, 22, "Editor")]
        self.limits = Limits()

    def test_recovery_rescans_after_chromium_activation(self):
        attempts = []
        roots = iter([hollow(), full()])
        def activate(handles):
            attempts.append(handles)
            return ActivationResult(handles=(10,), signaled=1)
        result = scan_with_recovery(self.windows, 22, self.limits, lambda: Adapter(next(roots)), activate, delay=lambda _: None)
        self.assertEqual(attempts, [[88]])
        self.assertFalse(missing_chromium_contents(result))
        self.assertEqual([n.name for n in result.nodes if n.name][-2:], ["导出", "编辑"])
        self.assertIn("文件", format_text_report(result))

    def test_recovery_failure_emits_loud_persistent_diagnostic(self):
        result = scan_with_recovery(self.windows, 22, self.limits, lambda: Adapter(hollow()),
                                    lambda _: ActivationResult(), delay=lambda _: None)
        self.assertTrue(missing_chromium_contents(result))
        self.assertTrue(any("扫描不完整" in e for e in result.errors))
        text = format_text_report(result)
        self.assertIn("【警告】", text)
        self.assertIn("下面的空清单不是软件没有功能", text)
        self.assertIn("扫描诊断 / 异常", text)

    def test_no_automatic_activation_on_normal_windows_ui(self):
        def fail(_):
            self.fail("should not attempt Chromium recovery")
        result = scan_with_recovery(self.windows, 22, self.limits, lambda: Adapter(C("WindowControl", "Notepad")), fail)
        self.assertFalse(result.errors)
        self.assertFalse(missing_chromium_contents_data(result.to_dict()["nodes"]))

    def test_shallow_tree_cannot_be_mistaken_for_full_contents(self):
        from vibe_using.scanner import scan_process
        r = scan_process(self.windows, 22, Adapter(hollow()))
        self.assertTrue(missing_chromium_contents(r))
        self.assertTrue(missing_chromium_contents_data(r.to_dict()["nodes"]))

    def test_rich_chromium_tree_has_no_false_warning(self):
        from vibe_using.scanner import scan_process
        r = scan_process(self.windows, 22, Adapter(full()))
        self.assertFalse(missing_chromium_contents(r))
        self.assertNotIn("【警告】", format_text_report(r))


if __name__ == "__main__":
    unittest.main()
