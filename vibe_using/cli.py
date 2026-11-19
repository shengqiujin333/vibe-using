"""GUI + headless entry points."""
from __future__ import annotations

import argparse
import json
import sys

from .database import DEFAULT_DB, InventoryDB
from .scanner import Limits
from .text_report import default_report_path, format_text_report


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read-only Windows UI control/function inventory; exports readable TXT")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--list-windows", action="store_true", help="List visible titled top-level windows")
    mode.add_argument("--scan-pid", type=int, metavar="PID", help="Scan visible windows belonging to PID")
    mode.add_argument("--export-scan", type=int, metavar="ID", help="Export saved scan as JSON")
    mode.add_argument("--export-txt", type=int, metavar="ID", help="Export saved scan as readable TXT")
    mode.add_argument("--search", metavar="QUERY", help="Search saved scan nodes by label/role/ID")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB file (default: ~/.vibe-using/inventory.sqlite3)")
    p.add_argument("--output", help="JSON output path for --scan-pid/--export-scan; TXT path for --export-txt")
    p.add_argument("--reports-dir", default="scans", help="Automatic TXT folder for --scan-pid (default: ./scans)")
    p.add_argument("--scan-id", type=int, help="Filter --search to one scan")
    p.add_argument("--max-depth", type=int, default=12)
    p.add_argument("--max-nodes", type=int, default=6000)
    p.add_argument("--max-seconds", type=float, default=30.0)
    p.add_argument("--include-text", action="store_true", help="Also include potentially sensitive Edit/Document names (TextControl labels are included by default)")
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
        output = db.get(scan_id)
        report_path = db.export_txt(scan_id, default_report_path(scan_id, result.pid, args.reports_dir))
        if args.output:
            db.export_json(scan_id, args.output)
        print(format_text_report(output))
        print(f"TXT 已保存: {report_path.resolve()}")
        return 0
    if args.export_scan is not None or args.export_txt is not None or args.search is not None:
        db = InventoryDB(args.db)
        try:
            if args.export_scan is not None:
                if not args.output:
                    parser().error("--export-scan requires --output")
                path = db.export_json(args.export_scan, args.output)
                print(path)
            elif args.export_txt is not None:
                record = db.get(args.export_txt)
                path = args.output or default_report_path(args.export_txt, record["pid"])
                path = db.export_txt(args.export_txt, path)
                print(path.resolve())
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
