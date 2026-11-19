"""GUI + headless entry points."""
from __future__ import annotations

import argparse
import json
import sys

from .database import DEFAULT_DB, InventoryDB
from .scanner import Limits


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read-only Windows UI inventory; stores local SQLite snapshots")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--list-windows", action="store_true", help="List visible titled top-level windows")
    mode.add_argument("--scan-pid", type=int, metavar="PID", help="Scan visible windows belonging to PID")
    mode.add_argument("--export-scan", type=int, metavar="ID", help="Export saved scan as JSON")
    mode.add_argument("--search", metavar="QUERY", help="Search saved scan nodes by label/role/ID")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB file (default: ~/.vibe-using/inventory.sqlite3)")
    p.add_argument("--output", help="JSON output path for --scan-pid or --export-scan")
    p.add_argument("--scan-id", type=int, help="Filter --search to one scan")
    p.add_argument("--max-depth", type=int, default=12)
    p.add_argument("--max-nodes", type=int, default=6000)
    p.add_argument("--max-seconds", type=float, default=30.0)
    p.add_argument("--include-text", action="store_true", help="Include potentially sensitive text/edit/document names")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.list_windows or args.scan_pid is not None:
        if sys.platform != "win32":
            print("Windows-only scanning requires Windows 10/11.", file=sys.stderr)
            return 2
        from .win32 import list_windows

        windows = list_windows()
        if args.list_windows:
            print(json.dumps([w.__dict__ for w in windows], indent=2, ensure_ascii=False))
            return 0
        try:
            limits = Limits(args.max_depth, args.max_nodes, args.max_seconds)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        from .service import scan_windows

        result = scan_windows(windows, args.scan_pid, limits, args.include_text)
        if not result.windows:
            print("No visible titled windows found for that PID", file=sys.stderr)
            return 1
        db = InventoryDB(args.db)
        scan_id = db.save(result)
        output = {"scan_id": scan_id, **result.to_dict()}
        if args.output:
            db.export_json(scan_id, args.output)
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0
    if args.export_scan is not None or args.search is not None:
        db = InventoryDB(args.db)
        try:
            if args.export_scan is not None:
                if not args.output:
                    parser().error("--export-scan requires --output")
                path = db.export_json(args.export_scan, args.output)
                print(path)
            else:
                matches = db.search(args.search, args.scan_id)
                print(json.dumps(matches, indent=2, ensure_ascii=False))
        except KeyError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0
    if sys.platform != "win32":
        print("The GUI requires Windows 10/11. Headless tests can run on other platforms.", file=sys.stderr)
        return 2
    from .gui import run_gui

    run_gui(args.db)
    return 0
