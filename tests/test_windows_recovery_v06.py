"""Provider fallback regression tests that do not require a Windows desktop."""
import unittest

from vibe_using.chromium_recovery import coverage_warning
from vibe_using.models import WindowInfo
from vibe_using.scanner import Limits
from vibe_using.service import scan_with_recovery
from vibe_using.windows_chromium import ActivationResult, activation_targets
from vibe_using.windows_probe import select_content_ancestor


class Element:
    def __init__(self, role, name='', class_name='', children=(), parent=None):
        self.role = role
        self.name = name
        self.class_name = class_name
        self.kids = list(children)
        self.parent = parent
        self.ControlTypeName = role
        self.Name = name
        self.ClassName = class_name
        for child in self.kids:
            child.parent = self

    def GetParentControl(self):
        return self.parent


class FakeAdapter:
    def __init__(self, root):
        self.root = root

    def from_handle(self, hwnd):
        return self.root

    def describe(self, control):
        return {'role': control.role, 'name': control.name, 'class_name': control.class_name}

    def children(self, control):
        return control.kids


def hollow():
    return Element('PaneControl', 'EDA', 'Chrome_WidgetWin_1', [
        Element('PaneControl', children=[Element('PaneControl')])
    ])


def document():
    return Element('DocumentControl', '', children=[
        Element('GroupControl', '文件', children=[Element('MenuItemControl', '打开')]),
        Element('GroupControl', '放置', children=[Element('MenuItemControl', '元件')]),
    ])


class WindowsRecoveryV06Tests(unittest.TestCase):
    def setUp(self):
        self.win = [WindowInfo(88, 22, 'EDA')]

    def test_no_renderer_still_tries_chromium_top_level(self):
        targets = activation_targets([88], (), lambda _: 'Chrome_WidgetWin_1')
        self.assertEqual(targets, ((88, 1, 'top-level custom object'),
                                   (88, -4, 'top-level OBJID_CLIENT')))

    def test_arbitrary_windows_are_not_signaled(self):
        self.assertEqual(activation_targets([88], (), lambda _: 'Notepad'), ())

    def test_no_renderer_but_top_level_wake_can_restore_tree(self):
        roots = iter([hollow(), document()])
        result = scan_with_recovery(
            self.win, 22, Limits(), lambda: FakeAdapter(next(roots)),
            lambda _: ActivationResult(signaled=1, top_level_requests=2),
            delay=lambda _: None,
        )
        self.assertEqual([n.name for n in result.nodes if n.name], ['文件', '打开', '放置', '元件'])
        self.assertFalse(any('扫描不完整' in s for s in result.errors))

    def test_point_probe_recovers_without_renderer_or_top_level_wake(self):
        result = scan_with_recovery(
            self.win, 22, Limits(), lambda: FakeAdapter(hollow()),
            lambda _: ActivationResult(top_level_requests=2),
            point_probe=lambda adapter, windows, pid: (
                [(windows[0], document())], '6 个点中发现文档区域'),
            delay=lambda _: None,
        )
        self.assertIn('打开', [n.name for n in result.nodes])
        self.assertTrue(any('部分控件' in s for s in result.errors))
        self.assertFalse(any('扫描不完整' in s for s in result.errors))

    def test_point_probe_cannot_mistake_anonymous_panes_as_recovery(self):
        result = scan_with_recovery(
            self.win, 22, Limits(), lambda: FakeAdapter(hollow()),
            lambda _: ActivationResult(top_level_requests=2),
            point_probe=lambda adapter, windows, pid: (
                [(windows[0], Element('PaneControl', children=[Element('PaneControl')]))],
                '查询候选子树 1'),
            delay=lambda _: None,
        )
        self.assertTrue(any('扫描不完整' in s for s in result.errors))
        self.assertTrue(any('查询候选子树' in s for s in result.errors))

    def test_select_document_parent_not_just_clicked_child(self):
        doc = document()
        leaf = doc.kids[0].kids[0]
        self.assertIs(select_content_ancestor(leaf), doc)

    def test_warning_describes_actual_root_probe(self):
        warning = coverage_warning(attempted=True, root_requests=2)
        self.assertIn('顶层窗口', warning)
        self.assertIn('2 次', warning)
        self.assertNotIn('无法发送', warning)


if __name__ == '__main__':
    unittest.main()
