"""Persistent per-scan inventory. No online services or telemetry."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any

from .models import ScanResult


DEFAULT_DB = Path.home() / ".vibe-using" / "inventory.sqlite3"


class InventoryDB:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY,
                    created_utc TEXT NOT NULL,
                    pid INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    window_json TEXT NOT NULL,
                    errors_json TEXT NOT NULL,
                    truncated INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS nodes (
                    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
                    id INTEGER NOT NULL,
                    parent_id INTEGER,
                    role TEXT NOT NULL,
                    name TEXT NOT NULL,
                    automation_id TEXT NOT NULL,
                    class_name TEXT NOT NULL,
                    action_candidate INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    PRIMARY KEY (scan_id, id)
                );
                CREATE INDEX IF NOT EXISTS ix_nodes_role ON nodes(scan_id, role);
                CREATE INDEX IF NOT EXISTS ix_nodes_parent ON nodes(scan_id, parent_id);
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def save(self, result: ScanResult) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO scans (created_utc,pid,title,window_json,errors_json,truncated) VALUES (?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), result.pid, result.title,
                 json.dumps([asdict(w) for w in result.windows], ensure_ascii=False),
                 json.dumps(result.errors, ensure_ascii=False), int(result.truncated)),
            )
            scan_id = int(cursor.lastrowid)
            conn.executemany(
                "INSERT INTO nodes (scan_id,id,parent_id,role,name,automation_id,class_name,action_candidate,data_json) VALUES (?,?,?,?,?,?,?,?,?)",
                [(scan_id, n.id, n.parent_id, n.role, n.name, n.automation_id, n.class_name,
                  int(n.action_candidate), json.dumps(n.to_dict(), ensure_ascii=False)) for n in result.nodes],
            )
        return scan_id

    def list_scans(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            records = conn.execute("""
                SELECT s.*, COUNT(n.id) AS node_count
                FROM scans s LEFT JOIN nodes n ON n.scan_id=s.id
                GROUP BY s.id ORDER BY s.id DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(row) for row in records]

    def get(self, scan_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            scan = conn.execute("SELECT * FROM scans WHERE id=?", (scan_id,)).fetchone()
            if not scan:
                raise KeyError(f"Unknown scan ID: {scan_id}")
            nodes = conn.execute("SELECT data_json FROM nodes WHERE scan_id=? ORDER BY id", (scan_id,)).fetchall()
        parsed = [json.loads(n["data_json"]) for n in nodes]
        return {
            "schema_version": 1,
            "capture_mode": "read_only",
            "platform": "windows-uia",
            "scan_id": scan_id,
            "created_utc": scan["created_utc"],
            "pid": scan["pid"],
            "title": scan["title"],
            "windows": json.loads(scan["window_json"]),
            "errors": json.loads(scan["errors_json"]),
            "truncated": bool(scan["truncated"]),
            "nodes": parsed,
            "summary": {"nodes": len(parsed), "action_candidates": sum(n["action_candidate"] for n in parsed)},
            "disclaimer": "This is a partial UI snapshot, not a verified complete function list.",
        }

    def search(self, query: str, scan_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
        """Substring search, with SQL LIKE metacharacters treated literally."""
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        where_scan = " AND scan_id=?" if scan_id is not None else ""
        params: tuple[Any, ...] = (pattern, pattern, pattern, pattern) + ((scan_id,) if scan_id is not None else ()) + (limit,)
        with self._connect() as conn:
            rows = conn.execute(f"""
                SELECT scan_id,data_json FROM nodes
                WHERE (name LIKE ? ESCAPE '\\' OR role LIKE ? ESCAPE '\\'
                    OR automation_id LIKE ? ESCAPE '\\' OR class_name LIKE ? ESCAPE '\\')
                    {where_scan}
                ORDER BY scan_id DESC,id LIMIT ?
            """, params).fetchall()
        return [{"scan_id": row["scan_id"], **json.loads(row["data_json"])} for row in rows]

    def export_json(self, scan_id: int, path: str | Path) -> Path:
        dest = Path(path).expanduser()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(self.get(scan_id), ensure_ascii=False, indent=2), encoding="utf-8")
        return dest
