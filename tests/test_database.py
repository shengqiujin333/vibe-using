import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vibe_using.database import InventoryDB
from vibe_using.models import Node, ScanResult, WindowInfo


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = InventoryDB(Path(self.tmp.name) / "nested" / "test.sqlite3")
        self.scan = ScanResult(
            pid=11, title="Example", windows=[WindowInfo(100, 11, "Example")],
            nodes=[
                Node(1, None, 100, 0, "WindowControl", "Example"),
                Node(2, 1, 100, 1, "ButtonControl", "导出_100%", automation_id="export", action_candidate=True),
            ],
            errors=["one inaccessible popup"], truncated=True,
        )

    def test_round_trip_and_counts(self):
        scan_id = self.db.save(self.scan)
        record = self.db.get(scan_id)
        self.assertEqual(record["nodes"][1]["parent_id"], 1)
        self.assertEqual(record["summary"]["action_candidates"], 1)
        self.assertEqual(record["windows"][0]["hwnd"], 100)
        self.assertTrue(record["truncated"])
        self.assertEqual(record["errors"], ["one inaccessible popup"])
        self.assertEqual(self.db.list_scans()[0]["node_count"], 2)

    def test_search_literals_and_scoping(self):
        scan_id = self.db.save(self.scan)
        self.assertEqual(len(self.db.search("导出_100%", scan_id)), 1)
        self.assertEqual(len(self.db.search("导出_100_", scan_id)), 0)
        self.assertEqual(len(self.db.search("export", scan_id)), 1)
        self.assertEqual(len(self.db.search("missing", scan_id)), 0)
        self.assertEqual(len(self.db.search("ButtonControl", scan_id)), 1)

    def test_export_and_missing(self):
        scan_id = self.db.save(self.scan)
        path = self.db.export_json(scan_id, Path(self.tmp.name) / "exports" / "out.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["nodes"][1]["name"], "导出_100%")
        with self.assertRaises(KeyError):
            self.db.get(999)


if __name__ == "__main__":
    unittest.main()
