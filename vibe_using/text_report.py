"""Human-readable, offline Windows UIA scan reports (no clicks or AI calls)."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .models import ScanResult


def default_report_path(scan_id: int, pid: int, reports_dir: str | Path | None = None) -> Path:
    """Use a visible folder beside the user's current terminal working directory."""
    folder = Path(reports_dir).expanduser() if reports_dir is not None else Path.cwd() / "scans"
    return folder / f"scan-{scan_id}-pid-{pid}.txt"


def _clean(value: Any) -> str:
    """Keep a single scan field on one line, including untrusted window titles."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def format_text_report(record: dict[str, Any] | ScanResult) -> str:
    """Render a complete indented view of discovered windows and controls."""
    data = record.to_dict() if isinstance(record, ScanResult) else record
    windows = data.get("windows", [])
    nodes = data.get("nodes", [])
    action_count = sum(bool(n.get("action_candidate")) for n in nodes)
    lines = [
        "Vibe Using - Windows 软件界面扫描结果",
        "=" * 65,
        f"软件窗口: {_clean(data.get('title')) or '(无标题)'}",
        f"进程 PID: {data.get('pid', '')}",
    ]
    if data.get("scan_id") is not None:
        lines.append(f"扫描编号: {data['scan_id']}")
    if data.get("created_utc"):
        lines.append(f"扫描时间(UTC): {_clean(data['created_utc'])}")
    lines.extend([
        f"窗口数量: {len(windows)} | 控件数量: {len(nodes)} | 候选可交互控件: {action_count}",
        f"扫描是否截断: {'是' if data.get('truncated') else '否'}",
        "说明: 这是只读采集到的当前界面结构，不代表软件全部功能，也未验证操作 SOP。",
        "注意: 窗口标题及控件名称可能含文件名或个人信息，分享 TXT 前请检查。",
        "",
        "窗口及控件树",
        "-" * 65,
    ])
    for window in windows:
        hwnd = window.get("hwnd")
        lines.append(f"窗口: {_clean(window.get('title')) or '(无标题)'} [HWND={hwnd}, PID={window.get('pid', '')}]")
        belonging = [n for n in nodes if n.get("window_hwnd") == hwnd]
        if not belonging:
            lines.append("  (没有读取到 UIA 控件)")
        for n in belonging:
            depth = max(0, min(50, int(n.get("depth") or 0)))
            name = _clean(n.get("name")) or "(无名称)"
            role = _clean(n.get("role")) or "UnknownControl"
            lines.append(f"{'  ' * (depth + 1)}- #{n.get('id', '?')} [{role}] {name}")
            details = []
            for field, label in (
                ("automation_id", "AutomationId"),
                ("class_name", "Class"),
                ("accelerator_key", "快捷键"),
                ("access_key", "访问键"),
            ):
                value = _clean(n.get(field))
                if value:
                    details.append(f"{label}={value}")
            if n.get("action_candidate"):
                details.append("候选交互控件")
            if n.get("enabled") is not None:
                details.append("可用" if n["enabled"] else "禁用")
            if n.get("offscreen"):
                details.append("屏幕外")
            if n.get("error"):
                details.append(f"读取异常={_clean(n['error'])}")
            if details:
                lines.append(f"{'  ' * (depth + 2)}{' | '.join(details)}")
        lines.append("")
    if not windows:
        lines.append("(没有发现可扫描窗口)")
        lines.append("")
    if data.get("errors"):
        lines.append("扫描错误")
        lines.append("-" * 65)
        lines.extend(f"- {_clean(error)}" for error in data["errors"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def save_text_report(record: dict[str, Any] | ScanResult, path: str | Path) -> Path:
    dest = Path(path).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    # UTF-8 BOM makes Chinese render correctly in older Windows Notepad builds.
    dest.write_text(format_text_report(record), encoding="utf-8-sig")
    return dest
