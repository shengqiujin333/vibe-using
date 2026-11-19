import unittest

from vibe_using.models import WindowInfo
from vibe_using.scanner import Limits, scan_process


class FakeControl:
    def __init__(self, role, name, children=None, fail_children=False):
        self.role = role
        self.name = name
        self.kids = children or []
        self.fail_children = fail_children


class FakeAdapter:
    def __init__(self, windows):
        self.windows = windows

    def from_handle(self, hwnd):
        return self.windows[hwnd]

    def describe(self, control):
        return {"role": control.role, "name": control.name}

    def children(self, control):
        if control.fail_children:
            raise RuntimeError("inaccessible")
        return control.kids


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.windows = [WindowInfo(1, 44, "Demo"), WindowInfo(2, 45, "Other")]
        self.adapter = FakeAdapter({
            1: FakeControl("WindowControl", "Main", [
                FakeControl("MenuItemControl", "File", [FakeControl("ButtonControl", "Export")]),
                FakeControl("TextControl", "Hint", fail_children=True),
            ]),
            2: FakeControl("WindowControl", "Other"),
        })

    def test_process_filter_and_tree_parents(self):
        result = scan_process(self.windows, 44, self.adapter)
        self.assertEqual([n.name for n in result.nodes], ["Main", "File", "Export", "Hint"])
        self.assertEqual([n.parent_id for n in result.nodes], [None, 1, 2, 1])
        self.assertEqual([n.depth for n in result.nodes], [0, 1, 2, 1])
        self.assertTrue(result.nodes[1].action_candidate)
        self.assertTrue(result.nodes[2].action_candidate)
        self.assertFalse(result.nodes[0].action_candidate)
        self.assertIn("inaccessible", result.nodes[3].error)
        self.assertEqual(len(result.windows), 1)

    def test_max_depth(self):
        result = scan_process(self.windows, 44, self.adapter, Limits(max_depth=1))
        self.assertEqual([n.name for n in result.nodes], ["Main", "File", "Hint"])

    def test_max_nodes(self):
        result = scan_process(self.windows, 44, self.adapter, Limits(max_nodes=2))
        self.assertEqual(len(result.nodes), 2)
        self.assertTrue(result.truncated)

    def test_child_cap(self):
        result = scan_process(self.windows, 44, self.adapter, Limits(max_children=1))
        self.assertEqual([n.name for n in result.nodes], ["Main", "File", "Export"])
        self.assertTrue(result.truncated)

    def test_root_unavailable(self):
        result = scan_process([WindowInfo(90, 44, "Bad")], 44, self.adapter)
        self.assertEqual(len(result.nodes), 0)
        self.assertEqual(len(result.errors), 1)

    def test_no_windows(self):
        result = scan_process(self.windows, 999, self.adapter)
        self.assertFalse(result.windows)
        self.assertTrue(result.errors)

    def test_limits_validation(self):
        with self.assertRaises(ValueError):
            Limits(max_nodes=0)
        with self.assertRaises(ValueError):
            Limits(max_seconds=0)


if __name__ == "__main__":
    unittest.main()
